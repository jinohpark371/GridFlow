# 트리플렛/피처 로딩 (`Ai/dataset.py`)

> 작성일: 2026-08-27 · 최종 수정: 2026-09-15 · 작성자: 진오 · 관련 이슈: test/mlp-학습-파이프라인/4, #9

## 📌 목적
`Ai/data/unsplash/pairs.csv`의 `{theme, pos, neg}` 트리플렛을 읽고, `Ai/data/unsplash/photos.csv`에 미리 계산돼 있는 11차원 피처를 `photo_id`로 조회해 학습 루프에 바로 넣을 수 있는 배치 텐서로 만든다.

## 🧭 파이프라인 상 위치
"MLP 모델 설계" 단계와 학습 스크립트(`Ai/train_mlp.py`) 사이의 데이터 로더.

- Layer: Layer 1 · 테마 적합도 스코어링 > 학습 데이터 로딩
- 이전 단계: `Ai/collect_unsplash_data.py`가 만든 `photos.csv`(피처)/`pairs.csv`(트리플렛)
- 다음 단계: 학습 스크립트(`Ai/train_mlp.py`) — `rank_forward` + `margin_ranking_loss`, 평가 스크립트(`Ai/evaluate_mlp.py`)

## 🔧 입출력 스펙

| 함수 | 입력 | 출력 | 설명 |
|---|---|---|---|
| `load_label_pairs` | `path` (기본값 `Ai/data/unsplash/pairs.csv`) | `list[dict]` | `{theme, pos, neg}` 트리플렛을 그대로 반환 (`pos`/`neg`는 `photo_id`) |
| `load_photo_features` | `path` (기본값 `Ai/data/unsplash/photos.csv`) | `dict[str, np.ndarray]` | `photo_id -> 11차원 피처 벡터` 딕셔너리 |
| `build_pair_features` | `pairs: list[dict], photo_features: dict \| None` | `(feats_pos, feats_neg)` (각 `torch.Tensor`, shape `(N, 11)`) | 트리플렛의 `pos`/`neg` id로 `photo_features`를 조회해 배치로 묶음 |
| `load_photo_pool` | `path`(기본값 `photos.csv`) | `(photo_id -> 11d 피처, 테마 -> photo_id 리스트)` | `transition_cost_model.py`의 페어와이즈 샘플링용 — 테마별 그룹 정보까지 한 번에 로딩 |
| `sample_theme_pair_features` | `features, by_theme, n_pairs, rng` | `(feat_pos_a, feat_pos_b, feat_neg_a, feat_neg_b)` (각 `(n_pairs, 11)`) | 같은 테마 2장(pos_pair)/다른 테마 2장(neg_pair)을 무작위 샘플링 |

## 🧠 설계 결정과 이유

- 결정(변경): 사진마다 `build_feature_vector`를 다시 호출하는 대신, `photos.csv`에 미리 계산된 피처를 `photo_id`로 조회
  - 이유: 원래 `Ai/data/label_pairs.json`(수동 라벨링 12쌍) 시절엔 매번 이미지를 열어 CLIP을 재계산했는데, Unsplash 데이터로 전환하면서(이슈 #9) 이미지 자체를 로컬에 저장하지 않기로 결정 — 애초에 다시 열 이미지가 없어서, `collect_unsplash_data.py`가 수집 시점에 한 번 계산해 둔 피처를 재사용하는 구조로 바뀜. 부수적으로 이전 TODO였던 "같은 사진이 여러 쌍에 등장하면 CLIP을 반복 계산"하는 비효율도 자연히 해소됨(딕셔너리 조회 1회로 끝)
- 결정: `label_pairs.json`(JSON, 이미지 경로 기반) 대신 `pairs.csv`(CSV, `photo_id` 기반)를 읽음 — `load_label_pairs` 함수명은 유지
  - 이유: `train_mlp.py`/`evaluate_mlp.py`가 이 함수명으로 import하고 있어, 이름을 유지하면 두 스크립트를 전혀 건드리지 않고 데이터 소스만 교체할 수 있음(사용자가 "dataset.py의 로딩 로직만 바꾸자"고 명시적으로 요청)
- 결정: `build_pair_features`가 `photo_features` 딕셔너리를 선택적 인자로 받음(없으면 기본 경로에서 로딩)
  - 이유: 테스트에서 실제 CSV 파일 없이도 가짜 피처 딕셔너리를 주입해 순수 로직만 검증할 수 있게 하기 위해 — 이 덕분에 이 모듈은 더 이상 CLIP/네트워크에 의존하지 않아 `tests/ai/test_dataset_integration.py`(통합 테스트)가 필요 없어짐(삭제)
- 결정: `feats_pos`/`feats_neg`를 각각 리스트로 모은 뒤 `np.stack`으로 `(N, 11)` 배열을 만들고 `torch.from_numpy`로 변환 (유지)
  - 이유: `rank_forward`/`margin_ranking_loss`가 배치 입력을 기대하므로, 쌍 하나하나를 개별 처리하지 않고 N개를 한 번에 forward pass 돌릴 수 있는 형태로 미리 묶어둠

## ⚙️ 동작 흐름

```python
pairs = load_label_pairs()  # Ai/data/unsplash/pairs.csv -> [{theme, pos, neg}, ...]
feats_pos, feats_neg = build_pair_features(pairs)  # photos.csv에서 조회 -> (N, 11), (N, 11)

# 학습 스크립트(Ai/train_mlp.py)에서:
# model, loss_history = train(feats_pos, feats_neg)
```

## ⚠️ 알려진 제약 / TODO

- [x] ~~같은 사진이 여러 쌍에 등장해도 그때마다 CLIP 임베딩을 다시 계산함~~ — Unsplash 데이터 전환으로 해소(피처를 한 번만 계산해 CSV에 저장, 이후로는 조회만)
- [ ] 라벨 파일 하나(`Ai/data/unsplash/pairs.csv`)만 지원 — 여러 라벨 파일을 합치거나 증분 라벨을 병합하는 기능은 없음
- [x] 학습 스크립트는 `Ai/train_mlp.py`, 평가 스크립트는 `Ai/evaluate_mlp.py`에 구현됨 — 이 모듈은 그 입력 텐서를 만드는 데까지만 책임지는 역할 분리 유지
- **주의(2026-09-22)**: `load_label_pairs`/`build_pair_features`(트리플렛 기반)로 `ScoringMLP`를 재학습시키는 실험은 구조적으로 잘못된 전제였음이 확인됨 — 자세한 이유는 `docs/ai/Mlp_scoring.md`, `docs/ai/Transition_cost_model.md` 참고. `load_photo_pool`/`sample_theme_pair_features`(페어와이즈)만 계속 사용 권장

## 🧪 사용 예시

```bash
python Ai/dataset.py
# 출력 예: loaded 45 pairs -> feats_pos (45, 11), feats_neg (45, 11)
```

## 🔗 참고

- `docs/ai/Collect_unsplash_data.md` — `photos.csv`/`pairs.csv`를 만드는 수집 스크립트, 스키마 설계 이유
- `docs/ai/Mlp_scoring.md` — `build_feature_vector`(11d) 세부 설계
- `Ai/data/unsplash/photos.csv`, `pairs.csv` — 실제 데이터
- GitHub 이슈 #4 — MLP 스코어링 모델 학습 파이프라인 구축, #9 — Unsplash 데이터 수집
