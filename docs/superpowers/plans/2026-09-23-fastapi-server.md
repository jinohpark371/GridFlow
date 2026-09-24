# FastAPI 서버화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `Ai/`의 두 모델(`ScoringMLP` 테마 필터링, `TransitionCostModel` 전이 비용)을 실제로 정렬까지 수행하는 `Ai/arrange_photos.py`로 엮고, FastAPI `POST /arrange` 엔드포인트로 HTTP에 노출한다.

**Architecture:** `Ai/arrange_photos.py`(신규)가 삭제된 `transition.py`의 조합 최적화 로직(완전탐색/greedy+2-opt)을 부활시키되 비용 함수를 학습된 `TransitionCostModel.pair_cost`로 교체한다. `Backend/main.py`는 `sys.path`로 `Ai/`를 추가해 bare import로 두 체크포인트를 시작 시 한 번만 로딩하고, 업로드된 사진마다 피처를 뽑아 `suggest_removal`(필터링) + `arrange_photos`(정렬)를 순서대로 호출한다.

**Tech Stack:** FastAPI, uvicorn, python-multipart(멀티파트 파싱), 기존 `Ai/` 스택(PyTorch, PIL, transformers) 재사용.

**Spec:** Notion "FastAPI 서버화 설계" — https://app.notion.com/p/3e4d1ebe485381c59a38c54dc392252c (GridFlow / 흐름도)

## Global Constraints

- `Ai/`는 패키지가 아니라 스크립트 스타일 — `Backend/main.py`는 `sys.path`에 `Ai/` 경로를 추가한 뒤 bare import(`from mlp import ...`)로 재사용한다. `tests/conftest.py`가 이미 같은 방식으로 `Ai/`를 `sys.path`에 추가하고 있으니 그 패턴을 그대로 따른다
- 사진은 저장하지 않는다 — 업로드된 사진은 메모리에서 피처만 뽑고 버린다(S3/디스크 저장 없음)
- 요청은 `multipart/form-data`: `theme`(텍스트), `photos`(파일 목록), `group_ids`(정수 목록, `photos`와 같은 길이)
- 응답의 `photo_id`는 업로드된 파일의 원본 파일명을 그대로 쓴다(요청 안에서만 유효, 별도 ID 체계 없음)
- `removed_candidates`는 `mlp.suggest_removal`이 제안한 것을 그대로 응답에 포함한다(자동 삭제 아님)
- 손상된 이미지는 해당 사진만 건너뛰고 응답의 `skipped` 목록에 담는다 — 조용히 사라지면 안 됨
- 체크포인트(`Ai/checkpoints/scoring_mlp.pt`, `Ai/checkpoints/transition_cost_model.pt`)가 없으면 서버 시작을 실패시킨다(요청마다 확인하지 않음)
- 이번 범위는 로컬 실행까지만 — Docker/클라우드 배포는 범위 밖
- 커밋은 사용자 승인 후 진행, 한글 메시지, `Co-Authored-By` 줄 없음(`AGENTS.md` 컨벤션)

## Review Focus

- 그룹의 사진이 테마 필터링으로 전부 제외되면 빈 그룹이 남는다 — 스펙은 이 경우를 명시하지 않지만, `select_representative`가 빈 리스트에서 `max()`를 호출하면 `ValueError`가 난다. 빈 그룹은 응답에서 조용히 제외해야 한다
- 같은 파일명(`photo_id`)이 두 번 업로드되면 `color_feats` 딕셔너리 키가 충돌해 사진 하나가 소리 없이 사라진다 — 명시적으로 `400`으로 거부해야 한다
- 그룹 안에 사진이 1장뿐이면 정렬할 게 없다 — `order_items`가 `n<=1`을 이미 처리하지만(원본 로직 재사용), `arrange_photos`가 빈 `adjacency_costs`를 정상적으로 반환하는지 확인해야 한다
- `photos`와 `group_ids` 길이가 다르면 어느 사진이 어느 그룹인지 알 수 없다 — `400`으로 거부해야 한다
- `photos`가 비어있는 요청(테마만 보내고 사진 없음)은 처리할 게 없다 — `400`으로 거부해야 한다

