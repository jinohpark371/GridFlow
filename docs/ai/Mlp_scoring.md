# MLP 테마 적합도 스코어링 (`Ai/mlp.py`)

> 작성일: 2026-08-24 · 최종 수정: 2026-11-02 · 작성자: 진오 · 관련 이슈: feature/mlp-적합도-스코어링/1, #23

## 📌 목적
사진이 선택된 테마에 얼마나 적합한지 **상대적으로** 비교하도록 학습되는 Siamese MLP. **테마마다 모델을 하나씩**(흑백·비비드·골든아워) 따로 학습해 둔다. 순서를 직접 정하지 않고 ①부적합 사진의 제외를 제안하고 ②유지 사진에 점수(가중치)를 부여하는 역할만 담당한다.

## 🧭 파이프라인 상 위치
전체 아키텍처 순서도 기준 "MLP 모델 설계" 단계이며, `clip.py`의 콜드스타트 baseline을 대체하는 Layer 1 본 모델이다.

- Layer: Layer 1 · 테마 적합도 스코어링
- 이전 단계: CLIP 임베딩(`clip.py`) + 색감 피처(`features.py`) → 11d 입력 벡터
- 다음 단계: 전이 비용 최소화 배치(실제 순서 결정) — 아직 미구현, 이 모듈 책임 밖

## 🔧 입출력 스펙

| 함수 | 입력 | 출력 | 설명 |
|---|---|---|---|
| `build_feature_vector` | `image, theme_text` | `np.ndarray` (11d) | CLIP 유사도(1) + 색감 피처(10)를 concat |
| `ScoringMLP.forward` | `torch.Tensor` (batch, 11) | `torch.Tensor` (batch, 1) | 사진 하나당 적합도 점수 하나 |
| `rank_forward` | `model, feat_a, feat_b` | `(score_a, score_b)` | 동일 가중치 모델을 두 사진에 각각 적용 (Siamese) |
| `margin_ranking_loss` | `score_pos, score_neg, margin=0.2` | `torch.Tensor` (scalar) | (a) 초기 권장 loss |
| `ranknet_loss` | `score_pos, score_neg` | `torch.Tensor` (scalar) | (b) 안정화 후 전환 후보 |
| `filter_by_fitness` | `model, feats, threshold=0.35` | `(keep_idx, scores)` | threshold 이상 인덱스만 반환, 순서는 정하지 않음 |
| `suggest_removal` | `model, feats, photo_ids, threshold=0.35` | `(keep_ids, remove_candidates)` | 제외 "제안" 목록만 생성 (자동 삭제 아님) |
| `inference_scores` | `model, feats` | `torch.Tensor` (shape `(N,)`) | eval 모드로 결정적으로 점수 계산 후 이전 모드로 복원 (Dropout 끔) |
| `save_checkpoint` | `model, path` | `None` | 학습된 가중치(`state_dict`) 저장 — 경로는 `theme_checkpoint_path`로 정함 |
| `load_checkpoint` | `path` | `ScoringMLP` (eval 모드) | 저장된 가중치를 불러와 즉시 추론 가능한 모델로 복원 |
| `THEME_KEYS` | — | `dict[str, str]` | 테마 문장 -> 짧은 키(`mono`/`vivid`/`golden`). 모델 파일명·`cross_clip_sim.csv` 컬럼명에 씀 |
| `theme_checkpoint_path` | `theme_text` | `Path` | `Ai/checkpoints/scoring_mlp_<키>.pt` |
| `save_thresholds` / `load_thresholds` | `{키: 기준값}`, `path`(기본 `Ai/checkpoints/scoring_thresholds.json`) | `None` / `dict[str, float]` | 테마별 기준값 저장·불러오기 |

## 🧠 설계 결정과 이유

- 결정: 절대 점수가 아니라 **pairwise ranking**으로 학습
  - 이유: 사용자로부터 "이 사진은 0.7점" 같은 절대 라벨을 받을 방법이 없음. 반면 "이 사진은 유지, 저 사진은 제외" 같은 상대적 피드백은 자연스럽게 쌓임 (Notion 설계 문서 1절)
