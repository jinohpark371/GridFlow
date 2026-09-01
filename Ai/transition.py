"""전이 비용(transition cost) 기반 사진 배치 (흐름도 > 전이 비용 배치 설계).

흐름: (수동 그룹핑 입력) -> 그룹 내 정렬 -> 그룹 대표 사진 선정 -> 그룹 간 정렬
      -> 그룹 경계 방향(정/역) 조정 -> 최종 순서 + 인접쌍 비용

1단계(고정 가중치 MVP) 범위 — w1=w2=w3=1.0 고정. 가중치 학습(TransitionCostModel, 2단계)은
드래그 재정렬 데이터가 쌓인 뒤 별도 이슈로 다룬다.
"""

from __future__ import annotations

import functools
import itertools
from typing import Callable

import numpy as np

# features.py의 extract_color_features 출력 레이아웃: [mean_h, mean_s, mean_v, sat_std, val_std, contrast, hue_hist(4)]
_HUE_IDX, _SAT_IDX, _VAL_IDX = 0, 1, 2

CostFn = Callable[[np.ndarray, np.ndarray], float]


def transition_cost(fi: np.ndarray, fj: np.ndarray, w1: float = 1.0, w2: float = 1.0, w3: float = 1.0) -> float:
    """색감 피처 벡터 두 개(fi, fj) 사이의 전이 비용. 값이 작을수록 나란히 놓기 자연스럽다."""
    color_diff = abs(fi[_HUE_IDX] - fj[_HUE_IDX])
    bright_diff = abs(fi[_VAL_IDX] - fj[_VAL_IDX])
    sat_diff = abs(fi[_SAT_IDX] - fj[_SAT_IDX])
    return float(w1 * color_diff + w2 * bright_diff + w3 * sat_diff)


def _total_cost(order: list[int], feats: list[np.ndarray], cost_fn: CostFn) -> float:
    return sum(cost_fn(feats[order[i]], feats[order[i + 1]]) for i in range(len(order) - 1))


def _brute_force_order(n: int, feats: list[np.ndarray], cost_fn: CostFn) -> list[int]:
    best_order, best_cost = list(range(n)), float("inf")
    for perm in itertools.permutations(range(n)):
        cost = _total_cost(list(perm), feats, cost_fn)
        if cost < best_cost:
            best_order, best_cost = list(perm), cost
    return best_order


def _nearest_neighbor_order(n: int, feats: list[np.ndarray], cost_fn: CostFn) -> list[int]:
    unvisited = set(range(1, n))
    order = [0]
    while unvisited:
        last = order[-1]
        nxt = min(unvisited, key=lambda j: cost_fn(feats[last], feats[j]))
        order.append(nxt)
        unvisited.discard(nxt)
    return order


def _two_opt(order: list[int], feats: list[np.ndarray], cost_fn: CostFn) -> list[int]:
    improved = True
    while improved:
        improved = False
        # 경로(순환 아님)라 구간 반전이 비용 중립적이지 않음 — 첫 자리(i=0)도 반전 대상에 포함해야 탐색이 안 좁아짐
        for i in range(len(order) - 1):
            for j in range(i + 1, len(order)):
                new_order = order[:i] + order[i:j][::-1] + order[j:]
                if _total_cost(new_order, feats, cost_fn) < _total_cost(order, feats, cost_fn):
                    order = new_order
                    improved = True
    return order


def order_items(feats: list[np.ndarray], cost_fn: CostFn, brute_force_max: int = 8) -> list[int]:
    """전이 비용 총합이 최소가 되는 순서(원본 인덱스 리스트)를 반환.

    사진 수가 적으면(<= brute_force_max) 완전탐색, 많으면 greedy(최근접 이웃) + 2-opt.
    """
    n = len(feats)
    if n <= 1:
        return list(range(n))
    if n <= brute_force_max:
        return _brute_force_order(n, feats, cost_fn)
    return _two_opt(_nearest_neighbor_order(n, feats, cost_fn), feats, cost_fn)


def select_representative(group: list[str], fitness_scores: dict[str, float]) -> str:
    """그룹 내 MLP 적합도(inference_scores)가 가장 높은 사진을 그룹 대표로 선정."""
    return max(group, key=lambda pid: fitness_scores[pid])


