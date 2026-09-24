# 사진 그룹 정렬 (`Ai/arrange_photos.py`)

> 작성일: 2026-09-23 · 작성자: 진오 · 관련 이슈: #8

## 📌 목적
학습된 `TransitionCostModel`을 실제로 써서 그룹 내 사진을 어울리는 순서로, 그룹 간에는 대표 사진 기준으로 정렬한다. `Ai/transition.py`(별도 브랜치에서 삭제됨)에 있던 조합 최적화 로직(완전탐색/greedy+2-opt)을 그대로 되살리되, 비용 함수만 고정 가중치 공식에서 학습된 모델로 교체했다.

## 🧭 파이프라인 상 위치
Layer 2 · 배치(순서 결정). `Ai/transition_cost_model.py`(비용 함수)와 `Ai/mlp.py`(그룹 대표 선정용 적합도 점수) 사이·다음에 위치하며, `Backend/main.py`의 `POST /arrange`가 이 모듈을 직접 호출한다.

- 이전 단계: `Ai/transition_cost_model.py`의 `pair_cost`(체크포인트 로딩 후), `Ai/mlp.py`의 `inference_scores`(그룹 대표 선정용 적합도)
- 다음 단계: `Backend/main.py`의 `POST /arrange` 엔드포인트

## 🔧 입출력 스펙

| 함수 | 입력 | 출력 | 설명 |
|---|---|---|---|
| `model_cost_fn` | `model, fi, fj` (11d 피처 2개) | `float` | `pair_cost`를 감싸 `order_items`가 기대하는 `(np.ndarray, np.ndarray) -> float` 형태로 맞춤 |
| `order_items` | `feats, cost_fn, brute_force_max=8` | `list[int]` | 총 비용 최소 순서(원본 인덱스). 적으면 완전탐색, 많으면 greedy+2-opt |
| `select_representative` | `group, fitness_scores` | `str` | 그룹 내 적합도 최고 사진을 대표로 선정 |
| `arrange_photos` | `groups, color_feats, fitness_scores, model, brute_force_max=8` | `(순서: list[list[str]], 인접쌍: list[list[tuple[str,str,float]]])` | 그룹 내 정렬 → 대표 선정 → 그룹 간 정렬 → 최종 순서 |

## 🧠 설계 결정과 이유

- 결정: `Ai/transition.py`의 조합 최적화 로직(`_total_cost`, `_brute_force_order`, `_nearest_neighbor_order`, `_two_opt`, `order_items`)을 거의 그대로 복원
  - 이유: 그 로직 자체(완전탐색/greedy+2-opt로 순서 찾기)는 문제없이 검증됐었고, 잘못됐던 건 "비용을 어떻게 계산하는가"(고정 가중치 공식)였지 "찾은 순서가 최적인가를 보장하는 알고리즘"이 아니었다. `_two_opt`의 구간 반전에 첫 자리(`i=0`)를 포함하는 수정 사항도 그대로 유지
- 결정: `transition_cost(fi, fj, w1, w2, w3)` 대신 `model_cost_fn(model, fi, fj)`로 비용 함수를 교체
  - 이유: 원래 함수는 hue/밝기/채도 3개 축의 고정 가중치 합이었는데, 이제 11차원 전체를 보고 비선형으로 판단하는 학습된 `TransitionCostModel.pair_cost`가 있어(val cost ranking accuracy 93.33%) 그걸 그대로 사용. `pair_cost`가 배치 텐서를 받는 것과 달리 `order_items`는 `(np.ndarray, np.ndarray) -> float` 형태의 콜러블을 기대해서, 사진 한 쌍씩 `unsqueeze(0)`으로 배치 크기 1을 만들어 감싸는 `model_cost_fn`을 새로 추가
- 결정: 그룹 경계의 전이 비용은 여전히 계산하지 않음(그룹 간은 대표 사진 비교로만 순서 결정)
  - 이유: 그룹은 화면에서 별도 게시물/섹션으로 분리돼 실제 사진이 맞닿지 않는다는 결정(예전 `docs/ai/Transition.md`의 결정)을 그대로 승계 — 이 전제 자체는 모델을 바꿨다고 달라지지 않음

## ⚙️ 동작 흐름

```python
model = load_checkpoint()  # transition_cost_model.py, 학습된 TransitionCostModel

order, adjacency = arrange_photos(groups, color_feats, fitness_scores, model)
# order: [[그룹0 사진 순서], [그룹1 사진 순서], ...]
# adjacency: [[그룹0 내부 인접쌍(사진A, 사진B, 비용)], ...] — 그룹 경계 비용은 없음
```

## ⚠️ 알려진 제약 / TODO

- [ ] 그룹핑 자체(촬영 장소/세션 단위로 나누는 로직)는 여전히 이 모듈 책임 밖 — 클라이언트가 미리 나눠서 보내는 것을 가정
- [ ] `brute_force_max=8` 초과 시 greedy+2-opt로 넘어가는데, 사진이 아주 많은 그룹(수십 장)에서의 속도는 실측하지 않음

## 🧪 사용 예시

```bash
python -c "
from transition_cost_model import load_checkpoint
from arrange_photos import arrange_photos
model = load_checkpoint()
# groups, color_feats, fitness_scores 준비 후:
# order, adjacency = arrange_photos(groups, color_feats, fitness_scores, model)
"
```

## 🔗 참고

- `docs/ai/Transition_cost_model.md` — `pair_cost` 세부 설계
- `docs/ai/Mlp_scoring.md` — 그룹 대표 선정에 쓰이는 `inference_scores`
- Notion "FastAPI 서버화 설계" — https://app.notion.com/p/3e4d1ebe485381c59a38c54dc392252c
- 관련 이슈: #8
