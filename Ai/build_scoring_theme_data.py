"""테마별 ScoringMLP 학습에 필요한 교차 clip_sim(사진 x 테마 문장 전부) 수집.

흐름: Ai/data/unsplash/photos.csv(사진 90장, 테마당 30장) -> photo_id로 Unsplash에서 원본 이미지
      재다운로드 -> CLIP 이미지 벡터 1번 + 테마 문장 3개와 각각 코사인 유사도
      -> cross_clip_sim.csv(photo_id, clip_mono, clip_vivid, clip_golden)에 한 줄씩 추가

photos.csv의 clip_sim은 "그 사진이 수집된 테마" 문장 기준 값 하나뿐이라, 테마마다 모델을 따로
학습하려면(이 테마 사진 = pos, 다른 테마 사진 = neg) 다른 테마 사진을 이 테마 문장으로 잰 값이
필요하다. 색감 피처(10d)는 테마와 무관한 사진 고유값이라 다시 계산하지 않는다.

photos.csv의 unsplash_url은 추적용 웹페이지 링크(photo.links.html)라 이미지를 바로
받을 수 없어, Unsplash "Get a photo"(/photos/:id) API로 원본 이미지 URL을 다시 조회한다.
이 API는 시간당 50회 제한이라 한 번 실행에 MAX_PHOTOS_PER_RUN장까지만 받고, 이미 받은 사진은
건너뛰므로 시간을 두고 다시 실행하면 이어서 채운다.
"""

from __future__ import annotations

import csv
import os
from io import BytesIO
from pathlib import Path

import httpx
import numpy as np
from dotenv import load_dotenv
from PIL import Image

from clip import cosine_similarity, get_image_embedding, get_text_embedding
from collect_unsplash_data import DATA_DIR as UNSPLASH_DATA_DIR
from mlp import THEME_KEYS

MAX_PHOTOS_PER_RUN = 45  # 시간당 50회 제한에서 여유를 둠

UNSPLASH_PHOTO_URL = "https://api.unsplash.com/photos/{photo_id}"
SOURCE_PHOTOS_PATH = UNSPLASH_DATA_DIR / "photos.csv"
CROSS_CLIP_PATH = UNSPLASH_DATA_DIR / "cross_clip_sim.csv"
CROSS_CLIP_FIELDS = ["photo_id"] + [f"clip_{key}" for key in THEME_KEYS.values()]


def load_source_rows(path: Path = SOURCE_PHOTOS_PATH) -> list[dict]:
    """collect_unsplash_data.py가 만든 photos.csv를 그대로 읽음."""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_done_photo_ids(path: Path = CROSS_CLIP_PATH) -> set[str]:
    """이미 cross_clip_sim.csv에 있는 photo_id — 재실행 시 건너뛰기 위함."""
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        return {row["photo_id"] for row in csv.DictReader(f)}


def pending_rows(source_rows: list[dict], done_ids: set[str], limit: int) -> list[dict]:
    """아직 계산 안 한 사진을 photos.csv 순서대로 limit장까지."""
    return [row for row in source_rows if row["photo_id"] not in done_ids][:limit]


def fetch_image(photo_id: str, access_key: str) -> Image.Image:
    """photo_id -> Unsplash "Get a photo" API로 원본 URL 조회 -> 이미지 다운로드."""
    response = httpx.get(
        UNSPLASH_PHOTO_URL.format(photo_id=photo_id),
        headers={"Authorization": f"Client-ID {access_key}"},
        timeout=30.0,
    )
    response.raise_for_status()
    image_response = httpx.get(response.json()["urls"]["regular"], timeout=30.0)
    image_response.raise_for_status()
    return Image.open(BytesIO(image_response.content)).convert("RGB")


def cross_clip_row(photo_id: str, image_vec: np.ndarray, theme_vecs: dict[str, np.ndarray]) -> dict:
    """사진 벡터 1개 x 테마 문장 벡터 전부 -> {photo_id, clip_<테마 키>...} 한 행."""
    row = {"photo_id": photo_id}
    for theme_text, key in THEME_KEYS.items():
        row[f"clip_{key}"] = cosine_similarity(image_vec, theme_vecs[theme_text])
    return row


def append_cross_clip_row(row: dict, path: Path = CROSS_CLIP_PATH) -> None:
    """한 장 계산할 때마다 바로 덧붙여 저장 — 중간에 제한·오류로 멈춰도 받은 만큼은 남는다."""
    is_new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CROSS_CLIP_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


if __name__ == "__main__":
    load_dotenv()
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not access_key:
        print("UNSPLASH_ACCESS_KEY가 .env에 없음")
        raise SystemExit(1)

    source_rows = load_source_rows()
    done_ids = load_done_photo_ids()
    todo = pending_rows(source_rows, done_ids, MAX_PHOTOS_PER_RUN)
    theme_vecs = {theme_text: get_text_embedding(theme_text) for theme_text in THEME_KEYS}

    saved = 0
    for row in todo:
        try:
            image = fetch_image(row["photo_id"], access_key)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 429):  # 시간당 요청 제한 — 나머지는 다음 실행에서
                print(f"요청 제한에 걸려 중단: {exc.response.status_code}")
                break
            print(f"[skip] {row['photo_id']}: {exc}")
            continue
        except httpx.HTTPError as exc:
            print(f"[skip] {row['photo_id']}: {exc}")
            continue
        append_cross_clip_row(cross_clip_row(row["photo_id"], get_image_embedding(image), theme_vecs))
        saved += 1

    total = len(done_ids) + saved
    print(f"cross_clip_sim.csv: 이번에 {saved}장 추가, 전체 {total}/{len(source_rows)}장")
    if total < len(source_rows):
        print("남은 사진이 있음 — 1시간쯤 뒤에 다시 실행하면 이어서 채운다")
