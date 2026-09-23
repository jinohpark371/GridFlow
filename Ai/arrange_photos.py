"""학습된 TransitionCostModel로 사진 그룹을 정렬 (흐름도 > FastAPI 서버화 설계).

흐름: (수동 그룹핑 입력) -> 그룹 내 정렬 -> 그룹 대표 사진 선정 -> 그룹 간 정렬(대표 사진 기준)
      -> 그룹별 최종 순서 + 그룹 내부 인접쌍 비용

Ai/transition.py(삭제됨, 고정 가중치 버전)의 조합 최적화 로직을 그대로 가져오되,
비용 함수를 고정 가중치 공식 대신 학습된 TransitionCostModel.pair_cost로 교체했다.
그룹은 화면에서 별도 게시물/섹션으로 분리돼 실제 사진이 그룹 경계에서 맞닿지 않는다 —
그룹과 그룹 사이를 "이어주는" 건 대표 사진끼리의 비교(그룹 순서 결정)뿐이라, 그룹 경계의
전이 비용은 계산하지 않는다.
"""

from __future__ import annotations

import functools
import itertools
from typing import Callable

import numpy as np
import torch

from transition_cost_model import TransitionCostModel, pair_cost

CostFn = Callable[[np.ndarray, np.ndarray], float]


def model_cost_fn(model: TransitionCostModel, fi: np.ndarray, fj: np.ndarray) -> float:
    """두 사진의 11차원 피처 -> 학습된 TransitionCostModel 기준 전이 비용."""
    feat_a = torch.from_numpy(fi).unsqueeze(0)
    feat_b = torch.from_numpy(fj).unsqueeze(0)
    return pair_cost(model, feat_a, feat_b).item()


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


def arrange_photos(
    groups: list[list[str]],
    color_feats: dict[str, np.ndarray],
    fitness_scores: dict[str, float],
    model: TransitionCostModel,
    brute_force_max: int = 8,
) -> tuple[list[list[str]], list[list[tuple[str, str, float]]]]:
    """전체 배치 파이프라인: 그룹 내 정렬 -> 대표 사진 선정 -> 그룹 간 정렬 -> 그룹별 최종 순서.

    groups: 촬영 장소/세션 단위로 사용자가 수동 그룹핑한 photo_id 리스트의 리스트.
    반환: (그룹별 최종 사진 순서, 그룹별 내부 인접쌍 근거) — 둘 다 그룹 개수·순서가 같은 2차원 리스트.
      그룹은 화면에서 별도로 분리되므로 그룹 경계의 전이 비용은 계산하지 않는다.
    """
    cost_fn = functools.partial(model_cost_fn, model)

    group_orders = []
    for group in groups:
        feats = [color_feats[pid] for pid in group]
        order_idx = order_items(feats, cost_fn, brute_force_max)
        group_orders.append([group[i] for i in order_idx])

    representatives = [select_representative(group, fitness_scores) for group in groups]
    rep_feats = [color_feats[pid] for pid in representatives]
    group_order_idx = order_items(rep_feats, cost_fn, brute_force_max)
    group_orders = [group_orders[i] for i in group_order_idx]

    adjacency_costs = [
        [
            (group[i], group[i + 1], cost_fn(color_feats[group[i]], color_feats[group[i + 1]]))
            for i in range(len(group) - 1)
        ]
        for group in group_orders
    ]

    return group_orders, adjacency_costs
