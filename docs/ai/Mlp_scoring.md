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
- 결정(버그 수정): `filter_by_fitness`/`suggest_removal` 내부에 `_inference_scores` 헬퍼를 추가해 `model.eval()` 후 원래 학습 모드로 복원
  - 이유: 최초 구현 시 `torch.no_grad()`만 사용했는데, 이는 그래디언트 계산만 끌 뿐 `Dropout`은 여전히 활성 상태로 남음. 동일한 11d 입력으로 `filter_by_fitness`와 `suggest_removal`을 연달아 호출했을 때 점수가 서로 달라지는 것을 실측(샘플 사진 2장)으로 확인해 발견 → eval 모드 전환 없이는 추론 결과가 결정적이지 않음

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

- [ ] 아직 학습 루프(옵티마이저, 데이터로더, 쌍 데이터 구성)는 미구현 — 현재는 랜덤 초기화 가중치로, 점수 자체는 의미 없음(피처 파이프라인과 forward shape만 검증됨)
- [ ] 사용자 유지/제외 행동으로부터 학습 쌍(pos, neg)을 수집·저장하는 파이프라인 미구현 (Notion 설계 문서 8절)
- [ ] `threshold=0.35`는 설계 문서의 예시값을 그대로 사용 중 — 실 데이터 기반 검증 필요, "상대 기준(그룹 내 하위 N%)" 방식으로 전환 검토 (Notion 설계 문서 7절)
- [ ] Pairwise accuracy, Precision/Recall 등 평가 지표 측정 로직 미구현
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
