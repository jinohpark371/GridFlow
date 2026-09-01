"""Ai/evaluate_mlp.py 단위 테스트.

split_pairs/ranking_accuracy는 무작위 텐서로, plot 함수는 tmp_path로 빠르게 검증
(실제 라벨 데이터로 끝까지 도는지는 python Ai/evaluate_mlp.py로 수동 확인).
"""

import pytest
import torch
from torch import nn

from evaluate_mlp import N_VAL, plot_loss_curve, plot_score_distribution, ranking_accuracy, split_pairs


def test_split_pairs_default_keeps_9_train_3_val():
    pairs = [{"theme": "t", "pos": f"p{i}", "neg": f"n{i}"} for i in range(12)]

    train_pairs, val_pairs = split_pairs(pairs)

    assert len(train_pairs) == 12 - N_VAL
    assert len(val_pairs) == N_VAL
    assert train_pairs == pairs[: 12 - N_VAL]
    assert val_pairs == pairs[12 - N_VAL :]


class _SumModel(nn.Module):
    """점수 = 입력 피처 합 (ranking_accuracy 계산 로직만 검증하기 위한 결정적 스텁 모델)."""

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x.sum(dim=1, keepdim=True)


def test_ranking_accuracy_counts_fraction_where_pos_beats_neg():
    model = _SumModel()
    feats_pos = torch.tensor([[1.0, 1.0], [0.0, 0.0], [5.0, 5.0]])
    feats_neg = torch.tensor([[0.0, 0.0], [1.0, 1.0], [0.0, 0.0]])
    # pos 합: 2, 0, 10 / neg 합: 0, 2, 0 -> pos > neg인 쌍은 0번, 2번 -> 2/3

    acc = ranking_accuracy(model, feats_pos, feats_neg)

    assert acc == pytest.approx(2 / 3)


def test_plot_loss_curve_writes_a_png_file(tmp_path):
    path = tmp_path / "loss_curve.png"

    plot_loss_curve([1.0, 0.5, 0.1], path)

    assert path.exists()


def test_plot_score_distribution_writes_a_png_file(tmp_path):
    path = tmp_path / "score_distribution.png"

    plot_score_distribution(torch.tensor([0.1, 0.2]), torch.tensor([0.05, 0.15]), path)

    assert path.exists()
