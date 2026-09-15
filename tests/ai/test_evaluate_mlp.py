"""Ai/evaluate_mlp.py 단위 테스트.

split_pairs/ranking_accuracy는 무작위 텐서로, plot 함수는 tmp_path로 빠르게 검증
(실제 라벨 데이터로 끝까지 도는지는 python Ai/evaluate_mlp.py로 수동 확인).
"""

import pytest
import torch
from torch import nn

from evaluate_mlp import N_VAL_PER_THEME, plot_loss_curve, plot_score_distribution, ranking_accuracy, split_pairs


def test_split_pairs_splits_each_theme_separately_not_just_the_last_rows():
    """테마별로 연속해서 묶인 입력이라도, val이 한 테마에만 쏠리지 않고 테마마다 나뉘어야 한다."""
    pairs = [{"theme": "a", "pos": f"pa{i}", "neg": f"na{i}"} for i in range(15)]
    pairs += [{"theme": "b", "pos": f"pb{i}", "neg": f"nb{i}"} for i in range(15)]

    train_pairs, val_pairs = split_pairs(pairs)

    assert len(val_pairs) == 2 * N_VAL_PER_THEME
    assert len(train_pairs) == len(pairs) - 2 * N_VAL_PER_THEME
    assert sum(1 for p in val_pairs if p["theme"] == "a") == N_VAL_PER_THEME
    assert sum(1 for p in val_pairs if p["theme"] == "b") == N_VAL_PER_THEME


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