---

## File Structure

- **Create:** `Ai/arrange_photos.py` — 그룹 내/그룹 간 정렬 알고리즘 (조합 최적화 + `TransitionCostModel` 비용 함수)
- **Test:** `tests/ai/test_arrange_photos.py` — 순수 로직 단위 테스트
- **Create:** `Backend/main.py` — FastAPI 앱, `POST /arrange` 엔드포인트
- **Create:** `Backend/CLAUDE.md` — Backend 파트 세부 지침
- **Modify:** `AGENTS.md` — Backend 파트 절을 `[미정]`에서 실제 내용으로 교체
- **Modify:** `requirements.txt` — `fastapi`, `uvicorn`, `python-multipart` 추가(알파벳 순)
- **Test:** `tests/backend/test_main.py` — FastAPI `TestClient`로 엔드포인트 end-to-end 테스트 (`samples/`의 실제 사진 사용)
- **Create:** `docs/ai/Arrange_photos.md` — `Ai/arrange_photos.py` 설계 문서

---

## Task 1: 정렬 알고리즘 (`Ai/arrange_photos.py`)

**Files:**
- Create: `Ai/arrange_photos.py`
- Test: `tests/ai/test_arrange_photos.py`

**Interfaces:**
- Consumes: `Ai/mlp.py`의 `INPUT_DIM`(11), `Ai/transition_cost_model.py`의 `TransitionCostModel`, `pair_cost(model, feat_a, feat_b) -> torch.Tensor`
- Produces: `model_cost_fn(model, fi: np.ndarray, fj: np.ndarray) -> float`, `order_items(feats: list[np.ndarray], cost_fn, brute_force_max: int = 8) -> list[int]`, `select_representative(group: list[str], fitness_scores: dict[str, float]) -> str`, `arrange_photos(groups: list[list[str]], color_feats: dict[str, np.ndarray], fitness_scores: dict[str, float], model: TransitionCostModel, brute_force_max: int = 8) -> tuple[list[list[str]], list[list[tuple[str, str, float]]]]`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/ai/test_arrange_photos.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'arrange_photos'`

- [ ] **Step 3: 구현 작성**

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/ai/test_arrange_photos.py -v`
Expected: PASS (8개 테스트 모두)

- [ ] **Step 5: `docs/ai/Arrange_photos.md` 작성**

`docs/templete.md` 구조를 따라 새로 작성한다. 최소한 다음 내용을 담을 것:
- 📌 목적: 삭제된 `transition.py`의 조합 최적화 로직을 학습된 `TransitionCostModel` 기반으로 재구현
- 🧠 설계 결정과 이유: 왜 `transition.py`를 그대로 복사하지 않고 `model_cost_fn`으로 비용 함수만 교체했는지(원본 로직은 이미 검증된 조합 최적화라 재사용), 그룹 경계 비용을 계산하지 않는 이유(그룹은 화면에서 분리됨, 기존 `docs/ai/Transition.md`의 결정을 그대로 승계)
- 🔗 참고: `docs/ai/Transition_cost_model.md`, GitHub 이슈 #8

- [ ] **Step 6: 전체 유닛 테스트 재확인**

Run: `python -m pytest -q`
Expected: 이전까지의 모든 테스트 + 이번 8개 모두 PASS, 회귀 없음

---

## Task 2: Backend 프로젝트 뼈대 + 헬스체크

**Files:**
- Create: `Backend/main.py`
- Create: `Backend/CLAUDE.md`
- Modify: `AGENTS.md` (Backend 파트 절)
- Modify: `requirements.txt`
- Test: `tests/backend/test_main.py` (헬스체크만, `/arrange`는 Task 3)

