"""FastAPI 서버 - Ai/ScoringMLP(테마 필터링) + Ai/arrange_photos(정렬) 엔드포인트.

흐름: 사진 업로드(멀티파트) + 테마 문장 -> 11차원 피처 추출
      -> ScoringMLP로 부적합 사진 제외 제안 -> 그룹별로 arrange_photos로 정렬 -> JSON 응답

Ai/는 패키지가 아닌 bare import 스크립트 스타일이라, sys.path에 Ai/ 경로를 추가한 뒤
bare import로 재사용한다(tests/conftest.py와 동일한 패턴).
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

AI_DIR = Path(__file__).resolve().parent.parent / "Ai"
sys.path.insert(0, str(AI_DIR))

from io import BytesIO  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
from fastapi import File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from PIL import Image  # noqa: E402
from mlp import build_feature_vector, inference_scores, suggest_removal  # noqa: E402
from mlp import load_checkpoint as load_scoring_checkpoint  # noqa: E402
from transition_cost_model import load_checkpoint as load_transition_checkpoint  # noqa: E402
from arrange_photos import arrange_photos  # noqa: E402

scoring_model = None
transition_model = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scoring_model, transition_model
    # 체크포인트가 없으면 여기서 예외가 나서 서버 시작 자체가 실패한다(의도된 동작)
    scoring_model = load_scoring_checkpoint()
    transition_model = load_transition_checkpoint()
    yield


app = FastAPI(lifespan=lifespan)

# 프론트(Netlify)는 백엔드(CloudFront)와 주소가 달라 브라우저가 CORS 허락을 확인한다.
# 허용 주소는 코드에 박지 않고 환경변수로 받는다 — 주소가 바뀌어도 재빌드 없이 docker run -e로 바꿀 수 있게
# 기본값 localhost:3000은 개발용이고, 운영에서는 Netlify 주소로 덮어쓴다(빠뜨리면 프론트가 막혀 바로 드러남)
ALLOWED_ORIGINS = [
    origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


THRESHOLD = 0.35
BRUTE_FORCE_MAX = 8
MAX_PHOTOS = 20  # 인스타그램 캐러셀 최대치. Frontend/lib/limits.ts와 같은 값
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 프론트는 512px로 줄여 보내므로 정상 사용에선 안 걸림 — 원본 직접 전송 방어용


@app.post("/arrange")
async def arrange(
    theme: str = Form(...),
    photos: list[UploadFile] = File(default=[]),
    group_ids: list[int] = Form(default=[]),
):
    if not photos:
        raise HTTPException(400, "photos가 비어있음")
    if len(photos) > MAX_PHOTOS:
        raise HTTPException(400, f"사진은 최대 {MAX_PHOTOS}장까지 보낼 수 있음")
    if len(photos) != len(group_ids):
        raise HTTPException(400, "photos와 group_ids 길이가 다름")

    filenames = [photo.filename for photo in photos]
    if len(set(filenames)) != len(filenames):
        raise HTTPException(400, "photos에 중복된 파일명이 있음 — photo_id로 구분할 수 없음")

    color_feats: dict[str, np.ndarray] = {}
    photo_id_to_group: dict[str, int] = {}
    skipped: list[dict] = []

    for photo, group_id in zip(photos, group_ids):
        try:
            content = await photo.read()
            if len(content) > MAX_PHOTO_BYTES:
                skipped.append(
                    {"photo_id": photo.filename, "reason": f"용량 초과({MAX_PHOTO_BYTES // (1024 * 1024)}MB 제한)"}
                )
                continue
            image = Image.open(BytesIO(content)).convert("RGB")
            color_feats[photo.filename] = build_feature_vector(image, theme)
            photo_id_to_group[photo.filename] = group_id
        except Exception as exc:  # 손상된 이미지 등은 이 사진만 건너뜀
            skipped.append({"photo_id": photo.filename, "reason": str(exc)})

    if not color_feats:
        return {"removed_candidates": [], "skipped": skipped, "groups": []}

    photo_ids = list(color_feats.keys())
    feats_tensor = torch.from_numpy(np.stack([color_feats[pid] for pid in photo_ids]))
    keep_ids, remove_candidates = suggest_removal(scoring_model, feats_tensor, photo_ids, threshold=THRESHOLD)
    removed_candidates = [{"photo_id": pid, "score": score} for pid, score in remove_candidates]

    fitness_scores: dict[str, float] = {}
    if keep_ids:
        keep_feats_tensor = torch.from_numpy(np.stack([color_feats[pid] for pid in keep_ids]))
        fitness_scores = {
            pid: score.item() for pid, score in zip(keep_ids, inference_scores(scoring_model, keep_feats_tensor))
        }

    groups_by_id: dict[int, list[str]] = {}
    for pid in keep_ids:
        groups_by_id.setdefault(photo_id_to_group[pid], []).append(pid)
    # Review Focus: 필터링으로 전부 제거된 그룹은 조용히 결과에서 뺀다(빈 그룹으로 select_representative를 부르면 에러)
    non_empty_groups = [group for group in groups_by_id.values() if group]

    order: list[list[str]] = []
    adjacency: list[list[tuple[str, str, float]]] = []
    if non_empty_groups:
        order, adjacency = arrange_photos(
            non_empty_groups, color_feats, fitness_scores, transition_model, BRUTE_FORCE_MAX
        )

    groups_response = [
        {
            "order": group_order,
            "adjacency_costs": [[a, b, cost] for a, b, cost in group_adjacency],
        }
        for group_order, group_adjacency in zip(order, adjacency)
    ]

    return {"removed_candidates": removed_candidates, "skipped": skipped, "groups": groups_response}
