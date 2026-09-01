# 전이 비용 배치 (`Ai/transition.py`)

> 작성일: 2026-09-01 · 작성자: 진오 · 관련 이슈: #7

## 📌 목적
MLP가 테마 부적합 사진을 거른 뒤, **유지된 사진들의 실제 순서**를 정하는 단계. "이웃한 두 사진이 얼마나 튀는가"를 색감 차이(hue/brightness/saturation)로 계산해, 그 합이 최소가 되는 순서를 찾는다. 그룹은 화면에서 별도 게시물/섹션으로 분리되므로, 정렬은 **그룹 내부**(사진끼리)와 **그룹 간**(대표 사진끼리) 두 레벨로 독립적으로 이뤄지고 둘이 실제로 맞닿는 경계 비용은 계산하지 않는다.

## 🧭 파이프라인 상 위치
전체 아키텍처 순서도 기준 "전이 비용 배치 설계" 단계이며, `mlp.py`가 만든 적합도 점수(그룹 대표 선정)와 `features.py`의 색감 피처(전이 비용 계산)를 입력으로 받는다.

- Layer: Layer 2 · 배치(순서 결정)
- 이전 단계: MLP 적합도 스코어링(`mlp.py`) — 부적합 사진 제외 + 유지 사진 점수, 색감 피처 추출(`features.py`)
- 다음 단계: 없음 — 1단계(고정 가중치 MVP) 범위. 가중치 학습(`TransitionCostModel`, 2단계)은 드래그 재정렬 데이터가 쌓인 뒤 별도 이슈

## 🔧 입출력 스펙

| 함수 | 입력 | 출력 | 설명 |
|---|---|---|---|
| `transition_cost` | `fi, fj (10d 색감 피처), w1=w2=w3=1.0` | `float` | 두 사진 사이 전이 비용 — hue/brightness/saturation 절대차의 가중합 |
| `order_items` | `feats: list[np.ndarray], cost_fn, brute_force_max=8` | `list[int]` (원본 인덱스 순서) | 총 전이 비용 최소 순서. `len<=8`은 완전탐색, 그 이상은 greedy+2-opt |
| `select_representative` | `group: list[str], fitness_scores: dict[str, float]` | `str` (photo_id) | 그룹 내 MLP 적합도 최고 사진을 대표로 선정 |
| `arrange_photos` | `groups: list[list[str]], color_feats: dict[str, np.ndarray], fitness_scores: dict[str, float], w1, w2, w3` | `(순서: list[list[str]], 인접쌍 근거: list[list[tuple[str, str, float]]])` | 전체 파이프라인 — 그룹 내 정렬 → 대표 선정 → 그룹 간 정렬 → 그룹별 최종 순서. 둘 다 그룹 개수·순서가 같은 2차원 리스트, 인접쌍은 그룹 내부만 담음 |

## 🧠 설계 결정과 이유

- 결정: `transition_cost`는 딕셔너리(`fi['hue']`) 대신 `features.py`의 배열 인덱스(`fi[0..2]`=mean_h/s/v)를 그대로 사용
  - 이유: Notion 문서는 딕셔너리 접근을 가정하지만 `extract_color_features`는 이미 배열을 반환 중 — 어댑터 없이 기존 파이프라인에 바로 연결(사용자 확인 후 결정)
- 결정: 그룹 입력은 `list[list[str]]` (이름/메타 없는 photo_id 리스트의 리스트)
  - 이유: 그룹핑 UI/로직은 이슈 범위 밖 — 수동 입력용 최소 시그니처만 필요(사용자 확인 후 결정)
- 결정: `arrange_photos`는 순서(`order`)와 인접쌍 근거(`adjacency`)를 모두 `group_orders`와 정렬된 2차원 리스트(`list[list[...]]`)로 반환 — 평탄화된 `list[str]`을 만들지 않음
  - 이유: 처음엔 평탄화된 `list[str]`만 반환했으나, 그룹 소속 정보가 사라져 나중에 그룹 경계를 다시 알아낼 방법이 없다는 문제가 대화 중 확인돼 `group_orders` 구조를 그대로 보존하는 쪽으로 변경
