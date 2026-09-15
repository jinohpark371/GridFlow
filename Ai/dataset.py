"""Unsplash pos/neg 트리플렛(pairs.csv) 로딩 + photos.csv에서 피처 조회 (MLP 학습 입력 준비).

흐름: Ai/data/unsplash/pairs.csv({theme, pos, neg} 목록) + Ai/data/unsplash/photos.csv
      (photo_id -> 11차원 피처) -> photo_id로 피처 조회 -> (feats_pos, feats_neg) 텐서 쌍
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import torch

DEFAULT_PAIRS_PATH = Path(__file__).resolve().parent / "data" / "unsplash" / "pairs.csv"
DEFAULT_PHOTOS_PATH = Path(__file__).resolve().parent / "data" / "unsplash" / "photos.csv"

# collect_unsplash_data.py의 FEATURE_FIELDS와 동일한 순서 — photos.csv 컬럼이 이 순서로 저장돼 있음
FEATURE_FIELDS = [
    "clip_sim", "mean_h", "mean_s", "mean_v", "sat_std", "val_std", "contrast",
    "hue_hist_0", "hue_hist_1", "hue_hist_2", "hue_hist_3",
]


def load_label_pairs(path: str | Path = DEFAULT_PAIRS_PATH) -> list[dict]:
    """pairs.csv({theme, pos, neg} 트리플렛)를 읽어 딕셔너리 리스트로 반환."""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_photo_features(path: str | Path = DEFAULT_PHOTOS_PATH) -> dict[str, np.ndarray]:
    """photos.csv를 photo_id -> 11차원 피처 벡터 딕셔너리로 로딩."""
    features = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            features[row["photo_id"]] = np.array(
                [float(row[field]) for field in FEATURE_FIELDS], dtype=np.float32
            )
    return features


def build_pair_features(
    pairs: list[dict], photo_features: dict[str, np.ndarray] | None = None
) -> tuple[torch.Tensor, torch.Tensor]:
    """트리플렛 목록 -> (feats_pos, feats_neg) 텐서. mlp.rank_forward에 바로 사용 가능.

    photos.csv에 미리 계산된 피처를 photo_id로 조회하기만 해서, 사진을 다시 열거나
    CLIP을 재계산하지 않는다(collect_unsplash_data.py가 이미 다 계산해 둠).
    """
    if photo_features is None:
        photo_features = load_photo_features()

    feats_pos = [photo_features[pair["pos"]] for pair in pairs]
    feats_neg = [photo_features[pair["neg"]] for pair in pairs]

    return torch.from_numpy(np.stack(feats_pos)), torch.from_numpy(np.stack(feats_neg))


if __name__ == "__main__":
    pairs = load_label_pairs()
    feats_pos, feats_neg = build_pair_features(pairs)
    print(f"loaded {len(pairs)} pairs -> feats_pos {tuple(feats_pos.shape)}, feats_neg {tuple(feats_neg.shape)}")
