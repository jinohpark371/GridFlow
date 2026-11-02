"""ScoringMLP용 테마별 학습 데이터 + TransitionCostModel용 페어와이즈 데이터 로딩 (학습 입력 준비).

흐름(ScoringMLP): photos.csv(사진별 수집 테마 + 11차원 피처) + cross_clip_sim.csv(사진 x 테마 문장
      clip_sim) -> split_photos로 테마별 학습/검증 사진 분할 -> 테마 하나 기준으로 clip_sim만
      그 테마 문장 값으로 바꿔 (이 테마 사진 x 다른 테마 사진) 쌍 -> (feats_pos, feats_neg)
흐름(TransitionCostModel): Ai/data/unsplash/photos.csv(사진별 테마 + 피처)
      -> 같은/다른 테마 페어 샘플링 -> (feat_pos_a, feat_pos_b, feat_neg_a, feat_neg_b)

ScoringMLP는 테마마다 모델을 따로 학습한다 — 한 모델을 흑백 데이터로만 학습했더니 테마와
상관없이 "채도가 낮을수록 높은 점수"만 배웠기 때문(docs/ai/Mlp_scoring.md, 이슈 #23 참고).
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

import numpy as np
import torch

DEFAULT_PHOTOS_PATH = Path(__file__).resolve().parent / "data" / "unsplash" / "photos.csv"

# collect_unsplash_data.py의 FEATURE_FIELDS와 동일한 순서 — photos.csv 컬럼이 이 순서로 저장돼 있음
FEATURE_FIELDS = [
    "clip_sim", "mean_h", "mean_s", "mean_v", "sat_std", "val_std", "contrast",
    "hue_hist_0", "hue_hist_1", "hue_hist_2", "hue_hist_3",
]


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


DEFAULT_CROSS_CLIP_PATH = Path(__file__).resolve().parent / "data" / "unsplash" / "cross_clip_sim.csv"
N_VAL_PHOTOS_PER_THEME = 6
SPLIT_SEED = 42


def load_cross_clip_sim(path: str | Path = DEFAULT_CROSS_CLIP_PATH) -> dict[str, dict[str, float]]:
    """cross_clip_sim.csv -> photo_id -> {테마 문장: 그 문장 기준 clip_sim}."""
    from mlp import THEME_KEYS

    cross: dict[str, dict[str, float]] = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cross[row["photo_id"]] = {theme: float(row[f"clip_{key}"]) for theme, key in THEME_KEYS.items()}
    return cross


def split_photos(
    by_theme: dict[str, list[str]], n_val: int = N_VAL_PHOTOS_PER_THEME, seed: int = SPLIT_SEED
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """테마별 사진을 섞은 뒤 n_val장은 검증, 나머지는 학습으로 고정 분할.

    쌍이 아니라 사진 단위로 나눠야, 검증 사진이 학습 쌍에 한 번도 등장하지 않아
    "처음 보는 사진도 맞히는지"를 잴 수 있다. photos.csv 순서는 Unsplash 검색 순위라
    뒤쪽만 떼면 검증이 덜 대표적인 사진으로 쏠려서 seed로 섞는다.
    """
    rng = random.Random(seed)
    train, val = {}, {}
    for theme, ids in by_theme.items():
        shuffled = ids[:]
        rng.shuffle(shuffled)
        val[theme] = shuffled[:n_val]
        train[theme] = shuffled[n_val:]
    return train, val


def theme_feature(
    photo_id: str, theme_text: str, features: dict[str, np.ndarray], cross: dict[str, dict[str, float]]
) -> np.ndarray:
    """photos.csv의 11d(clip_sim은 수집 테마 기준) -> clip_sim만 theme_text 기준 값으로 바꾼 11d."""
    feat = features[photo_id].copy()
    feat[0] = cross[photo_id][theme_text]
    return feat


def build_theme_pairs(
    theme_text: str,
    by_theme: dict[str, list[str]],
    features: dict[str, np.ndarray],
    cross: dict[str, dict[str, float]],
) -> tuple[torch.Tensor, torch.Tensor]:
    """테마 하나 기준 (이 테마 사진 x 다른 테마 사진) 모든 조합 -> (feats_pos, feats_neg)."""
    pos_ids = by_theme[theme_text]
    neg_ids = [pid for theme, ids in by_theme.items() if theme != theme_text for pid in ids]
    pos = [theme_feature(p, theme_text, features, cross) for p in pos_ids for _ in neg_ids]
    neg = [theme_feature(n, theme_text, features, cross) for _ in pos_ids for n in neg_ids]
    return torch.from_numpy(np.stack(pos)), torch.from_numpy(np.stack(neg))


def build_theme_labeled(
    theme_text: str,
    by_theme: dict[str, list[str]],
    features: dict[str, np.ndarray],
    cross: dict[str, dict[str, float]],
) -> tuple[torch.Tensor, torch.Tensor]:
    """테마 하나 기준 사진별 11d + 정답(이 테마 사진 1, 나머지 0) — 기준값 계산·검증용."""
    feats, labels = [], []
    for theme, ids in by_theme.items():
        for pid in ids:
            feats.append(theme_feature(pid, theme_text, features, cross))
            labels.append(1 if theme == theme_text else 0)
    return torch.from_numpy(np.stack(feats)), torch.tensor(labels)


if __name__ == "__main__":
    features, by_theme = load_photo_pool()
    cross = load_cross_clip_sim()
    train_by_theme, val_by_theme = split_photos(by_theme)
    for theme_text, ids in train_by_theme.items():
        feats_pos, feats_neg = build_theme_pairs(theme_text, train_by_theme, features, cross)
        print(f"{theme_text}: 학습 {len(ids)}장 / 검증 {len(val_by_theme[theme_text])}장 -> 학습 쌍 {tuple(feats_pos.shape)}")
