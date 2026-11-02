"""Ai/evaluate_mlp.py 단위 테스트.

기준값·정확도 계산은 손으로 만든 점수로, 테마별 학습·평가 흐름은 작은 가짜 데이터로,
plot 함수는 tmp_path로 빠르게 검증 (실제 데이터로 끝까지 도는지는 python Ai/evaluate_mlp.py로 확인).
"""

import numpy as np
import pytest
import torch
from torch import nn

from dataset import FEATURE_FIELDS, split_photos
from evaluate_mlp import (
    best_threshold,
    evaluate_theme,
    plot_loss_curve,
    plot_score_distribution,
    plot_theme_summary,
    ranking_accuracy,
    threshold_accuracy,
    val_pass_counts,
)

MONO = "black and white monochrome photography"
VIVID = "vibrant colorful photography"
GOLDEN = "warm golden hour sunset photography"


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


def test_threshold_accuracy_counts_score_at_or_above_threshold_as_theme():
    scores = torch.tensor([0.1, 0.5, 0.7])
    labels = torch.tensor([0, 1, 1])

    assert threshold_accuracy(scores, labels, 0.5) == pytest.approx(1.0)  # 0.5는 기준 이상 -> 테마
    assert threshold_accuracy(scores, labels, 0.6) == pytest.approx(2 / 3)


def test_best_threshold_sits_in_the_middle_of_the_gap_when_separable():
    scores = torch.tensor([0.1, 0.2, 0.8, 0.9])
    labels = torch.tensor([0, 0, 1, 1])

    assert best_threshold(scores, labels) == pytest.approx(0.5)


def test_best_threshold_maximizes_accuracy_when_groups_overlap():
    scores = torch.tensor([0.1, 0.6, 0.4, 0.9, 0.95])
    labels = torch.tensor([0, 0, 1, 1, 1])

    threshold = best_threshold(scores, labels)

    # 어느 기준을 잡아도 0.6(아닌데 높음) 또는 0.4(맞는데 낮음) 중 하나는 틀림 -> 최대 4/5
    assert threshold_accuracy(scores, labels, threshold) == pytest.approx(4 / 5)


def test_evaluate_theme_trains_on_train_photos_and_reports_on_val_photos():
    torch.manual_seed(0)
    by_theme = {t: [f"{t[:1]}{i}" for i in range(4)] for t in (MONO, VIVID, GOLDEN)}
    # 첫 색감 칸을 테마마다 확실히 다르게 둬서, 짧게 학습해도 비비드를 가를 수 있게 함
    level = {MONO: 0.0, VIVID: 1.0, GOLDEN: 0.5}
    features, cross = {}, {}
    for theme, ids in by_theme.items():
        for pid in ids:
            features[pid] = np.array([0.0, level[theme]] + [0.0] * (len(FEATURE_FIELDS) - 2), dtype=np.float32)
            cross[pid] = {t: 0.25 for t in by_theme}
    train, val = split_photos(by_theme, n_val=1, seed=0)

    result = evaluate_theme(VIVID, train, val, features, cross, epochs=200)

    assert result["n_train_pairs"] == 3 * 6  # 비비드 학습 3장 x 다른 테마 학습 6장
    assert result["val_labels"].tolist() == [0, 1, 0]  # 검증 사진: 흑백 1, 비비드 1, 골든아워 1
    assert result["ranking_accuracy"] == pytest.approx(1.0)
    assert result["threshold_accuracy"] == pytest.approx(1.0)
    assert np.isfinite(result["threshold"])


def test_plot_loss_curve_writes_a_png_file(tmp_path):
    path = tmp_path / "loss_curve.png"

    plot_loss_curve([1.0, 0.5, 0.1], path)

    assert path.exists()


def test_plot_score_distribution_writes_a_png_file(tmp_path):
    path = tmp_path / "score_distribution.png"

    plot_score_distribution(torch.tensor([0.1, 0.2]), torch.tensor([0.05, 0.15]), path, threshold=0.12)

    assert path.exists()


class _FirstColorModel(nn.Module):
    """점수 = 첫 색감 칸 값 (통과 개수 계산 로직만 검증하기 위한 결정적 스텁 모델)."""

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x[:, 1:2]


def test_val_pass_counts_counts_photos_at_or_above_threshold_per_theme():
    level = {MONO: 0.0, VIVID: 1.0, GOLDEN: 0.5}
    val_by_theme = {t: [f"{t[:1]}{i}" for i in range(2)] for t in level}
    features = {
        pid: np.array([0.0, level[t]] + [0.0] * (len(FEATURE_FIELDS) - 2), dtype=np.float32)
        for t, ids in val_by_theme.items()
        for pid in ids
    }
    cross = {pid: {t: 0.25 for t in level} for pid in features}

    counts = val_pass_counts(_FirstColorModel(), VIVID, 0.5, val_by_theme, features, cross)

    assert counts == {MONO: (0, 2), VIVID: (2, 2), GOLDEN: (2, 2)}  # 0.5는 기준 이상이라 골든아워도 통과


def test_plot_theme_summary_writes_a_png_file(tmp_path):
    path = tmp_path / "theme_summary.png"
    summaries = {
        key: {
            "loss_history": [0.2, 0.1, 0.0],
            "ranking_accuracy": 0.9,
            "threshold_accuracy": 0.95,
            "pass_counts": {MONO: (1, 6), VIVID: (6, 6), GOLDEN: (0, 6)},
        }
        for key in ("mono", "vivid", "golden")
    }

    plot_theme_summary(summaries, path)

    assert path.exists()
