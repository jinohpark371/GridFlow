# 학습 데이터 로딩·구성 (`Ai/dataset.py`)

> 작성일: 2026-08-27 · 최종 수정: 2026-11-02 · 작성자: 진오 · 관련 이슈: test/mlp-학습-파이프라인/4, #9, #13, #23

## 📌 목적
`ScoringMLP`(`Ai/mlp.py`)와 `TransitionCostModel`(`Ai/transition_cost_model.py`)이 각자 필요로 하는 형태로 Unsplash 데이터를 읽어, 학습 루프에 바로 넣을 수 있는 배치 텐서로 만든다. `ScoringMLP`는 테마마다 모델을 따로 두므로 "테마 하나 기준" 학습 쌍을, `TransitionCostModel`은 여러 테마를 오가는 페어와이즈 샘플을 만든다.

## 🧭 파이프라인 상 위치
"MLP 모델 설계"/"전이 비용 배치 설계" 단계와 각 학습 스크립트 사이의 데이터 로더.

- Layer: Layer 1(테마 적합도) + Layer 2(전이 비용) 공통 · 학습 데이터 로딩
- 이전 단계: `Ai/collect_unsplash_data.py`가 만든 `photos.csv`(피처), `Ai/build_scoring_theme_data.py`가 만든 `cross_clip_sim.csv`(사진 x 테마 문장 clip_sim)
- 다음 단계: `Ai/train_mlp.py`+`Ai/evaluate_mlp.py`(ScoringMLP), `Ai/transition_cost_model.py`+`Ai/evaluate_transition_cost_model.py`(TransitionCostModel)

## 🔧 입출력 스펙

| 함수 | 입력 | 출력 | 설명 |
|---|---|---|---|
| `load_photo_pool` | `path`(기본 `photos.csv`) | `(photo_id -> 11d 피처, 테마 -> photo_id 리스트)` | 두 모델 공통. 11d의 `clip_sim`은 수집 테마 기준 값 |
| `load_cross_clip_sim` | `path`(기본 `cross_clip_sim.csv`) | `photo_id -> {테마 문장: clip_sim}` | 컬럼(`clip_mono` 등)을 테마 문장으로 되돌려 둠 |
| `split_photos` | `by_theme, n_val=6, seed=42` | `(학습 by_theme, 검증 by_theme)` | 테마별로 섞어 6장 검증 / 나머지 학습 |
| `theme_feature` | `photo_id, theme_text, features, cross` | `np.ndarray` (11d) | 색감 10d는 그대로, `clip_sim`만 `theme_text` 기준 값으로 교체한 사본 |
| `build_theme_pairs` | `theme_text, by_theme, features, cross` | `(feats_pos, feats_neg)` | (이 테마 사진 x 다른 테마 사진) 모든 조합 |
| `build_theme_labeled` | `theme_text, by_theme, features, cross` | `(feats, labels)` | 사진별 11d + 정답(이 테마 1, 나머지 0) — 기준값·검증용 |
| `sample_theme_pair_features` | `features, by_theme, n_pairs, rng` | 4개 텐서 | TransitionCostModel용 같은 테마 2장/다른 테마 2장 무작위 샘플 |

## 🧠 설계 결정과 이유

- 결정(변경, 2026-11-02): 흑백 고정 테마 트리플렛(`scoring_pairs.csv`/`scoring_photos.csv`, `load_label_pairs`/`build_pair_features`)을 없애고, `photos.csv` + `cross_clip_sim.csv`에서 테마별 학습 쌍을 그때그때 구성
  - 이유: 테마마다 모델을 따로 학습하기로 함(#23, `docs/ai/Mlp_scoring.md`). 테마 3개 x 쌍 구성을 CSV로 미리 저장해 두기보다, 원본 피처 + 교차 clip_sim 두 파일만 두고 쌍은 코드로 만드는 편이 데이터 중복이 없음
- 결정: 학습/검증을 **쌍이 아니라 사진 단위**로 나눔(테마당 24장 / 6장)
  - 이유: 쌍 단위로 나누면 같은 사진이 학습 쌍과 검증 쌍에 동시에 들어가, 모델이 사진을 외워도 정확도가 높게 나옴. 사진 단위로 나눠야 "처음 보는 사진도 맞히는지"를 잼
- 결정: 분할 전에 고정 seed로 섞음
  - 이유: `photos.csv`는 Unsplash 검색 순위 순서라 뒤쪽만 떼면 검증 사진이 테마와 덜 맞는 하위권으로 쏠림. seed 고정으로 실행마다 같은 분할 유지
- 결정: 학습 쌍은 무작위 샘플이 아니라 (이 테마 x 다른 테마) **모든 조합**(테마당 24 x 48 = 1,152쌍)
  - 이유: 사진이 72장뿐이라 일부만 뽑으면 버려지는 정보가 생기고, 1,152쌍도 풀배치 학습이 1초 안팎이라 부담이 없음
- 결정: `theme_feature`는 `clip_sim`만 대상 테마 값으로 바꾼 **사본**을 돌려줌
  - 이유: `photos.csv`의 `clip_sim`은 수집 테마 기준이라 그대로 쓰면 흑백 사진이 비비드 모델 입장에서 엉뚱한 값을 갖게 됨(#23 원인 중 하나). 원본 딕셔너리를 바꾸면 다른 테마 쌍을 만들 때 오염되므로 복사본으로 처리
- 결정: `load_cross_clip_sim`은 `mlp.THEME_KEYS`를 함수 안에서 import
  - 이유: `TransitionCostModel`처럼 `dataset.py`만 쓰는 곳이 모듈을 불러올 때마다 CLIP(transformers)까지 따라 올라오지 않게 함
- 결정: CSV에 미리 계산된 피처를 `photo_id`로 조회 (유지)
  - 이유: Unsplash 데이터는 이미지를 로컬에 저장하지 않아(이슈 #9) 다시 열 이미지가 없음 — 수집 시점에 계산해 둔 피처를 재사용

## ⚙️ 동작 흐름

```python
features, by_theme = load_photo_pool()           # 90장, 테마당 30장
cross = load_cross_clip_sim()                     # 90장 x 테마 문장 3개
train, val = split_photos(by_theme)               # 테마당 24 / 6

feats_pos, feats_neg = build_theme_pairs(VIVID, train, features, cross)   # (1152, 11) x 2
val_feats, val_labels = build_theme_labeled(VIVID, val, features, cross)  # (18, 11), 비비드 6장만 1
```

## ⚠️ 알려진 제약 / TODO

- [x] ~~같은 사진이 여러 쌍에 등장해도 그때마다 CLIP 임베딩을 다시 계산함~~ — Unsplash 데이터 전환으로 해소
- [x] ~~ScoringMLP가 흑백 고정 테마 데이터 하나만 지원~~ — 테마별 쌍 구성으로 해소(2026-11-02, #23)
- [ ] 검증 사진이 테마당 6장뿐이라 정확도 한 장 차이가 5%p 넘게 움직임 — 데이터가 늘면 k-fold 등 재검토

## 🧪 사용 예시

```bash
python Ai/dataset.py
# 출력 예: black and white monochrome photography: 학습 24장 / 검증 6장 -> 학습 쌍 (1152, 11)
```

## 🔗 참고

- `docs/ai/Collect_unsplash_data.md` — `photos.csv`를 만드는 수집 스크립트
- `docs/ai/Build_scoring_theme_data.md` — `cross_clip_sim.csv`를 만드는 스크립트
- `docs/ai/Mlp_scoring.md` — 테마별 모델 설계와 결과
- GitHub 이슈 #4, #9, #13, #23
