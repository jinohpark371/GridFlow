"""Ai/arrange_photos.py 정렬 알고리즘 단위 테스트.

색감 피처는 실제 사진 없이 무작위 벡터로 구성. TransitionCostModel은 학습 전
랜덤 초기화 상태로 사용(구조/로직 검증 목적 — 실제 학습된 체크포인트로 끝까지
도는지는 tests/backend/test_main.py에서 end-to-end로 확인).
"""

import functools

import numpy as np
import pytest
from mlp import INPUT_DIM
from transition_cost_model import TransitionCostModel

from arrange_photos import (
    _brute_force_order,
    _total_cost,
    _two_opt,
    arrange_photos,
    model_cost_fn,
    order_items,
    select_representative,
)


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


def test_two_opt_can_reverse_a_suffix_that_touches_the_last_index():
    """최종 리뷰에서 발견된 버그: 내부 루프의 j가 len(order)-1까지만 가서, 마지막 인덱스를
    포함하는 구간 반전이 한 번도 시도되지 않았다. 이 케이스는 그 반전(order[i:len(order)])
    이 있어야만 최적에 도달하는 상황을 고정해서 재현한다 — 값 [0,1,11,10]에서 시작 순서
    [0,1,2,3](비용 12)의 유일한 개선 수는 i=2,j=4 구간 반전([0,1,3,2], 비용 11)인데,
    버그가 있으면 j가 4에 못 미쳐 이 수를 찾지 못하고 그대로 멈춘다."""

    def cost_fn(a: np.ndarray, b: np.ndarray) -> float:
        return abs(float(a[0]) - float(b[0]))

    feats = [np.array([v] + [0.0] * (INPUT_DIM - 1), dtype=np.float32) for v in [0.0, 1.0, 11.0, 10.0]]
    start_order = [0, 1, 2, 3]

    result = _two_opt(start_order, feats, cost_fn)

    assert _total_cost(result, feats, cost_fn) == pytest.approx(11.0)


def test_two_opt_matches_brute_force_optimal_cost_for_small_cases():
    """위 케이스 하나로는 우연일 수 있으니, 여러 작은 케이스에서 2-opt 결과 비용이
    완전탐색(브루트포스) 최적 비용과 같은지 폭넓게 확인한다."""

    def cost_fn(a: np.ndarray, b: np.ndarray) -> float:
        return abs(float(a[0]) - float(b[0]))

    trials = [
        [0.0, 5.0, 1.0, 6.0, 2.0, 7.0],
        [3.0, 9.0, 0.0, 4.0, 8.0, 1.0],
        [10.0, 1.0, 9.0, 2.0, 8.0, 3.0],
    ]
    for values in trials:
        feats = [np.array([v] + [0.0] * (INPUT_DIM - 1), dtype=np.float32) for v in values]
        n = len(feats)

        optimal_order = _brute_force_order(n, feats, cost_fn)
        two_opt_order = _two_opt(list(range(n)), feats, cost_fn)

        optimal_cost = _total_cost(optimal_order, feats, cost_fn)
        two_opt_cost = _total_cost(two_opt_order, feats, cost_fn)

        assert two_opt_cost == pytest.approx(optimal_cost)


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