def _optimize_boundaries(
    group_orders: list[list[str]], color_feats: dict[str, np.ndarray], cost_fn: CostFn
) -> list[list[str]]:
    """그룹 경계 이음매 미세조정.

    그룹 내부 순서는 이미 확정됐지만, 경로(path)의 총 내부 비용은 인접쌍 절대차의 합이라
    방향을 뒤집어도(정방향/역방향) 값이 동일하다 — 이것이 그룹 내부에 남아있는 배치 자유도다.
    각 그룹을 정방향/역방향 중 어느 쪽으로 놓을지 DP로 골라 인접 그룹 간 경계 비용 합을 최소화한다.
    """
    n = len(group_orders)
    if n <= 1:
        return group_orders

    inf = float("inf")
    # dp[i][state]: state=0(정방향)/1(역방향)일 때 그룹 i까지의 누적 경계 비용
    dp: list[list[float]] = [[0.0, 0.0]]
    backptr: list[list[int | None]] = [[None, None]]

    def oriented(i: int, state: int) -> list[str]:
        return group_orders[i] if state == 0 else group_orders[i][::-1]

    for i in range(1, n):
        dp.append([inf, inf])
        backptr.append([None, None])
        for cur_state in (0, 1):
            cur_first = oriented(i, cur_state)[0]
            for prev_state in (0, 1):
                prev_last = oriented(i - 1, prev_state)[-1]
                candidate = dp[i - 1][prev_state] + cost_fn(color_feats[prev_last], color_feats[cur_first])
                if candidate < dp[i][cur_state]:
                    dp[i][cur_state] = candidate
                    backptr[i][cur_state] = prev_state

    state = 0 if dp[-1][0] <= dp[-1][1] else 1
    states = [state]
    for i in range(n - 1, 0, -1):
        state = backptr[i][state]
        states.append(state)
    states.reverse()

    return [oriented(i, states[i]) for i in range(n)]


def arrange_photos(
    groups: list[list[str]],
    color_feats: dict[str, np.ndarray],
    fitness_scores: dict[str, float],
    w1: float = 1.0,
    w2: float = 1.0,
    w3: float = 1.0,
    brute_force_max: int = 8,
) -> tuple[list[str], list[tuple[str, str, float]]]:
    """전체 배치 파이프라인: 그룹 내 정렬 -> 대표 사진 선정 -> 그룹 간 정렬 -> 경계 조정 -> 최종 순서.

    groups: 촬영 장소/세션 단위로 사용자가 수동 그룹핑한 photo_id 리스트의 리스트 (그룹 자체의 순서는 무관).
    반환: (최종 photo_id 순서, [(사진A, 사진B, 두 사진 사이 전이 비용), ...] 인접쌍 근거)
    """
    cost_fn = functools.partial(transition_cost, w1=w1, w2=w2, w3=w3)

    group_orders = []
    for group in groups:
        feats = [color_feats[pid] for pid in group]
        order_idx = order_items(feats, cost_fn, brute_force_max)
        group_orders.append([group[i] for i in order_idx])

    representatives = [select_representative(group, fitness_scores) for group in groups]
    rep_feats = [color_feats[pid] for pid in representatives]
    group_order_idx = order_items(rep_feats, cost_fn, brute_force_max)
    group_orders = [group_orders[i] for i in group_order_idx]

    group_orders = _optimize_boundaries(group_orders, color_feats, cost_fn)

    final_order = [pid for group in group_orders for pid in group]
    adjacency_costs = [
        (final_order[i], final_order[i + 1], cost_fn(color_feats[final_order[i]], color_feats[final_order[i + 1]]))
        for i in range(len(final_order) - 1)
    ]
    return final_order, adjacency_costs


if __name__ == "__main__":
    import sys

    import torch

    from features import extract_color_features
    from mlp import ScoringMLP, build_feature_vector, inference_scores

    if len(sys.argv) < 4:
        print("usage: python transition.py <theme_text> <group1_img,group1_img,...> [<group2_img,...> ...]")
        raise SystemExit(1)

    theme_text = sys.argv[1]
    groups: list[list[str]] = []
    paths: dict[str, str] = {}
    for group_idx, group_arg in enumerate(sys.argv[2:]):
        group_ids = [f"g{group_idx}_p{photo_idx}" for photo_idx in range(len(group_arg.split(",")))]
        groups.append(group_ids)
        paths.update(zip(group_ids, group_arg.split(",")))

    color_feats = {pid: extract_color_features(path) for pid, path in paths.items()}

    # 학습 전 랜덤 가중치이므로 점수 자체는 의미 없음 — 배치 파이프라인 shape만 검증
    model = ScoringMLP()
    fitness_scores = {
        pid: inference_scores(model, torch.from_numpy(build_feature_vector(path, theme_text)).unsqueeze(0)).item()
        for pid, path in paths.items()
    }

    order, adjacency = arrange_photos(groups, color_feats, fitness_scores)
    print(f"final order: {order}")
    for a, b, cost in adjacency:
        print(f"  {a} -> {b}: cost={cost:.4f}")
