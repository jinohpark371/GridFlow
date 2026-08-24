"""Ai/mlp.py MLP 테마 적합도 스코어링 단위 테스트.

CLIP 모델을 로딩하지 않고 무작위 텐서로만 검증해 빠르게 실행됨
(CLIP까지 엮은 build_feature_vector 검증은 tests/ai/test_clip_integration.py 참고).
"""

import torch
from mlp import (
    INPUT_DIM,
    ScoringMLP,
    filter_by_fitness,
    margin_ranking_loss,
    rank_forward,
    ranknet_loss,
    suggest_removal,
)


def test_scoring_mlp_outputs_one_score_per_photo():
    model = ScoringMLP()
    x = torch.randn(4, INPUT_DIM)
    out = model(x)
    assert out.shape == (4, 1)


def test_rank_forward_shares_weights_between_the_two_photos():
    """Siamese 검증: 같은 가중치를 통과하므로 같은 입력이면 두 점수가 같아야 한다."""
    model = ScoringMLP()
    model.eval()
    feat = torch.randn(1, INPUT_DIM)

    score_a, score_b = rank_forward(model, feat, feat)

    assert torch.allclose(score_a, score_b)


def test_margin_ranking_loss_is_zero_once_margin_is_satisfied():
    score_pos = torch.tensor([[1.0]])
    score_neg = torch.tensor([[0.0]])
    assert margin_ranking_loss(score_pos, score_neg, margin=0.2).item() == 0.0


def test_margin_ranking_loss_is_positive_when_order_is_reversed():
    score_pos = torch.tensor([[0.0]])
    score_neg = torch.tensor([[1.0]])
    assert margin_ranking_loss(score_pos, score_neg, margin=0.2).item() > 0.0


def test_ranknet_loss_prefers_correct_pairwise_order():
    score_pos = torch.tensor([[2.0]])
    score_neg = torch.tensor([[0.0]])

    loss_correct_order = ranknet_loss(score_pos, score_neg)
    loss_wrong_order = ranknet_loss(score_neg, score_pos)

    assert loss_correct_order.item() < loss_wrong_order.item()


def test_filter_by_fitness_keeps_indices_at_or_above_threshold():
    model = ScoringMLP()
    model.eval()
    feats = torch.randn(5, INPUT_DIM)
    with torch.no_grad():
        raw_scores = model(feats).squeeze(-1)
    threshold = raw_scores.median().item()

    keep, scores = filter_by_fitness(model, feats, threshold=threshold)

    assert torch.equal(scores, raw_scores)
    assert keep == [i for i, s in enumerate(raw_scores) if s >= threshold]


def test_suggest_removal_partitions_all_photo_ids_into_keep_or_remove():
    model = ScoringMLP()
    feats = torch.randn(3, INPUT_DIM)
    photo_ids = ["p1", "p2", "p3"]

    keep_ids, remove_candidates = suggest_removal(model, feats, photo_ids, threshold=0.0)
    removed_ids = {pid for pid, _ in remove_candidates}

    assert set(keep_ids) | removed_ids == set(photo_ids)
    assert not (set(keep_ids) & removed_ids)


def test_inference_helpers_are_deterministic_even_when_model_is_in_train_mode():
    """회귀 테스트.

    최초 구현에서는 filter_by_fitness/suggest_removal이 torch.no_grad()만 쓰고
    model.eval()을 호출하지 않아, model이 train 모드일 때 Dropout이 추론 중에도
    활성 상태로 남아 동일 입력에 대해 호출마다 점수가 달라지는 문제가 있었다
    (docs/ai/Mlp_scoring.md 참고).
    """
    model = ScoringMLP()
    model.train()
    feats = torch.randn(3, INPUT_DIM)

    _, scores_first_call = filter_by_fitness(model, feats, threshold=0.0)
    _, scores_second_call = filter_by_fitness(model, feats, threshold=0.0)

    assert torch.equal(scores_first_call, scores_second_call)
    assert model.training is True  # 호출 전 모드로 복원돼야 함
