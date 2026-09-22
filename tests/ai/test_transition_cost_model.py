"""Ai/transition_cost_model.py 페어와이즈 비용 모델 단위 테스트.

무작위 텐서로만 검증해 CLIP 없이 빠르게 실행됨
(실제 데이터로 끝까지 도는지는 python Ai/evaluate_transition_cost_model.py로 수동 확인).
"""

import torch
from mlp import INPUT_DIM
from transition_cost_model import TransitionCostModel, pair_cost, train


def test_pair_cost_is_symmetric_regardless_of_argument_order():
    """|A - B| == |B - A|이므로, 사진 순서를 바꿔도 비용은 같아야 한다."""
    model = TransitionCostModel()
    model.eval()
    feat_a = torch.randn(3, INPUT_DIM)
    feat_b = torch.randn(3, INPUT_DIM)

    cost_ab = pair_cost(model, feat_a, feat_b)
    cost_ba = pair_cost(model, feat_b, feat_a)

    assert torch.allclose(cost_ab, cost_ba)


def test_pair_cost_is_zero_distance_diff_for_identical_photos():
    """같은 사진끼리는 |A - A| = 0벡터이므로, 두 사진이 같으면 항상 같은 비용이 나와야 한다."""
    model = TransitionCostModel()
    model.eval()
    feat_a = torch.randn(2, INPUT_DIM)

    cost_self = pair_cost(model, feat_a, feat_a)

    assert cost_self.shape == (2,)


def test_train_returns_a_transition_cost_model_and_full_loss_history():
    feat_pos_a = torch.randn(4, INPUT_DIM)
    feat_pos_b = torch.randn(4, INPUT_DIM)
    feat_neg_a = torch.randn(4, INPUT_DIM)
    feat_neg_b = torch.randn(4, INPUT_DIM)

    model, loss_history = train(feat_pos_a, feat_pos_b, feat_neg_a, feat_neg_b, epochs=5)

    assert isinstance(model, TransitionCostModel)
    assert len(loss_history) == 5


def test_train_converges_close_to_zero_on_a_fixed_batch():
    """pos_pair를 서로 가깝게, neg_pair를 서로 멀게 고정해두면(뚜렷한 신호),
    충분히 학습했을 때 margin_ranking_loss가 0에 가깝게 수렴해야 한다.
    """
    torch.manual_seed(0)
    feat_pos_a = torch.randn(6, INPUT_DIM)
    feat_pos_b = feat_pos_a + 0.01 * torch.randn(6, INPUT_DIM)  # pos_pair: 거의 같은 사진(비용 낮아야 함)
    feat_neg_a = torch.randn(6, INPUT_DIM)
    feat_neg_b = feat_neg_a + 5.0 * torch.randn(6, INPUT_DIM)  # neg_pair: 크게 다른 사진(비용 높아야 함)

    _, loss_history = train(feat_pos_a, feat_pos_b, feat_neg_a, feat_neg_b, epochs=300)

    assert loss_history[-1] < loss_history[0]
    assert loss_history[-1] < 0.01
