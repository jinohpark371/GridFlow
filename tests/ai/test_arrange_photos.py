"""Ai/arrange_photos.py 정렬 알고리즘 단위 테스트.

색감 피처는 실제 사진 없이 무작위 벡터로 구성. TransitionCostModel은 학습 전
랜덤 초기화 상태로 사용(구조/로직 검증 목적 — 실제 학습된 체크포인트로 끝까지
도는지는 tests/backend/test_main.py에서 end-to-end로 확인).
"""

import functools

import numpy as np
from mlp import INPUT_DIM
from transition_cost_model import TransitionCostModel

from arrange_photos import arrange_photos, model_cost_fn, order_items, select_representative


def _feat(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.random(INPUT_DIM).astype(np.float32)


def test_model_cost_fn_is_symmetric():
    model = TransitionCostModel()
    model.eval()
    fi, fj = _feat(0), _feat(1)

    assert model_cost_fn(model, fi, fj) == model_cost_fn(model, fj, fi)


def test_order_items_brute_force_returns_valid_permutation():
    model = TransitionCostModel()
    model.eval()
    cost_fn = functools.partial(model_cost_fn, model)
    feats = [_feat(i) for i in range(4)]

    order = order_items(feats, cost_fn, brute_force_max=8)

    assert sorted(order) == [0, 1, 2, 3]


def test_order_items_greedy_two_opt_returns_valid_permutation_above_threshold():
    model = TransitionCostModel()
    model.eval()
    cost_fn = functools.partial(model_cost_fn, model)
    feats = [_feat(i) for i in range(9)]

    order = order_items(feats, cost_fn, brute_force_max=8)

    assert sorted(order) == list(range(9))


def test_order_items_handles_single_item_group():
    """Review Focus: 그룹에 사진이 1장뿐이면 정렬할 게 없어야 한다."""
    model = TransitionCostModel()
    model.eval()
    cost_fn = functools.partial(model_cost_fn, model)
    feats = [_feat(0)]

    order = order_items(feats, cost_fn, brute_force_max=8)

    assert order == [0]


def test_select_representative_picks_highest_fitness_photo():
    group = ["p1", "p2", "p3"]
    fitness_scores = {"p1": 0.1, "p2": 0.9, "p3": 0.5}

    assert select_representative(group, fitness_scores) == "p2"


def test_arrange_photos_returns_every_photo_once_with_group_internal_adjacency_only():
    model = TransitionCostModel()
    model.eval()
    groups = [["a1", "a2", "a3"], ["b1", "b2"]]
    color_feats = {pid: _feat(i) for i, pid in enumerate(["a1", "a2", "a3", "b1", "b2"])}
    fitness_scores = {pid: float(i) for i, pid in enumerate(color_feats)}

    order, adjacency = arrange_photos(groups, color_feats, fitness_scores, model)
    flat_order = [pid for group in order for pid in group]

    assert len(order) == len(adjacency) == len(groups)
    assert sorted(flat_order) == sorted(color_feats)
    for group_order, group_adjacency in zip(order, adjacency):
        assert len(group_adjacency) == len(group_order) - 1
        assert [a for a, _, _ in group_adjacency] == group_order[:-1]
        assert [b for _, b, _ in group_adjacency] == group_order[1:]


def test_arrange_photos_handles_group_of_size_one():
    """Review Focus: 그룹에 사진이 1장뿐이면 adjacency_costs가 빈 리스트여야 한다."""
    model = TransitionCostModel()
    model.eval()
    groups = [["solo"]]
    color_feats = {"solo": _feat(0)}
    fitness_scores = {"solo": 1.0}

    order, adjacency = arrange_photos(groups, color_feats, fitness_scores, model)

    assert order == [["solo"]]
    assert adjacency == [[]]