- 결정: `adjacency`는 그룹 **내부** 인접쌍만 담고, 그룹 경계(그룹 마지막 사진 ↔ 다음 그룹 첫 사진)의 전이 비용은 계산하지 않음. 그룹 간 순서는 대표 사진끼리의 비교(`order_items(rep_feats, ...)`)로만 정함
  - 이유: 그룹은 화면에서 별도 게시물/섹션으로 분리돼 실제로는 그룹 경계의 두 사진이 옆에 붙지 않음 — 그룹과 그룹을 "이어주는" 건 대표 사진끼리의 비교뿐이라는 걸 대화 중 확인. 애초에 이 전제를 잘못 파악해 그룹 경계 방향(정/역)을 DP로 최적화하는 `_optimize_boundaries`를 구현했었으나, 존재하지 않는 문제를 풀고 있었던 것이라 제거함(Notion 5-2절 "경계 최적화"도 같은 이유로 함께 수정)
- 결정: 그룹 내 정렬(4번)과 그룹 간 정렬(5-1번)이 `order_items` 하나를 재사용
  - 이유: Notion 문서 5-1절 — "레벨만 다를 뿐 문제 구조는 같다"
- 결정: `order_items`의 완전탐색/greedy+2-opt 분기 기준(`brute_force_max`)은 문서의 "~8장" 기준을 그대로 기본값으로 사용
- 결정: `_two_opt`의 구간 반전에 첫 자리(`i=0`)도 포함 (Notion 원문은 `range(1, ...)`로 고정)
  - 이유: 순환(TSP)과 달리 경로는 부분 반전이 비용 중립이 아님 — 첫 자리를 고정하면 개선 가능한 후보를 놓칠 수 있어 대화 중 수정, Notion 원문도 함께 갱신

## ⚙️ 동작 흐름

```python
# 1) 사용자가 촬영 장소/세션 단위로 수동 그룹핑 (그룹핑 로직 자체는 이 모듈 밖)
groups = [["photo1", "photo2", "photo3"], ["photo4", "photo5"]]

# 2) 각 사진의 색감 피처(features.py)와 MLP 적합도 점수(mlp.py)를 미리 준비
color_feats = {pid: extract_color_features(path) for pid, path in paths.items()}
fitness_scores = {pid: inference_scores(model, feat).item() for pid, feat in ...}

# 3) 전체 배치 파이프라인 실행 (고정 가중치 w1=w2=w3=1.0)
order, adjacency = arrange_photos(groups, color_feats, fitness_scores)
# order: [[그룹0 사진 순서], [그룹1 사진 순서], ...] — 그룹은 화면에서 분리되므로 그룹 자체는 안 섞임
# adjacency: [[그룹0 내부 인접쌍], [그룹1 내부 인접쌍], ...] — 그룹 경계 비용은 포함하지 않음
total_cost = sum(cost for group_adjacency in adjacency for _, _, cost in group_adjacency)  # "총 전이 비용" 평가 지표
```

## ⚠️ 알려진 제약 / TODO

- [x] 그룹 내/그룹 간 정렬을 포함한 1단계 파이프라인(`arrange_photos`) 구현 완료 — 그룹 경계 비용은 계산하지 않음(위 결정 참고)
- [ ] 가중치 학습(`TransitionCostModel`, 2단계)은 이 이슈 범위 밖 — 드래그 재정렬 데이터가 쌓인 뒤 별도 이슈로 진행 (Notion 설계 문서 3절, 8절)
- [ ] 평가 지표 중 "총 전이 비용"은 `arrange_photos`가 반환하는 `adjacency`(그룹 내부 비용)를 합산하면 계산 가능하나, "사용자 수정 비율"(추천 순서 대비 실제 변경 정도)은 실제 드래그 재정렬 데이터가 없어 측정 로직 미구현 — 데이터가 쌓인 뒤 `evaluate_mlp.py`와 유사한 형태로 추가 검토

## 🧪 사용 예시

```bash
python Ai/transition.py "미니멀한 감성 사진" photo1.jpg,photo2.jpg,photo3.jpg photo4.jpg,photo5.jpg
# 출력 예: group 0: ['g0_p1', 'g0_p0', 'g0_p2']
#            g0_p1 -> g0_p0: cost=0.1234
#            g0_p0 -> g0_p2: cost=0.2345
#          group 1: ['g1_p0', 'g1_p1']
#            g1_p0 -> g1_p1: cost=0.0567
```

## 🔗 참고

- Notion "전이 비용 배치 설계" 문서(흐름도 > 전이 비용 배치 설계) — https://app.notion.com/p/3ced1ebe4853805da88adb86b34ec0a6
- `docs/ai/Color_features.md` — 전이 비용 계산에 쓰이는 색감 피처(10d) 세부 설계
- `docs/ai/Mlp_scoring.md` — 그룹 대표 사진 선정에 쓰이는 적합도 점수(`inference_scores`)
- 관련 이슈: #7