- 결정: Siamese 구조 (모델 하나, 두 사진에 동일 가중치 적용)
  - 이유: 학습 시에는 쌍으로 비교하지만, 추론 시에는 사진 각각에 독립적으로 적용해야 하므로 모델 자체는 "사진 하나 → 점수 하나"인 단일 함수여야 함
- 결정: `margin_ranking_loss`를 기본, `ranknet_loss`를 대안으로 함께 구현
  - 이유: margin loss가 구현이 단순해 초기 baseline에 적합. 학습이 안정화된 후에는 gradient가 더 부드러운 ranknet loss로 전환할 예정 (Notion 설계 문서 5절)
- 결정: `filter_by_fitness`/`suggest_removal`이 순서(`argsort`)를 만들지 않음
  - 이유: 실제 배치 순서 결정은 이후 "전이 비용 최소화" 단계의 책임으로 명확히 분리 — 이 모듈은 적합도 점수와 제외 후보만 만든다
- 결정: `suggest_removal`은 자동 삭제가 아니라 후보 목록(사진 id, 점수)만 반환
  - 이유: 설계 문서 요구사항 — 시스템이 임의로 사진을 지우지 않고, 근거(점수)와 함께 사용자에게 제시해 최종 결정은 사용자가 함
- 결정: 입력 차원 11 = CLIP 유사도(1, `clip.py`) + 색감 피처(10, `features.py`)
  - 이유: Notion 설계 문서의 "약 11차원" 스펙에 맞춤. 색감 피처 세부 구성은 `Color_features.md` 참고
