"""Unsplash API 기반 전이 비용 학습 데이터 수집 (흐름도 > Unsplash API 기반 전이 비용 학습 데이터 수집 설계).

흐름: 테마 검색어 -> Unsplash /search/photos -> 사진마다 build_feature_vector(11d)로 피처만 추출
      -> photos.csv 저장 -> 같은 테마=pos/다른 테마=neg로 트리플렛 샘플링 -> pairs.csv 저장

2단계 TransitionCostModel 학습용 라벨 데이터를 실사용자 트래픽 없이 준자동으로 만들기 위한 수집 스크립트.
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

from features import HUE_HIST_BINS
from mlp import build_feature_vector

THEMES = [
    "minimalist aesthetic photography",
    "vintage retro film photography",
    "moody urban night photography",
]
PHOTOS_PER_THEME = 30
TRIPLETS_PER_THEME = 15

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"

DATA_DIR = Path(__file__).parent / "data" / "unsplash"
PHOTOS_CSV_FIELDS = [
    "photo_id", "query", "unsplash_url", "clip_sim",
    "mean_h", "mean_s", "mean_v", "sat_std", "val_std", "contrast",
    "hue_hist_0", "hue_hist_1", "hue_hist_2", "hue_hist_3",
]
PAIRS_CSV_FIELDS = ["theme", "pos", "neg"]


def sample_triplets(photo_rows: list[dict], triplets_per_theme: int, rng: random.Random) -> list[dict]:
    """수집된 사진 행(테마별) -> pos/neg 트리플렛 -> TransitionCostModel 학습용 데이터."""
    by_theme: dict[str, list[str]] = {}
    for row in photo_rows:
        by_theme.setdefault(row["query"], []).append(row["photo_id"])

    triplets = []
    for theme, photo_ids in by_theme.items():
        if len(photo_ids) < triplets_per_theme:
            raise ValueError(
                f"테마 '{theme}'의 사진 수({len(photo_ids)})가 triplets_per_theme({triplets_per_theme})보다 적음"
            )
        pos_picks = rng.sample(photo_ids, triplets_per_theme)
        other_photo_ids = [pid for t, ids in by_theme.items() if t != theme for pid in ids]
        for pos in pos_picks:
            neg = rng.choice(other_photo_ids)
            triplets.append({"theme": theme, "pos": pos, "neg": neg})
    return triplets


def search_photos(theme: str, access_key: str, per_page: int = PHOTOS_PER_THEME) -> list[dict]:
    """테마 검색어 -> Unsplash /search/photos -> 사진 메타데이터 리스트(raw JSON)."""
    response = httpx.get(
        UNSPLASH_SEARCH_URL,
        params={"query": theme, "per_page": per_page},
        headers={"Authorization": f"Client-ID {access_key}"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["results"]


def photo_to_row(photo: dict, theme: str) -> dict | None:
    """Unsplash 사진 1장 -> 11차원 피처(clip_sim + 색감 10) 행. 다운로드/피처 추출 실패 시 None."""
    try:
        image_response = httpx.get(photo["urls"]["regular"], timeout=30.0)
        image_response.raise_for_status()
        image = Image.open(BytesIO(image_response.content)).convert("RGB")
        feats = build_feature_vector(image, theme)
    except Exception as exc:  # 네트워크/디코딩 실패는 이 사진만 건너뜀
        print(f"[skip] {photo.get('id')}: {exc}")
        return None

    row = {
        "photo_id": photo["id"],
        "query": theme,
        "unsplash_url": photo["links"]["html"],
        "clip_sim": float(feats[0]),
        "mean_h": float(feats[1]),
        "mean_s": float(feats[2]),
        "mean_v": float(feats[3]),
        "sat_std": float(feats[4]),
        "val_std": float(feats[5]),
        "contrast": float(feats[6]),
    }
    for i in range(HUE_HIST_BINS):
        row[f"hue_hist_{i}"] = float(feats[7 + i])
    return row


def collect_all_photos(themes: list[str], access_key: str, per_page: int) -> list[dict]:
    """테마 리스트 전체를 검색해 피처 행 리스트로 변환 (다운로드 실패 사진은 제외)."""
    rows = []
    for theme in themes:
        for photo in search_photos(theme, access_key, per_page):
            row = photo_to_row(photo, theme)
            if row is not None:
                rows.append(row)
    return rows


def write_csv(rows: list[dict], path: Path, fieldnames: list[str]) -> None:
    """딕셔너리 행 리스트 -> CSV 파일 저장."""
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

    photo_rows = collect_all_photos(THEMES, access_key, PHOTOS_PER_THEME)
    write_csv(photo_rows, DATA_DIR / "photos.csv", PHOTOS_CSV_FIELDS)
    print(f"photos.csv: {len(photo_rows)}장 저장")

    triplets = sample_triplets(photo_rows, TRIPLETS_PER_THEME, random.Random())
    write_csv(triplets, DATA_DIR / "pairs.csv", PAIRS_CSV_FIELDS)
    print(f"pairs.csv: {len(triplets)}행 저장")