**Interfaces:**
- Consumes: `Ai/mlp.py`의 `load_checkpoint`(이름 충돌 방지를 위해 `load_scoring_checkpoint`로 alias), `Ai/transition_cost_model.py`의 `load_checkpoint`(`load_transition_checkpoint`로 alias)
- Produces: FastAPI 앱 인스턴스 `app`(`Backend/main.py`의 모듈 전역), `GET /health` 엔드포인트, 앱 전역 `scoring_model`/`transition_model`(Task 3에서 사용)

- [ ] **Step 1: `requirements.txt`에 의존성 추가**

알파벳 순서에 맞춰 삽입: `fastapi`, `python-multipart`, `uvicorn`(정확한 버전은 설치 시 `pip index versions <패키지>`로 최신 안정 버전을 확인해 고정(`==`)한다. 확인이 어려우면 `fastapi==0.115.6`, `python-multipart==0.0.20`, `uvicorn==0.34.0`으로 우선 고정하고 설치 시점에 재확인).

- [ ] **Step 2: 실패하는 테스트 작성**

```python
"""Backend/main.py 헬스체크 + 앱 기동 테스트.

체크포인트가 실제로 로딩되는지 확인 — Ai/checkpoints/*.pt가 저장소에 커밋돼 있어
네트워크 없이 빠르게 실행됨.
"""

from fastapi.testclient import TestClient


def test_health_check_returns_ok():
    from main import app

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `python -m pytest tests/backend/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'main'` (아직 파일이 없음)

- [ ] **Step 4: 구현 작성**

`tests/backend/`에 `__init__.py`는 만들지 않는다(기존 `tests/ai/`도 패키지가 아님). 대신 `tests/conftest.py`가 이미 저장소 루트 기준 `sys.path` 설정을 하고 있는지 먼저 확인하고, `Backend/`도 같은 방식으로 `sys.path`에 잡히도록 `tests/conftest.py`에 한 줄 추가한다:

```python
# tests/conftest.py 맨 위쪽, 기존 Ai/ sys.path 추가 코드 바로 아래에 추가
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Backend"))
```

`Backend/main.py`:

```python
"""FastAPI 서버 - Ai/ScoringMLP(테마 필터링) + Ai/arrange_photos(정렬) 엔드포인트.

흐름: 사진 업로드(멀티파트) + 테마 문장 -> 11차원 피처 추출
      -> ScoringMLP로 부적합 사진 제외 제안 -> 그룹별로 arrange_photos로 정렬 -> JSON 응답

Ai/는 패키지가 아닌 bare import 스크립트 스타일이라, sys.path에 Ai/ 경로를 추가한 뒤
bare import로 재사용한다(tests/conftest.py와 동일한 패턴).
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

AI_DIR = Path(__file__).resolve().parent.parent / "Ai"
sys.path.insert(0, str(AI_DIR))

from fastapi import FastAPI  # noqa: E402
from mlp import load_checkpoint as load_scoring_checkpoint  # noqa: E402
from transition_cost_model import load_checkpoint as load_transition_checkpoint  # noqa: E402

scoring_model = None
transition_model = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scoring_model, transition_model
    # 체크포인트가 없으면 여기서 예외가 나서 서버 시작 자체가 실패한다(의도된 동작)
    scoring_model = load_scoring_checkpoint()
    transition_model = load_transition_checkpoint()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/backend/test_main.py -v`
Expected: PASS

- [ ] **Step 6: `Backend/CLAUDE.md` 작성**

```markdown
# Backend/CLAUDE.md

`Backend/` 디렉터리에서 작업할 때 적용되는 세부 지침이다. 프로젝트 공통 규칙은 루트 [`AGENTS.md`](../AGENTS.md) 참고.

## 구조

- FastAPI 앱, `Backend/main.py`가 진입점
- `Ai/`는 패키지가 아니라 bare import 스크립트 스타일이라, `sys.path`에 `Ai/` 경로를 추가한 뒤 bare import로 재사용한다(`Backend/main.py` 상단 참고) — `Ai/` 쪽 컨벤션(상대 import 금지 등)은 건드리지 않는다
- 별도 가상환경을 만들지 않는다 — 저장소 루트 `.venv`/`requirements.txt`를 그대로 사용

## 개발 환경

- 실행: `uvicorn main:app --reload --app-dir Backend`
- 체크포인트(`Ai/checkpoints/scoring_mlp.pt`, `Ai/checkpoints/transition_cost_model.pt`)가 없으면 서버 시작이 실패한다 — 먼저 `Ai/evaluate_mlp.py`, `Ai/evaluate_transition_cost_model.py`를 실행해 체크포인트를 만들어야 한다

## 테스트

- `tests/backend/test_main.py`에 FastAPI `TestClient`로 작성. `python -m pytest`로 `tests/ai/`와 함께 실행됨(같은 `pytest.ini` 기준)

## 범위

- 이번 단계는 로컬 실행까지만 — Docker/클라우드 배포는 범위 밖(필요해지면 이 문서에 절 추가)
- 사진은 저장하지 않는다 — 업로드된 사진은 메모리에서 피처만 뽑고 버린다(S3 등 오브젝트 스토리지 없음)
```

- [ ] **Step 7: `AGENTS.md`의 Backend 파트 절 갱신**

`AGENTS.md`에서 다음 텍스트를:
```
## Backend 파트

[미정] 아직 코드가 없다. 프레임워크, API 구조, DB 등 전부 미결정 상태 — 실제로 착수할 때 사용자와 먼저 정하고, 정해지면 `Backend/CLAUDE.md`를 이 절과 함께 추가한다.
```
다음으로 교체:
```
## Backend 파트

- 구조·개발 환경·테스트 명령어 등 세부 지침은 [`Backend/CLAUDE.md`](Backend/CLAUDE.md)에 있다
- 요약: FastAPI, `Ai/`를 `sys.path`로 불러와 bare import로 재사용, 별도 가상환경 없음, 사진은 저장하지 않음, 로컬 실행까지만(배포는 범위 밖)
```

- [ ] **Step 8: `git status`로 미커밋 변경 확인 후 커밋 준비**

이 태스크는 커밋하지 않는다 — Task 3까지 끝난 뒤 전체를 하나의 논리 단위로 묶어 `/ai-commit`에 준하는 방식으로 커밋한다(Backend/ 변경이 섞여 있어 `/ai-commit` 자체는 범위 밖이므로, 수동으로 커밋 메시지 작성 후 사용자 승인받아 진행).

---

## Task 3: `POST /arrange` 엔드포인트

**Files:**
- Modify: `Backend/main.py`
- Test: `tests/backend/test_main.py` (Task 2의 헬스체크 테스트에 이어서 추가)

**Interfaces:**
- Consumes: `Ai/mlp.py`의 `build_feature_vector(image, theme_text) -> np.ndarray`, `suggest_removal(model, feats: torch.Tensor, photo_ids: list[str], threshold=0.35) -> tuple[list[str], list[tuple[str, float]]]`, `Ai/arrange_photos.py`의 `arrange_photos(groups, color_feats, fitness_scores, model, brute_force_max=8) -> tuple[list[list[str]], list[list[tuple[str, str, float]]]]`, `Ai/mlp.py`의 `inference_scores(model, feats: torch.Tensor) -> torch.Tensor`
- Produces: `POST /arrange` 엔드포인트, 응답 JSON 스키마(`removed_candidates`, `skipped`, `groups`)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/backend/test_main.py`에 이어서 추가 (Task 2의 `test_health_check_returns_ok` 아래):

```python
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"


def _sample_file(name: str) -> tuple[str, bytes, str]:
    path = SAMPLES_DIR / name
    return (name, path.read_bytes(), "image/jpeg")


def test_arrange_returns_groups_and_removed_candidates():
    from main import app

    with TestClient(app) as client:
        response = client.post(
            "/arrange",
            data={"theme": "미니멀한 감성 사진", "group_ids": [0, 0, 1]},
            files=[
                ("photos", _sample_file("photo1.JPG")),
                ("photos", _sample_file("photo2.JPG")),
                ("photos", _sample_file("photo10.JPG")),
            ],
        )

    assert response.status_code == 200
    body = response.json()
    assert "removed_candidates" in body
    assert "skipped" in body
    assert len(body["groups"]) <= 2  # 필터링으로 그룹이 통째로 비면 결과에서 빠질 수 있음
    for group in body["groups"]:
        assert len(group["adjacency_costs"]) == len(group["order"]) - 1


def test_arrange_rejects_mismatched_lengths():
    from main import app

    with TestClient(app) as client:
        response = client.post(
            "/arrange",
            data={"theme": "테마", "group_ids": [0]},
            files=[
                ("photos", _sample_file("photo1.JPG")),
                ("photos", _sample_file("photo2.JPG")),
            ],
        )

    assert response.status_code == 400


def test_arrange_rejects_empty_photos():
    from main import app

    with TestClient(app) as client:
        response = client.post("/arrange", data={"theme": "테마", "group_ids": []}, files=[])

    assert response.status_code == 400


def test_arrange_rejects_duplicate_filenames():
    """Review Focus: 같은 파일명이 두 번 업로드되면 어느 사진인지 알 수 없어 거부해야 한다."""
    from main import app

    with TestClient(app) as client:
        response = client.post(
            "/arrange",
            data={"theme": "테마", "group_ids": [0, 0]},
            files=[
                ("photos", _sample_file("photo1.JPG")),
                ("photos", ("photo1.JPG", (SAMPLES_DIR / "photo2.JPG").read_bytes(), "image/jpeg")),
            ],
        )

    assert response.status_code == 400
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/backend/test_main.py -v`
Expected: FAIL — `404 Not Found` (엔드포인트가 아직 없음)

- [ ] **Step 3: 구현 작성**

`Backend/main.py`에 추가(기존 `import` 블록과 `app = FastAPI(...)` 사이에 import 추가, 파일 맨 아래에 엔드포인트 추가):

```python
# 기존 import 블록에 추가 (Backend/main.py 상단, "from transition_cost_model import ..." 다음 줄부터)
from io import BytesIO  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
from fastapi import File, Form, HTTPException, UploadFile  # noqa: E402
from PIL import Image  # noqa: E402
from mlp import build_feature_vector, inference_scores, suggest_removal  # noqa: E402
from arrange_photos import arrange_photos  # noqa: E402
```

`np`는 이 파일에 처음 등장하는 import이므로, Task 2에서 작성한 기존 import 블록 끝에 정확히 위 순서대로 추가한다(중복 import 없이 한 번만).

```python
# 파일 맨 아래에 추가

THRESHOLD = 0.35
BRUTE_FORCE_MAX = 8


@app.post("/arrange")
async def arrange(
    theme: str = Form(...),
    photos: list[UploadFile] = File(...),
    group_ids: list[int] = Form(...),
):
    if not photos:
        raise HTTPException(400, "photos가 비어있음")
    if len(photos) != len(group_ids):
        raise HTTPException(400, "photos와 group_ids 길이가 다름")

    filenames = [photo.filename for photo in photos]
    if len(set(filenames)) != len(filenames):
        raise HTTPException(400, "photos에 중복된 파일명이 있음 — photo_id로 구분할 수 없음")

    color_feats: dict[str, "np.ndarray"] = {}
    photo_id_to_group: dict[str, int] = {}
    skipped: list[dict] = []

    for photo, group_id in zip(photos, group_ids):
        try:
            content = await photo.read()
            image = Image.open(BytesIO(content)).convert("RGB")
            color_feats[photo.filename] = build_feature_vector(image, theme)
            photo_id_to_group[photo.filename] = group_id
        except Exception as exc:  # 손상된 이미지 등은 이 사진만 건너뜀
            skipped.append({"photo_id": photo.filename, "reason": str(exc)})

    if not color_feats:
        return {"removed_candidates": [], "skipped": skipped, "groups": []}

    photo_ids = list(color_feats.keys())
    feats_tensor = torch.from_numpy(np.stack([color_feats[pid] for pid in photo_ids]))
    keep_ids, remove_candidates = suggest_removal(scoring_model, feats_tensor, photo_ids, threshold=THRESHOLD)
    removed_candidates = [{"photo_id": pid, "score": score} for pid, score in remove_candidates]

    keep_feats_tensor = torch.from_numpy(np.stack([color_feats[pid] for pid in keep_ids])) if keep_ids else torch.empty(0)
    fitness_scores = {
        pid: score.item() for pid, score in zip(keep_ids, inference_scores(scoring_model, keep_feats_tensor))
    } if keep_ids else {}

    groups_by_id: dict[int, list[str]] = {}
    for pid in keep_ids:
        groups_by_id.setdefault(photo_id_to_group[pid], []).append(pid)
    # Review Focus: 필터링으로 전부 제거된 그룹은 조용히 결과에서 뺀다(빈 그룹으로 select_representative를 부르면 에러)
    non_empty_groups = [group for group in groups_by_id.values() if group]

    order, adjacency = arrange_photos(
        non_empty_groups, color_feats, fitness_scores, transition_model, BRUTE_FORCE_MAX
    ) if non_empty_groups else ([], [])

    groups_response = [
        {
            "order": group_order,
            "adjacency_costs": [[a, b, cost] for a, b, cost in group_adjacency],
        }
        for group_order, group_adjacency in zip(order, adjacency)
    ]

    return {"removed_candidates": removed_candidates, "skipped": skipped, "groups": groups_response}
```

구현 전에 `Backend/main.py` 전체를 한 번 읽고, 위 import 블록이 기존 import와 중복되지 않는지 확인한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/backend/test_main.py -v`
Expected: PASS (5개 테스트 모두). `test_arrange_returns_groups_and_removed_candidates`는 실제 체크포인트로 CLIP까지 태우므로 몇 초 걸릴 수 있음 — 정상.

- [ ] **Step 5: 전체 테스트 스위트 재확인**

Run: `python -m pytest -q`
Expected: 기존 테스트 전부 + 이번에 추가한 것 모두 PASS, 회귀 없음

- [ ] **Step 6: 수동 실행으로 실제 서버 기동 확인**

Run: `uvicorn main:app --app-dir Backend` (별도 터미널에서), 그다음 `curl -F theme="미니멀한 감성 사진" -F group_ids=0 -F group_ids=0 -F photos=@samples/photo1.JPG -F photos=@samples/photo2.JPG http://127.0.0.1:8000/arrange`로 실제 응답 확인. 사용자와 함께 결과를 확인할 것(자동화된 테스트로 대체하지 않음).

---

## Task 4: 문서화 + 커밋

**Files:**
- 이 플랜에서 변경된 모든 파일(`Ai/arrange_photos.py`, `Backend/main.py`, `Backend/CLAUDE.md`, `AGENTS.md`, `requirements.txt`, `docs/ai/Arrange_photos.md`, `tests/ai/test_arrange_photos.py`, `tests/backend/test_main.py`, `tests/conftest.py`)

- [ ] **Step 1: `git status`/`git diff`로 최종 변경 사항 확인**

`Ai/` 변경과 `Backend/` 변경이 섞여 있어 `/ai-commit`(Ai/ 전용) 범위를 벗어난다 — 수동으로 커밋 그룹을 나눈다(예: Ai/arrange_photos.py+docs+test 커밋 하나, Backend/ 전체 커밋 하나, 또는 사용자와 상의해 하나로 묶기).

- [ ] **Step 2: 커밋 메시지 작성 후 사용자 승인받고 커밋**

한글, `<type>(<scope>): <subject>` 형식, `Co-Authored-By` 없음(`AGENTS.md` 컨벤션). 승인 없이 임의로 커밋하지 않는다.

- [ ] **Step 3: PR 생성 여부 확인**

`git branch --show-current`로 현재 브랜치 확인(이슈 #8용 새 브랜치가 필요하면 `/issue` 절차의 브랜치 생성 관례에 맞춰 `develop` 기반으로 새로 파는 것을 사용자에게 먼저 확인). PR은 `/pr` 커맨드로 진행.
