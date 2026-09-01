# 전이 비용 배치 (`Ai/transition.py`)

> 작성일: 2026-09-01 · 작성자: 진오 · 관련 이슈: #7

## 📌 목적
MLP가 테마 부적합 사진을 거른 뒤, **유지된 사진들의 실제 순서**를 정하는 단계. "이웃한 두 사진이 얼마나 튀는가"를 색감 차이(hue/brightness/saturation)로 계산해, 그 합이 최소가 되는 순서를 그룹 내부/그룹 사이 두 레벨로 나눠 찾는다.

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
| `arrange_photos` | `groups: list[list[str]], color_feats: dict[str, np.ndarray], fitness_scores: dict[str, float], w1, w2, w3` | `(순서: list[str], 인접쌍 근거: list[tuple[str, str, float]])` | 전체 파이프라인 — 그룹 내 정렬 → 대표 선정 → 그룹 간 정렬 → 경계 조정 → 최종 순서 |

## 🧠 설계 결정과 이유

- 결정: `transition_cost`는 딕셔너리(`fi['hue']`) 대신 `features.py`의 배열 인덱스(`fi[0..2]`=mean_h/s/v)를 그대로 사용
  - 이유: Notion 문서는 딕셔너리 접근을 가정하지만 `extract_color_features`는 이미 배열을 반환 중 — 어댑터 없이 기존 파이프라인에 바로 연결(사용자 확인 후 결정)
- 결정: 그룹 입력은 `list[list[str]]` (이름/메타 없는 photo_id 리스트의 리스트)
  - 이유: 그룹핑 UI/로직은 이슈 범위 밖 — 수동 입력용 최소 시그니처만 필요(사용자 확인 후 결정)
- 결정: `arrange_photos`의 "근거"는 순서 + 인접쌍 전이 비용만 반환 (그룹 소속·대표 사진 등은 미포함)
  - 이유: "총 전이 비용" 평가 지표 계산에 바로 쓸 수 있는 최소 구성(사용자 확인 후 결정)
- 결정: 그룹 내 정렬(4번)과 그룹 간 정렬(5-1번)이 `order_items` 하나를 재사용
  - 이유: Notion 문서 5-1절 — "레벨만 다를 뿐 문제 구조는 같다"
- 결정: 그룹 경계 이음매 조정(5-2번)을 "각 그룹의 방향(정/역) 선택 DP"로 구현
  - 이유: 경로(path)의 내부 총 비용은 방향을 뒤집어도 동일 — 이것이 문서가 말하는 "남아있는 배치 자유도"의 실체. 그룹 시퀀스는 이미 고정돼 있으므로 방향만 고르면 되고, 2-state DP로 전역 최적을 구함. 문서에 구체적 알고리즘이 없어 가정으로 구현 — 다른 해석이 필요하면 재검토
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
# order: 최종 photo_id 순서
# adjacency: [(사진A, 사진B, 전이비용), ...] — sum(cost)이 "총 전이 비용" 평가 지표
```

## ⚠️ 알려진 제약 / TODO

- [x] 그룹 내/그룹 간 정렬, 경계 방향 조정을 포함한 1단계 파이프라인(`arrange_photos`) 구현 완료
- [ ] 가중치 학습(`TransitionCostModel`, 2단계)은 이 이슈 범위 밖 — 드래그 재정렬 데이터가 쌓인 뒤 별도 이슈로 진행 (Notion 설계 문서 3절, 8절)
- [ ] 평가 지표 중 "총 전이 비용"은 `arrange_photos`가 반환하는 `adjacency`를 합산하면 바로 계산 가능하나, "사용자 수정 비율"(추천 순서 대비 실제 변경 정도)은 실제 드래그 재정렬 데이터가 없어 측정 로직 미구현 — 데이터가 쌓인 뒤 `evaluate_mlp.py`와 유사한 형태로 추가 검토
- [ ] 경계 조정을 "그룹 방향 선택"으로 한정한 것은 가정이며, 설계 문서가 요구하는 범위와 다를 수 있음 — 실사용 결과가 부자연스러우면 그룹 내부 재배치까지 포함하는 방식으로 재검토

## 🧪 사용 예시

```bash
python Ai/transition.py "미니멀한 감성 사진" photo1.jpg,photo2.jpg,photo3.jpg photo4.jpg,photo5.jpg
# 출력 예: final order: ['g0_p1', 'g0_p0', 'g0_p2', 'g1_p0', 'g1_p1']
#            g0_p1 -> g0_p0: cost=0.1234
#            ...
```

## 🔗 참고

- Notion "전이 비용 배치 설계" 문서(흐름도 > 전이 비용 배치 설계) — https://app.notion.com/p/3ced1ebe4853805da88adb86b34ec0a6
- `docs/ai/Color_features.md` — 전이 비용 계산에 쓰이는 색감 피처(10d) 세부 설계
- `docs/ai/Mlp_scoring.md` — 그룹 대표 사진 선정에 쓰이는 적합도 점수(`inference_scores`)
- 관련 이슈: #7
