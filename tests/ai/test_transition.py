"""Ai/transition.py 전이 비용 배치 파이프라인 단위 테스트.

색감 피처는 실제 사진 없이 features.py 출력 레이아웃(10d, [hue, sat, val, ...])에 맞춘
무작위/수기 벡터로 구성해 빠르게 실행됨.
"""

import numpy as np
from features import COLOR_FEATURE_DIM
from transition import (
    arrange_photos,
    order_items,
    select_representative,
    transition_cost,
)


def _feat(hue: float = 0.0, sat: float = 0.0, val: float = 0.0) -> np.ndarray:
    feat = np.zeros(COLOR_FEATURE_DIM, dtype=np.float32)
    feat[0], feat[1], feat[2] = hue, sat, val
    return feat


def test_transition_cost_only_uses_hue_saturation_brightness():
    fi = _feat(hue=0.2, sat=0.3, val=0.4)
    fj = _feat(hue=0.2, sat=0.3, val=0.4)
    fi[-1], fj[-1] = 0.0, 1.0  # hue_hist 등 나머지 성분은 비용에 영향을 주면 안 됨

    assert transition_cost(fi, fj) == 0.0


def test_transition_cost_applies_weights_per_component():
    fi, fj = _feat(hue=0.0, sat=0.0, val=0.0), _feat(hue=0.5, sat=0.0, val=0.0)

    assert transition_cost(fi, fj, w1=2.0, w2=0.0, w3=0.0) == 1.0
    assert transition_cost(fi, fj, w1=0.0, w2=0.0, w3=0.0) == 0.0


def test_order_items_brute_force_beats_identity_order_when_shuffled():
    feats = [_feat(hue=h) for h in [0.9, 0.0, 0.3, 0.6]]

    order = order_items(feats, transition_cost, brute_force_max=8)

    ordered_cost = sum(transition_cost(feats[order[i]], feats[order[i + 1]]) for i in range(3))
    identity_cost = sum(transition_cost(feats[i], feats[i + 1]) for i in range(3))
    assert ordered_cost <= identity_cost
    assert sorted(order) == [0, 1, 2, 3]


def test_order_items_greedy_two_opt_path_returns_valid_permutation_above_threshold():
    rng = np.random.default_rng(0)
    feats = [_feat(hue=float(h)) for h in rng.random(9)]

    order = order_items(feats, transition_cost, brute_force_max=8)

    assert sorted(order) == list(range(9))


def test_select_representative_picks_highest_fitness_photo():
    group = ["p1", "p2", "p3"]
    fitness_scores = {"p1": 0.1, "p2": 0.9, "p3": 0.5}

    assert select_representative(group, fitness_scores) == "p2"


def test_arrange_photos_returns_every_photo_exactly_once_with_matching_adjacency():
    groups = [["a1", "a2", "a3"], ["b1", "b2"]]
    rng = np.random.default_rng(1)
    color_feats = {pid: _feat(hue=float(h)) for pid, h in zip(["a1", "a2", "a3", "b1", "b2"], rng.random(5))}
    fitness_scores = {pid: float(s) for pid, s in zip(color_feats, rng.random(5))}

    order, adjacency = arrange_photos(groups, color_feats, fitness_scores)

    assert sorted(order) == sorted(color_feats)
    assert len(adjacency) == len(order) - 1
    assert [a for a, _, _ in adjacency] == order[:-1]
    assert [b for _, b, _ in adjacency] == order[1:]


def test_boundary_optimization_reverses_group_to_minimize_join_cost():
    """그룹 내부 총 비용은 방향과 무관(대칭)하므로, 경계 비용이 낮은 방향을 골라야 한다.

    group1의 내부 순서는 완전탐색에서 [g1p0, g1p1] (hue 0.9 -> 0.1)로 확정되지만,
    group0(hue 0.0) 바로 뒤에 이어 붙일 때는 뒤집어서 [g1p1, g1p0]로 놓는 쪽이
    경계 비용(|0.0-0.1|=0.1)이 뒤집지 않는 쪽(|0.0-0.9|=0.9)보다 훨씬 낮다.
    """
    groups = [["g0p0"], ["g1p0", "g1p1"]]
    color_feats = {
        "g0p0": _feat(hue=0.0),
        "g1p0": _feat(hue=0.9),
        "g1p1": _feat(hue=0.1),
    }
    fitness_scores = {"g0p0": 1.0, "g1p0": 1.0, "g1p1": 0.0}

    order, _ = arrange_photos(groups, color_feats, fitness_scores)

    assert order == ["g0p0", "g1p1", "g1p0"]
