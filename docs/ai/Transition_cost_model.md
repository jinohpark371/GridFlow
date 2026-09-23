# 전이 비용 학습 모델 (`Ai/transition_cost_model.py`, `Ai/evaluate_transition_cost_model.py`)

> 작성일: 2026-09-22 · 작성자: 진오 · 관련 이슈: #13

## 📌 목적
사진 두 장을 같이 보고 "이 둘이 나란히 놓이면 자연스러운가"를 직접 예측하는 **페어와이즈(pairwise) 모델**을 학습한다. `transition.py`(별도 브랜치, 삭제됨)의 고정 가중치 `transition_cost(fi, fj) = w1*|hue차이| + w2*|밝기차이| + w3*|채도차이|`를, 11차원 피처 전체를 보고 비선형으로 판단하는 학습 가능한 버전으로 대체한다.

## 🧭 파이프라인 상 위치
Unsplash 데이터 수집(`collect_unsplash_data.py`)의 `photos.csv`를 입력으로 쓰는 2단계 학습 모델. `mlp.py`의 `ScoringMLP`(사진 한 장 → 테마 적합도 점수, 절대 점수형)와는 별개 모델 — 서로 다른 문제를 풀기 때문에 재사용하지 않는다(아래 "설계 결정" 참고).

- Layer: Layer 2 · 배치(순서 결정) — 전이 비용 학습
- 이전 단계: `Ai/collect_unsplash_data.py`가 만든 `photos.csv`(사진별 11차원 피처 + 테마)
- 다음 단계: 저장된 체크포인트(`Ai/checkpoints/transition_cost_model.pt`)를 백엔드(이슈 #8)에서 로딩해 서빙. 실제 배치 파이프라인(`arrange_photos`, 별도 브랜치에서 삭제됨)과의 재연동은 범위 밖

## 🔧 입출력 스펙

| 함수 | 입력 | 출력 | 설명 |
|---|---|---|---|
| `TransitionCostModel.forward` | `diff: torch.Tensor` (batch, 11) | `torch.Tensor` (batch, 1) | 피처 차이 벡터 → 비용 점수 하나 |
| `pair_cost` | `model, feat_a, feat_b` (각 (batch, 11)) | `torch.Tensor` (batch,) | 사진 두 장의 피처 → `\|A-B\|` → 비용. A/B 순서를 바꿔도 값이 같음(대칭) |
| `train` | `feat_pos_a, feat_pos_b, feat_neg_a, feat_neg_b` | `(TransitionCostModel, loss_history)` | pos_pair(같은 테마) 비용 < neg_pair(다른 테마) 비용이 되도록 풀배치 학습 |
| `dataset.load_photo_pool` | `path`(기본 `photos.csv`) | `(photo_id -> 피처, 테마 -> photo_id 리스트)` | 테마별 그룹 정보까지 한 번에 로딩 |
| `dataset.sample_theme_pair_features` | `features, by_theme, n_pairs, rng` | `(feat_pos_a, feat_pos_b, feat_neg_a, feat_neg_b)` | 같은 테마 2장(pos_pair)/다른 테마 2장(neg_pair)을 무작위 샘플링 |
| `save_checkpoint` | `model, path`(기본 `Ai/checkpoints/transition_cost_model.pt`) | `None` | 학습된 가중치(`state_dict`) 저장 |
| `load_checkpoint` | `path`(기본 위와 동일) | `TransitionCostModel` (eval 모드) | 저장된 가중치를 불러와 즉시 추론 가능한 모델로 복원 |

## 🧠 설계 결정과 이유

- 결정: `ScoringMLP`를 재사용하지 않고 `TransitionCostModel`을 별도 클래스로 새로 만듦
  - 이유: 처음엔 기존 `Ai/data/unsplash/pairs.csv`({theme, pos, neg})로 `ScoringMLP`를 재학습시켜봤는데 val ranking accuracy가 55~78%로 낮았다. 원인을 짚어보니 **모델 구조 자체가 문제**였음 — `ScoringMLP`는 사진 한 장의 절대 점수를 매기는데, 데이터는 테마 3개를 돌아가며 "이번 테마의 사진=pos, 다른 테마 사진=neg"로 구성돼 있어서, **같은 사진이 어떤 트리플렛에서는 pos(점수를 높여야 함), 다른 트리플렛에서는 neg(점수를 낮춰야 함)로 동시에 등장**하는 모순이 생김. 테마 색감을 더 뚜렷하게 갈라도(흑백 vs 컬러풀 vs 따뜻한 톤) 오히려 정확도가 더 떨어진 것(55.56%)이 이 가설을 뒷받침함 — 모순이 더 도드라졌기 때문. `ScoringMLP`는 원래 "고정된 테마 하나" 기준 절대 점수용으로 설계된 모델이라, 테마 필터링(`filter_by_fitness`, `suggest_removal`)에는 여전히 맞는 구조이고 그 용도로는 그대로 둠
  - 대안(페어와이즈)으로 바꾸자 val 93.33%로 크게 개선됨(비교: 실측 결과 아래 참고)
- 결정: 모델 입력을 `feat_a`, `feat_b` 그대로 concat하는 대신 `|feat_a - feat_b|`(절댓값 차이)로 만듦
  - 이유: 전이 비용은 "A 다음에 B를 놓을 때"와 "B 다음에 A를 놓을 때"가 같아야 하는 대칭적인 양인데(순서 상관없이 두 사진이 얼마나 안 어울리는지), `\|A-B\| = \|B-A\|`라 구조적으로 대칭이 보장됨. concat(`[A, B]`)을 썼다면 순서 바뀐 데이터도 같이 학습시켜야 대칭성이 생기는데, 차이 벡터는 그럴 필요가 없음. 원래 `transition_cost` 공식(`w1*|hue차이|+...`)도 절댓값 차이 기반이라 자연스러운 일반화이기도 함
- 결정: pos_pair(비용 낮아야 함)/neg_pair(비용 높아야 함) 학습에 `mlp.margin_ranking_loss`를 그대로 재사용(`-cost`를 점수로 취급)
  - 이유: "점수는 pos가 neg보다 커야 한다"는 기존 함수를 그대로 쓰되, "비용은 pos가 neg보다 작아야 한다"로 부호만 뒤집으면 똑같은 수식이라 새로 구현할 필요가 없었음
- 결정: 학습 데이터를 `pairs.csv`({theme, pos, neg} 트리플렛)가 아니라 `photos.csv`에서 직접 샘플링(`sample_theme_pair_features`)
  - 이유: 트리플렛 구조는 "사진 한 장 vs 테마"를 비교하던 옛 스키마의 흔적이라 페어와이즈 학습엔 안 맞음. `photos.csv`(사진별 테마 라벨)만 있으면 "같은 테마 2장"/"다른 테마 2장"을 그때그때 뽑을 수 있어 더 유연함 — `pairs.csv`는 더 이상 이 학습에 쓰이지 않음(트리플렛 스키마 자체가 필요 없어짐)
- 결정: train 60쌍/val 15쌍을 매번 새로 무작위 샘플링(고정 분할 파일 없음), `SEED=42`로 재현성만 확보
  - 이유: `photos.csv`(테마당 30장, 총 90장 — `filter_representative_photos`로 거른 15장은 `pairs.csv` 트리플렛에만 쓰이고 `photos.csv` 자체는 전체를 담음)에서 조합 가능한 같은/다른 테마 쌍이 매우 많아(같은 테마 쌍만 해도 테마당 `30*29/2=435`개) 굳이 고정 파일로 나눌 필요 없이 그때그때 샘플링. 시드만 고정해 실행마다 같은 결과가 나오게 함
- 결정: `save_checkpoint`/`load_checkpoint`는 `evaluate_transition_cost_model.py`가 val 정확도까지 확인한 모델(train 60쌍만 학습, val 15쌍은 검증용으로 남김)을 그대로 저장 — 저장 전 val을 합쳐 재학습하는 별도 단계는 두지 않음
  - 이유: 지금 목표는 "페어와이즈 구조가 실제로 통하는지" 검증이라, val을 버리지 않고 쓰는 최적화보다 검증된 모델을 그대로 남기는 쪽이 단순함. `torch.load`는 `weights_only=True`로 호출 — 신뢰 못 하는 체크포인트를 불러올 때 임의 코드 실행을 막는 최신 권장 설정

## ⚙️ 동작 흐름

```python
features, by_theme = load_photo_pool()  # photos.csv -> (photo_id->피처, 테마->id 리스트)
rng = random.Random(SEED)

train_pos_a, train_pos_b, train_neg_a, train_neg_b = sample_theme_pair_features(features, by_theme, 60, rng)
model, loss_history = train(train_pos_a, train_pos_b, train_neg_a, train_neg_b)

cost = pair_cost(model, feat_a, feat_b)  # 사진 두 장 -> 비용 점수 (낮을수록 잘 어울림)
```

## 🧪 실전 테스트 결과 (2026-09-22)

- 데이터: `Ai/data/unsplash/photos.csv`(테마 3개 — 흑백/컬러풀/따뜻한 톤, 테마당 30장, 총 90장)
- train 60쌍 / val 15쌍, 100 epoch: loss 0.2016 → 0.0121로 매끄럽게 수렴
- **val cost ranking accuracy: 93.33%(14/15)** — `cost(pos_pair) < cost(neg_pair)`가 거의 항상 성립
- 비용 분포 산점도(`docs/ai/output/transition_cost_distribution.png`)에서 pos_pair는 대부분 음수, neg_pair는 대부분 양수로 뚜렷하게 분리됨(겹치는 건 1쌍)
- 비교: 같은 데이터로 `ScoringMLP`(절대 점수형)를 재사용했을 때는 55.56~77.78% 수준 — 페어와이즈 구조 전환이 핵심 개선 요인이었음을 뒷받침

## ⚠️ 알려진 제약 / TODO

- [x] 학습된 `TransitionCostModel` 저장 — `save_checkpoint`/`load_checkpoint` 추가, `Ai/checkpoints/transition_cost_model.pt`(약 41KB)로 커밋됨
- [ ] 실제 배치 파이프라인(`arrange_photos`, 별도 브랜치에서 삭제됨)과의 연동은 범위 밖 — 재구현 필요
- [ ] val 15쌍은 통계적으로 크지 않음(한 쌍 틀리면 93.33%→86.67%) — 데이터가 더 쌓이면 재검증 필요
- [ ] `Ai/data/unsplash/pairs.csv`는 이제 이 모델 학습에 쓰이지 않음 — `mlp.py` 쪽 재학습 실험이 실은 잘못된 전제였다는 게 이번에 확인됨(`docs/ai/Mlp_scoring.md` 참고), `pairs.csv`/트리플렛 스키마 자체를 유지할지 재검토 필요

## 🔗 참고

- `docs/ai/Collect_unsplash_data.md` — `photos.csv` 생성 과정, 테마 3개(흑백/컬러풀/따뜻한 톤) 선정 이유
- `docs/ai/Mlp_scoring.md` — `ScoringMLP`가 왜 이 문제엔 안 맞는지, 원래 어떤 문제(테마 필터링)에 맞는 모델인지
- `docs/ai/Dataset.md` — `load_photo_pool`/`sample_theme_pair_features` 추가 배경
- GitHub 이슈 #13 — MLP val ranking accuracy 개선 작업에서 파생됨
