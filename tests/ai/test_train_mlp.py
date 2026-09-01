"""Ai/train_mlp.py 학습 루프 단위 테스트.

무작위 텐서로만 검증해 CLIP 없이 빠르게 실행됨
(실제 라벨 데이터로 끝까지 도는지는 python Ai/train_mlp.py로 수동 확인).
"""

import torch
from mlp import INPUT_DIM, ScoringMLP
from train_mlp import train


def test_train_returns_a_scoring_mlp_and_full_loss_history():
    feats_pos = torch.randn(4, INPUT_DIM)
    feats_neg = torch.randn(4, INPUT_DIM)

    model, loss_history = train(feats_pos, feats_neg, epochs=5)

    assert isinstance(model, ScoringMLP)
    assert len(loss_history) == 5


def test_train_converges_close_to_zero_on_a_fixed_batch():
    """같은 배치를 충분히 반복 학습하면(풀배치 gradient descent) margin_ranking_loss가
    0에 가깝게 수렴해야 한다 — 학습 루프가 실제로 최적화 목표에 도달하는지 확인.
    """
    torch.manual_seed(0)
    feats_pos = torch.randn(6, INPUT_DIM)
    feats_neg = torch.randn(6, INPUT_DIM)

    _, loss_history = train(feats_pos, feats_neg, epochs=300)

    assert loss_history[-1] < loss_history[0]
    assert loss_history[-1] < 0.01
