"""MLP 테마 적합도 스코어링 (흐름도 > MLP 모델 설계).

이 MLP는 순서를 직접 정하지 않는다. "이 사진이 이 테마에 얼마나 맞는가"를 판단해
①부적합 사진 제외를 제안하고 ②유지 사진에 점수(가중치)를 부여하는 역할이며,
실제 순서는 전이 비용 최소화 배치 단계에서 결정된다.

입력 피처(11d) = CLIP 유사도(1, clip.py) + 색감 피처(10, features.py)
Siamese 구조: 하나의 ScoringMLP를 두 사진에 동일 가중치로 적용해 pairwise ranking으로 학습한다.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image

from clip import cosine_similarity, get_image_embedding, get_text_embedding
from features import COLOR_FEATURE_DIM, extract_color_features

INPUT_DIM = 1 + COLOR_FEATURE_DIM  # CLIP 유사도 1 + 색감 피처 10 = 11d


class ScoringMLP(nn.Module):
    """사진 하나 -> 테마 적합도 점수 하나 (절대 점수가 아니라 상대 비교용)."""

    def __init__(self, input_dim: int = INPUT_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)  # (batch, 1)


def build_feature_vector(image: Image.Image | str | Path, theme_text: str) -> np.ndarray:
    """사진 + 테마 문장 -> 11d 입력 피처 (CLIP 유사도 1 + 색감 피처 10)."""
    image_vec = get_image_embedding(image)
    theme_vec = get_text_embedding(theme_text)
    clip_score = cosine_similarity(image_vec, theme_vec)
    color_feats = extract_color_features(image)
    return np.concatenate([[clip_score], color_feats]).astype(np.float32)


def rank_forward(
    model: ScoringMLP, feat_a: torch.Tensor, feat_b: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    """동일 가중치의 모델을 두 사진(쌍)에 각각 적용 (Siamese)."""
    score_a = model(feat_a)  # 테마에 더 잘 맞는 사진 (pos)
    score_b = model(feat_b)  # 덜 맞는 사진 (neg)
    return score_a, score_b


def margin_ranking_loss(
    score_pos: torch.Tensor, score_neg: torch.Tensor, margin: float = 0.2
) -> torch.Tensor:
    """(a) Margin Ranking Loss — 직관적, 구현 간단 (초기 권장)."""
    return torch.clamp(margin - (score_pos - score_neg), min=0).mean()


def ranknet_loss(score_pos: torch.Tensor, score_neg: torch.Tensor) -> torch.Tensor:
    """(b) RankNet Loss — 확률적, gradient 안정적 (안정화 후 전환)."""
    diff = score_pos - score_neg
    return -torch.log(torch.sigmoid(diff)).mean()


def _inference_scores(model: ScoringMLP, feats: torch.Tensor) -> torch.Tensor:
    """Dropout 등 학습 전용 레이어를 끄고(eval) 결정적으로 점수를 계산한 뒤 이전 모드로 복원."""
    was_training = model.training
    model.eval()
    try:
        with torch.no_grad():
            return model(feats).squeeze(-1)
    finally:
        model.train(was_training)


def filter_by_fitness(
    model: ScoringMLP, feats: torch.Tensor, threshold: float = 0.35
) -> tuple[list[int], torch.Tensor]:
    """적합도 점수만 계산해 threshold 이상 인덱스를 반환. 순서(argsort)는 여기서 정하지 않는다."""
    scores = _inference_scores(model, feats)
    keep = [i for i, s in enumerate(scores) if s >= threshold]
    return keep, scores


def suggest_removal(
    model: ScoringMLP,
    feats: torch.Tensor,
    photo_ids: list[str],
    threshold: float = 0.35,
) -> tuple[list[str], list[tuple[str, float]]]:
    """테마 부적합 사진의 제외를 '제안'만 한다 — 자동 삭제 아님, 최종 결정은 사용자."""
    scores = _inference_scores(model, feats)

    keep: list[str] = []
    remove_candidates: list[tuple[str, float]] = []
    for pid, s in zip(photo_ids, scores):
        if s < threshold:
            remove_candidates.append((pid, float(s)))
        else:
            keep.append(pid)
    return keep, remove_candidates


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("usage: python mlp.py <image_path> <theme_text>")
        raise SystemExit(1)

    feats = build_feature_vector(sys.argv[1], sys.argv[2])
    print(f"feature_vector({len(feats)}d): {feats}")

    # 학습 전 랜덤 가중치이므로 점수 자체는 의미 없음 — 피처 파이프라인과 forward shape만 검증
    model = ScoringMLP()
    score = model(torch.from_numpy(feats).unsqueeze(0))
    print(f"raw score (untrained): {score.item():.4f}")
