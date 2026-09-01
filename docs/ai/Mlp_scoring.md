# MLP 테마 적합도 스코어링 (`Ai/mlp.py`)

> 작성일: 2026-08-24 · 작성자: 진오 · 관련 이슈: feature/mlp-적합도-스코어링/1

## 📌 목적
사진이 선택된 테마에 얼마나 적합한지 **상대적으로** 비교하도록 학습되는 Siamese MLP. 순서를 직접 정하지 않고 ①부적합 사진의 제외를 제안하고 ②유지 사진에 점수(가중치)를 부여하는 역할만 담당한다.

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
- 결정: 학습 쌍(pos/neg) 라벨 데이터는 `Ai/data/label_pairs.json`에 `{theme, pos, neg}` 리스트로 저장
  - 이유: 사용자 유지/제외 행동으로부터 자동 수집하는 파이프라인(TODO)이 아직 없어, 학습 루프 자체가 동작하는지부터 검증하기 위해 `samples/`의 사진들로 "미니멀한 감성 사진" 테마 기준 12쌍을 수동 라벨링. pos/neg는 절대 점수가 아니라 상대 비교이므로 CSV보다 스키마 확장(테마 추가 등)이 쉬운 JSON을 선택. 추후 사용자 행동 기반 수집으로 전환해도 같은 포맷을 재사용 가능
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

## ⚙️ 동작 흐름

```python
# 1) 사진 + 테마 문장 -> 11d 입력 피처
feat = build_feature_vector(image, theme_text)

# 2) 학습: 두 사진(pos/neg)을 같은 모델에 통과시켜 점수 비교
score_pos, score_neg = rank_forward(model, feat_pos, feat_neg)
loss = margin_ranking_loss(score_pos, score_neg)

# 3) 추론: 적합도 점수 계산 후 threshold 미만은 제외 "제안"
keep_ids, remove_candidates = suggest_removal(model, feats, photo_ids, threshold=0.35)
# remove_candidates = [(photo_id, score), ...] -> 사용자가 제외/유지 직접 선택
```

## ⚠️ 알려진 제약 / TODO

- [x] 학습 루프는 `Ai/train_mlp.py`에 구현 (Adam + `margin_ranking_loss`, 풀배치). 실측(라벨 12쌍, 100 epoch): loss 0.1836 → 0.0000 — 데이터가 12쌍뿐이라 완전히 암기(overfit)한 수준이지만, 학습 루프 자체가 정상 동작함은 확인됨. 일반화 성능(ranking accuracy 등)은 아래 항목에서 별도 검증 필요
- [x] Validation ranking accuracy 측정 및 loss curve/점수 분포 시각화는 `Ai/evaluate_mlp.py`에 구현 (train 9쌍/val 3쌍 고정 분할). 실측: val ranking accuracy 100%(3/3), loss curve는 20 epoch 안에 0 근처로 수렴, 점수 분포 산점도에서 val 쌍 3개 모두 pos > neg로 분리됨 (`docs/ai/output/loss_curve.png`, `docs/ai/output/score_distribution.png`) — 다만 val이 3쌍뿐이라 100%는 통계적으로 약함(한 쌍만 틀려도 66%로 하락), 데이터가 12쌍뿐인 근본적 한계를 벗어나지 못함
- [ ] 사용자 유지/제외 행동으로부터 학습 쌍(pos, neg)을 수집·저장하는 파이프라인 미구현 (Notion 설계 문서 8절)
- [ ] `threshold=0.35`는 설계 문서의 예시값을 그대로 사용 중 — 실 데이터 기반 검증 필요, "상대 기준(그룹 내 하위 N%)" 방식으로 전환 검토 (Notion 설계 문서 7절)
- [ ] Precision/Recall 등 추가 평가 지표 측정 로직 미구현 (ranking accuracy는 구현됨)
- [ ] 순서 자체의 품질(Kendall's Tau 등)은 설계상 이 모듈 책임이 아니라 배치 단계 몫 — 범위 밖

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