- 결정(초기, 이후 대체됨): 학습 쌍(pos/neg) 라벨 데이터를 `Ai/data/label_pairs.json`에 `{theme, pos, neg}` 리스트로 저장
  - 이유: 사용자 유지/제외 행동으로부터 자동 수집하는 파이프라인(TODO)이 아직 없어, 학습 루프 자체가 동작하는지부터 검증하기 위해 `samples/`의 사진들로 "미니멀한 감성 사진" 테마 기준 12쌍을 수동 라벨링. pos/neg는 절대 점수가 아니라 상대 비교이므로 CSV보다 스키마 확장(테마 추가 등)이 쉬운 JSON을 선택
  - **대체(2026-09-15)**: 실사용자 행동 기반 수집(Notion 설계 문서 8절)을 기다리는 대신, Unsplash API로 규모를 키운 `{theme, pos, neg}` 트리플렛(45쌍, `Ai/data/unsplash/pairs.csv`)으로 전환(이슈 #9) — 원본 이미지 대신 미리 계산한 피처(`photos.csv`)를 `photo_id`로 조회하는 구조라 CSV를 사용. `Ai/data/label_pairs.json`은 삭제됨, 자세한 설계는 `docs/ai/Collect_unsplash_data.md` 참고
- 결정: `Ai/train_mlp.py`는 미니배치 없이 매 epoch 전체 쌍을 한 번에 통과시키는 풀배치(full-batch) 학습, optimizer는 Adam(lr=1e-3), epochs=100 기본값
  - 이유: 라벨이 12쌍뿐이라 미니배치로 쪼갤 이유가 없고, 지금 목표는 최적 하이퍼파라미터 탐색이 아니라 학습 루프(forward → loss → backward → step)가 실제로 도는지 검증하는 것이라 합리적인 기본값을 그대로 사용. 데이터가 늘어나면 미니배치/에폭 수 재검토 필요
- 결정: `Ai/evaluate_mlp.py`의 `split_pairs`는 랜덤 분할이 아니라 앞 9쌍(train)/뒤 3쌍(val) 고정 분할
  - 이유: 데이터가 12쌍뿐이라 랜덤 분할이든 고정 분할이든 val 3쌍 안에서의 결과가 크게 달라지지 않고, 고정 분할이 구현이 단순하고 실행마다 결과가 재현 가능함. 데이터가 늘어나면 랜덤/k-fold 분할 재검토 필요
- 결정: loss curve/점수 분포 그래프는 `docs/ai/output/`에 PNG로 저장 (matplotlib, `Agg` 백엔드)
  - 이유: 문서(`docs/ai/`)와 나란히 두어 실측 결과를 함께 확인하기 쉽게 함. git 커밋 여부는 아직 미정 — 실행마다 그래프 값이 달라져 커밋 diff가 잦아지면 `.gitignore` 전환 재검토 (`Ai/CLAUDE.md` 참고)
- 결정(버그 수정): `filter_by_fitness`/`suggest_removal` 내부에 `inference_scores` 헬퍼를 추가해 `model.eval()` 후 원래 학습 모드로 복원
  - 이유: 최초 구현 시 `torch.no_grad()`만 사용했는데, 이는 그래디언트 계산만 끌 뿐 `Dropout`은 여전히 활성 상태로 남음. 동일한 11d 입력으로 `filter_by_fitness`와 `suggest_removal`을 연달아 호출했을 때 점수가 서로 달라지는 것을 실측(샘플 사진 2장)으로 확인해 발견 → eval 모드 전환 없이는 추론 결과가 결정적이지 않음
- 결정: `inference_scores`는 원래 모듈 내부 전용(`_inference_scores`)이었으나, validation ranking accuracy 계산(`Ai/evaluate_mlp.py`)에서도 동일한 "eval 모드 전환 후 복원" 로직이 필요해져 공개 함수로 전환(`_` 제거)
  - 이유: 같은 로직을 `evaluate_mlp.py`에 다시 구현하면 위 버그(모드 미복원)가 재발할 수 있음 — 단일 소스를 재사용해 그 위험을 원천 차단

- 결정(변경, 2026-11-02): 모델 하나를 흑백 데이터로만 학습해 모든 테마에 쓰던 방식을 **테마마다 모델을 따로 학습**하는 방식으로 바꿈(#23)
  - 이유: 실제 사진을 어떤 테마로 보내도 전부 제거 후보로 나오는 문제를 분석해 보니, 흑백 사진(pos)과 컬러 사진(neg)만 비교하는 데이터라 "채도가 낮을수록 높은 점수"만 배워도 정답률 100%가 나왔음. 성분 하나씩을 데이터 범위 끝에서 끝까지 바꿔 보니 평균 채도는 점수를 −0.51 움직이는데 테마 정보가 들어오는 유일한 통로인 `clip_sim`은 +0.003뿐이었고, 그 결과 비비드·골든아워 사진은 자기 테마로 채점해도 0/30 통과. 테마별로 가르는 기준이 다르다는 것도 확인(흑백은 채도, 비비드는 색상 분포가 거의 완벽하게 가름, 골든아워는 단일 성분으론 안 되고 조합해야 AUC 0.87)
  - 검토한 다른 선택지: (B) 모델 하나에 테마 one-hot을 입력으로 추가(11d -> 14d) — 한 모델이 세 기준을 다 배워야 하는데 테마당 30장으로는 빠듯하고 입력 스키마가 바뀜. (C) `clip_sim`을 "이 테마 - 세 테마 평균"인 상대값으로 바꿈 — 효과가 불확실해 실험이 필요. 프론트 테마가 3개 프리셋으로 고정이라 "새 테마를 바로 못 다룸"이라는 A안의 단점이 지금은 문제가 안 돼 A를 택함
- 결정: 학습 데이터는 테마마다 "이 테마 사진 = pos, 다른 두 테마 사진 = neg" (`dataset.build_theme_pairs`), `clip_sim`은 neg 사진도 **이 테마 문장 기준**으로 잰 값(`cross_clip_sim.csv`)
  - 이유: 흑백 모델에게 "색이 없으면 좋다"는 이제 지름길이 아니라 정답이고, 비비드 모델은 반대로 배워야 함. `clip_sim`을 수집 테마 기준 값 그대로 쓰면 모든 사진이 "자기 테마와 비슷함"(0.27~0.28)이라 테마를 가르는 신호가 사라짐
- 결정: 기준값을 0.35 하나로 고정하지 않고 **테마별로 학습 때 검증 사진으로 정해 `scoring_thresholds.json`에 함께 저장** (`evaluate_mlp.best_threshold`)
  - 이유: pairwise ranking으로 학습해 점수의 절대 크기에 정해진 의미가 없고, 실제로 모델마다 점수 범위가 달라 기준값이 −0.374 / 0.317 / −0.028로 나옴 — 0.35 하나를 쓰면 세 모델 모두 대부분 탈락. "점수 하위 N%는 빼기 추천" 같은 순위 기준은 모든 사진이 테마에 맞아도 누군가는 빠지게 돼 택하지 않음. 정확도가 같은 후보가 여럿이면 양옆 점수 간격이 가장 넓은 곳을 골라 새 사진 점수가 조금 흔들려도 판정이 덜 뒤집히게 함
- 결정: `THEME_KEYS`를 `collect_unsplash_data.THEMES` 옆이 아니라 `mlp.py`에 둠
  - 이유: `collect_unsplash_data.py`가 `mlp.py`를 import하므로 반대로 가져오면 순환 import. 대신 두 목록이 어긋나면 실패하는 테스트(`test_theme_keys_cover_exactly_the_collected_themes`)로 묶음
- 결정: `evaluate_mlp.py`는 학습 seed를 고정(`TRAIN_SEED = 0`)하고 세 테마 결과를 `docs/ai/output/theme_summary.png` 한 장(loss curve / 검증 정확도 / 모델 x 사진 테마 통과표)으로 저장
  - 이유: 재실행해도 같은 체크포인트·그래프가 나와야 코드 변경의 효과만 비교할 수 있음. 세 결과를 한 장에 모아 학습이 됐는지·처음 보는 사진도 맞히는지·테마별로 갈리는지를 한눈에 확인

## ⚙️ 동작 흐름

```python
# 1) 사진 + 테마 문장 -> 11d 입력 피처
feat = build_feature_vector(image, theme_text)

# 2) 학습: 두 사진(pos/neg)을 같은 모델에 통과시켜 점수 비교
score_pos, score_neg = rank_forward(model, feat_pos, feat_neg)
loss = margin_ranking_loss(score_pos, score_neg)

# 3) 추론: 요청 테마의 모델·기준값으로 점수 계산 후 기준값 미만은 제외 "제안"
model = load_checkpoint(theme_checkpoint_path(theme_text))
threshold = load_thresholds()[THEME_KEYS[theme_text]]
keep_ids, remove_candidates = suggest_removal(model, feats, photo_ids, threshold=threshold)
# remove_candidates = [(photo_id, score), ...] -> 사용자가 제외/유지 직접 선택
```

## ⚠️ 알려진 제약 / TODO

- [x] 학습 루프는 `Ai/train_mlp.py`에 구현 (Adam + `margin_ranking_loss`, 풀배치). 원래 라벨 데이터는 수동 라벨링(12쌍, `label_pairs.json`)이었음
- [x] Validation ranking accuracy 측정 및 loss curve/점수 분포 시각화는 `Ai/evaluate_mlp.py`에 구현
- **원인 규명 + 재정비(2026-09-22)**: 한때 `Ai/data/unsplash/pairs.csv`(Unsplash 준자동 수집, 테마 3개를 돌아가며 pos/neg 구성)로 `dataset.py`/`evaluate_mlp.py`를 전환해 재학습해봤으나(val ranking accuracy 55.56~77.78%로 낮게 나옴), 원인을 분석해보니 **데이터 품질이 아니라 모델 구조 자체가 이 문제와 안 맞았음** — `ScoringMLP`는 사진 한 장의 절대 점수를 매기는 모델인데, "테마를 돌아가며 pos/neg 구성"하는 데이터는 같은 사진이 어떤 트리플렛에서는 pos, 다른 트리플렛에서는 neg로 동시에 등장하는 구조적 모순이 있음(테마를 색감이 더 뚜렷하게 갈리게 바꿨더니 오히려 정확도가 더 떨어진 게 근거). `ScoringMLP`는 원래 설계대로 **"고정된 테마 하나" 기준 절대 점수**(`filter_by_fitness`, `suggest_removal`)에만 쓰는 게 맞고, "사진 두 장이 서로 어울리는가"는 별도의 페어와이즈 모델(`Ai/transition_cost_model.py`, val 93.33%로 훨씬 잘 됨)로 분리함. 처음엔 `Ai/data/label_pairs.json`(초기 프로토타입 시절 "미니멀한 감성 사진" 테마, 지금 방향과 안 맞음)로 되돌리는 걸 고려했으나, `Ai/build_scoring_theme_data.py`를 새로 만들어 **Unsplash 테마 중 하나(`black and white monochrome photography`)를 고정 테마로 삼아** 재구성 — pos는 그 테마로 수집된 사진(clip_sim 그대로), neg는 다른 테마 사진을 원본에서 다시 받아 그 고정 테마 기준으로 clip_sim만 재계산. 결과: `Ai/data/unsplash/scoring_pairs.csv`(15쌍, 단일 고정 테마) 기준 **val ranking accuracy 100%(3/3)** — 구조적 모순만 없애면 Unsplash 데이터로도 잘 됨을 재확인. 체크포인트는 `Ai/checkpoints/scoring_mlp.pt`에 저장(`save_checkpoint`/`load_checkpoint` 신규). 자세한 경위는 `docs/ai/Transition_cost_model.md`, `docs/ai/Build_scoring_theme_data.md` 참고
- [ ] 사용자 유지/제외 행동으로부터 학습 쌍(pos, neg)을 수집·저장하는 파이프라인 미구현 (Notion 설계 문서 8절)
- [x] ~~`threshold=0.35`는 설계 문서의 예시값을 그대로 사용 중~~ — 테마별로 검증 사진에서 정한 기준값으로 대체(2026-11-02, #23). `filter_by_fitness`/`suggest_removal`의 기본값 0.35는 호환용으로만 남아 있고 백엔드는 항상 테마별 값을 넘김
- [x] ~~단일 모델이 테마를 구분하지 못함(어떤 테마든 흑백 사진만 통과)~~ — 테마별 모델로 해소(2026-11-02, #23)
- [ ] 검증 사진이 테마당 6장뿐이라 정확도·기준값이 사진 한두 장에 크게 흔들림 — 데이터를 늘리면 재검토
- [ ] 프론트 테마 프리셋에 없는 새 테마는 데이터 수집부터 학습까지 다시 해야 지원 가능
- [ ] Precision/Recall 등 추가 평가 지표 측정 로직 미구현 (ranking accuracy는 구현됨)
- [ ] 순서 자체의 품질(Kendall's Tau 등)은 설계상 이 모듈 책임이 아니라 배치 단계 몫 — 범위 밖

## 🧪 실전 테스트 결과 (2026-11-02)

`python Ai/evaluate_mlp.py` (테마당 학습 1,152쌍, 검증은 학습에 쓰지 않은 사진 18장)

| 모델 | 학습 loss | 순위 정확도 | 기준값 | 기준값 정확도 |
|---|---|---|---|---|
| 흑백 | 0.183 -> 0.000 | 97.2% | −0.374 | 94.4% |
| 비비드 | 0.164 -> 0.001 | 94.4% | 0.317 | 94.4% |
| 골든아워 | 0.197 -> 0.001 | 100% | −0.028 | 100% |

검증 사진 통과 수(테마당 6장): 흑백 모델 5/0/0, 비비드 모델 1/6/0, 골든아워 모델 0/0/6 — 대각선만 통과. 학습 seed를 5개로 바꿔도 흑백 순위 정확도만 93.1~97.2% 사이로 흔들리고 나머지는 같음. 모델이 보는 성분: 흑백은 채도(−0.80), 비비드는 붉은~노란 비율(−0.67)과 채도(+0.55), 골든아워는 붉은~노란 비율(+0.30)과 `clip_sim`(+0.11) — 색만으로 가르기 어려운 골든아워에서 교차 `clip_sim`이 실제로 쓰임

`samples/` 실제 사진 재측정(백엔드 `/arrange` 경로): 초록 나무 사진·장미 사진은 비비드에서만, 물 위 노을 사진은 골든아워에서만 통과하고 셋 다 흑백에서는 탈락. 수정 전에는 테마를 바꿔도 점수가 ±0.01만 움직이고 모든 테마에서 전부 탈락했음

## 🧪 사용 예시

```bash
python Ai/mlp.py photo.jpg "미니멀한 감성 사진"
# 출력 예: feature_vector(11d): [...]
#          raw score (untrained): -0.1165
```

## 🔗 참고

- Notion "MLP 모델 설계" 문서(흐름도 > MLP 모델 설계)
- `docs/ai/Color_features.md` — 색감 피처(10d) 세부 설계
- `docs/ai/Clip_embedding.md` — CLIP 유사도(1d) 콜드스타트 baseline
- 관련 이슈: feature/mlp-적합도-스코어링/1
