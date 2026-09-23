"""고정 테마 하나에 대한 ScoringMLP 학습 데이터를 Unsplash 사진으로 재구성.

흐름: Ai/data/unsplash/photos.csv -> 고정 테마 사진(pos, clip_sim 이미 정확)
      + 다른 테마 사진 일부(neg, photo_id로 Unsplash에서 원본 이미지 재다운로드해
      고정 테마 기준 clip_sim 재계산) -> {theme, pos, neg} 트리플렛 +
      photo_id -> 11차원 피처 CSV로 저장

ScoringMLP는 "고정된 테마 하나" 기준 절대 점수용 모델이라, collect_unsplash_data.py의
회전식 다중 테마 pairs.csv를 그대로 쓸 수 없다(docs/ai/Transition_cost_model.md 참고).
같은 Unsplash 파일럿 데이터를 재활용하되, neg 후보만 고정 테마 기준으로 clip_sim을
다시 계산해 label_pairs.json과 동일한 구조(단일 고정 테마)로 맞춘다. 색감 피처(10d)는
테마와 무관하게 사진 고유의 값이라 재계산하지 않고 그대로 재사용한다.

photos.csv의 unsplash_url은 추적용 웹페이지 링크(photo.links.html)라 이미지를 바로
받을 수 없어, Unsplash "Get a photo"(/photos/:id) API로 원본 이미지 URL을 다시 조회한다.
"""

from __future__ import annotations

import csv
import os
import random
from io import BytesIO
from pathlib import Path

import httpx
from dotenv import load_dotenv
from PIL import Image

from clip import get_theme_score
from collect_unsplash_data import DATA_DIR as UNSPLASH_DATA_DIR
from collect_unsplash_data import FEATURE_FIELDS

FIXED_THEME = "black and white monochrome photography"
N_PAIRS = 15
SEED = 42

UNSPLASH_PHOTO_URL = "https://api.unsplash.com/photos/{photo_id}"
SOURCE_PHOTOS_PATH = UNSPLASH_DATA_DIR / "photos.csv"
DATA_DIR = Path(__file__).parent / "data" / "unsplash"
SCORING_PHOTOS_CSV_FIELDS = ["photo_id", "unsplash_url"] + FEATURE_FIELDS
SCORING_PAIRS_CSV_FIELDS = ["theme", "pos", "neg"]


def load_source_rows(path: Path = SOURCE_PHOTOS_PATH) -> list[dict]:
    """collect_unsplash_data.py가 만든 photos.csv를 그대로 읽음."""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fetch_image_url(photo_id: str, access_key: str) -> str:
    """photo_id -> Unsplash "Get a photo" API -> 원본 이미지 다운로드 URL."""
    response = httpx.get(
        UNSPLASH_PHOTO_URL.format(photo_id=photo_id),
        headers={"Authorization": f"Client-ID {access_key}"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["urls"]["regular"]


def recompute_clip_sim(row: dict, theme_text: str, access_key: str) -> float:
    """다른 테마로 수집된 사진 하나를 원본에서 다시 받아, 고정 테마 기준 clip_sim을 재계산."""
    image_url = fetch_image_url(row["photo_id"], access_key)
    image_response = httpx.get(image_url, timeout=30.0)
    image_response.raise_for_status()
    image = Image.open(BytesIO(image_response.content)).convert("RGB")
    return get_theme_score(image, theme_text)


def build_scoring_rows(
    source_rows: list[dict], theme_text: str, n_pairs: int, access_key: str, rng: random.Random
) -> list[dict]:
    """고정 테마 사진(pos, clip_sim 그대로)과 다른 테마 일부(neg, clip_sim 재계산)를 합친 행 목록."""
    pos_candidates = [row for row in source_rows if row["query"] == theme_text]
    other_candidates = [row for row in source_rows if row["query"] != theme_text]
    neg_picks = rng.sample(other_candidates, n_pairs)

    rows = []
    for row in pos_candidates:
        rows.append({"photo_id": row["photo_id"], "unsplash_url": row["unsplash_url"], **{f: row[f] for f in FEATURE_FIELDS}})
    for row in neg_picks:
        feats = {f: row[f] for f in FEATURE_FIELDS}
        feats["clip_sim"] = recompute_clip_sim(row, theme_text, access_key)
        rows.append({"photo_id": row["photo_id"], "unsplash_url": row["unsplash_url"], **feats})
    return rows


def sample_scoring_pairs(pos_ids: list[str], neg_ids: list[str], theme_text: str, rng: random.Random) -> list[dict]:
    """pos/neg photo_id 목록을 1:1로 섞어 {theme, pos, neg} 트리플렛 생성."""
    shuffled_pos = pos_ids[:]
    shuffled_neg = neg_ids[:]
    rng.shuffle(shuffled_pos)
    rng.shuffle(shuffled_neg)
    return [{"theme": theme_text, "pos": pos, "neg": neg} for pos, neg in zip(shuffled_pos, shuffled_neg)]


def write_csv(rows: list[dict], path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    load_dotenv()
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not access_key:
        print("UNSPLASH_ACCESS_KEY가 .env에 없음")
        raise SystemExit(1)

    rng = random.Random(SEED)
    source_rows = load_source_rows()

    scoring_rows = build_scoring_rows(source_rows, FIXED_THEME, N_PAIRS, access_key, rng)
    write_csv(scoring_rows, DATA_DIR / "scoring_photos.csv", SCORING_PHOTOS_CSV_FIELDS)
    print(f"scoring_photos.csv: {len(scoring_rows)}장 저장")

    pos_ids = [row["photo_id"] for row in source_rows if row["query"] == FIXED_THEME]
    neg_ids = [row["photo_id"] for row in scoring_rows if row["photo_id"] not in pos_ids]
    pairs = sample_scoring_pairs(pos_ids, neg_ids, FIXED_THEME, rng)
    write_csv(pairs, DATA_DIR / "scoring_pairs.csv", SCORING_PAIRS_CSV_FIELDS)
    print(f"scoring_pairs.csv: {len(pairs)}쌍 저장 (theme={FIXED_THEME})")
