"""ScoringMLP용 고정 테마 트리플렛(scoring_pairs.csv) + TransitionCostModel용 페어와이즈
데이터(photos.csv) 로딩 (학습 입력 준비).

흐름(ScoringMLP): Ai/data/unsplash/scoring_pairs.csv({theme, pos, neg}, 테마 하나 고정) +
      scoring_photos.csv(photo_id -> 11차원 피처) -> photo_id로 피처 조회
      -> (feats_pos, feats_neg) 텐서 쌍
흐름(TransitionCostModel): Ai/data/unsplash/photos.csv(사진별 테마 + 피처)
      -> 같은/다른 테마 페어 샘플링 -> (feat_pos_a, feat_pos_b, feat_neg_a, feat_neg_b)

두 모델이 서로 다른 데이터를 쓰는 이유는 docs/ai/Transition_cost_model.md,
docs/ai/Mlp_scoring.md 참고 — ScoringMLP는 테마 하나 고정 기준 절대 점수용이라
회전식 다중 테마 데이터(photos.csv/pairs.csv)를 그대로 쓸 수 없다.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

import numpy as np
import torch

DEFAULT_PAIRS_PATH = Path(__file__).resolve().parent / "data" / "unsplash" / "scoring_pairs.csv"
DEFAULT_SCORING_PHOTOS_PATH = Path(__file__).resolve().parent / "data" / "unsplash" / "scoring_photos.csv"
DEFAULT_PHOTOS_PATH = Path(__file__).resolve().parent / "data" / "unsplash" / "photos.csv"

# collect_unsplash_data.py의 FEATURE_FIELDS와 동일한 순서 — photos.csv 컬럼이 이 순서로 저장돼 있음
FEATURE_FIELDS = [
    "clip_sim", "mean_h", "mean_s", "mean_v", "sat_std", "val_std", "contrast",
    "hue_hist_0", "hue_hist_1", "hue_hist_2", "hue_hist_3",
]


def load_label_pairs(path: str | Path = DEFAULT_PAIRS_PATH) -> list[dict]:
    """scoring_pairs.csv({theme, pos, neg} 트리플렛, 테마 하나 고정)를 읽어 딕셔너리 리스트로 반환."""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_photo_features(path: str | Path = DEFAULT_SCORING_PHOTOS_PATH) -> dict[str, np.ndarray]:
    """scoring_photos.csv를 photo_id -> 11차원 피처 벡터 딕셔너리로 로딩."""
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


def load_photo_pool(path: str | Path = DEFAULT_PHOTOS_PATH) -> tuple[dict[str, np.ndarray], dict[str, list[str]]]:
    """photos.csv -> (photo_id -> 11차원 피처, 테마 -> 그 테마 photo_id 리스트).

    transition_cost_model.py의 페어와이즈 샘플링(같은 테마 2장/다른 테마 2장)에 필요한
    테마별 그룹 정보까지 한 번에 읽어둔다.
    """
    features: dict[str, np.ndarray] = {}
    by_theme: dict[str, list[str]] = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            features[row["photo_id"]] = np.array(
                [float(row[field]) for field in FEATURE_FIELDS], dtype=np.float32
            )
            by_theme.setdefault(row["query"], []).append(row["photo_id"])
    return features, by_theme


def sample_theme_pair_features(
    features: dict[str, np.ndarray],
    by_theme: dict[str, list[str]],
    n_pairs: int,
    rng: random.Random,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """같은 테마 2장(pos_pair)/다른 테마 2장(neg_pair)을 n_pairs개씩 무작위 샘플링.

    pos_pair는 같은 테마라 어울려야(낮은 비용), neg_pair는 다른 테마라 안 어울려야(높은 비용)
    한다 — transition_cost_model.train()에 바로 넣을 수 있는 4개 텐서로 반환.
    """
    themes = list(by_theme.keys())
    pos_a, pos_b, neg_a, neg_b = [], [], [], []
    for _ in range(n_pairs):
        theme = rng.choice(themes)
        a_id, b_id = rng.sample(by_theme[theme], 2)
        pos_a.append(features[a_id])
        pos_b.append(features[b_id])

        theme_x, theme_y = rng.sample(themes, 2)
        neg_a.append(features[rng.choice(by_theme[theme_x])])
        neg_b.append(features[rng.choice(by_theme[theme_y])])

    return (
        torch.from_numpy(np.stack(pos_a)),
        torch.from_numpy(np.stack(pos_b)),
        torch.from_numpy(np.stack(neg_a)),
        torch.from_numpy(np.stack(neg_b)),
    )


if __name__ == "__main__":
    pairs = load_label_pairs()
    feats_pos, feats_neg = build_pair_features(pairs)
    print(f"loaded {len(pairs)} pairs -> feats_pos {tuple(feats_pos.shape)}, feats_neg {tuple(feats_neg.shape)}")
