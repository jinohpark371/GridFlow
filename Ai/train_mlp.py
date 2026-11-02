"""ScoringMLP 학습 스크립트 (rank_forward + margin_ranking_loss).

흐름: photos.csv + cross_clip_sim.csv -> dataset.build_theme_pairs(테마 하나 기준 쌍)
      -> ScoringMLP를 pairwise ranking loss로 학습 (테마마다 모델 하나, 검증·저장은 evaluate_mlp.py)
"""

from __future__ import annotations

import torch

from dataset import build_theme_pairs, load_cross_clip_sim, load_photo_pool
from mlp import THEME_KEYS, ScoringMLP, margin_ranking_loss, rank_forward

DEFAULT_EPOCHS = 100
DEFAULT_LR = 1e-3


def train(
    feats_pos: torch.Tensor,
    feats_neg: torch.Tensor,
    epochs: int = DEFAULT_EPOCHS,
    lr: float = DEFAULT_LR,
) -> tuple[ScoringMLP, list[float]]:
    """pos/neg 피처 배치로 ScoringMLP를 pairwise ranking loss로 학습.

    데이터가 소량이라 매 epoch 전체 쌍을 그대로 다시 통과시키는 풀배치 학습.
    """
    model = ScoringMLP()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    loss_history = []
    for _ in range(epochs):
        optimizer.zero_grad()
        score_pos, score_neg = rank_forward(model, feats_pos, feats_neg)
        loss = margin_ranking_loss(score_pos, score_neg)
        loss.backward()
        optimizer.step()
        loss_history.append(loss.item())

    return model, loss_history


if __name__ == "__main__":
    features, by_theme = load_photo_pool()
    cross = load_cross_clip_sim()

    for theme_text, key in THEME_KEYS.items():
        feats_pos, feats_neg = build_theme_pairs(theme_text, by_theme, features, cross)
        model, loss_history = train(feats_pos, feats_neg)
        print(f"[{key}] trained on {len(feats_pos)} pairs for {DEFAULT_EPOCHS} epochs")
        print(f"[{key}] loss: {loss_history[0]:.4f} -> {loss_history[-1]:.4f}")
