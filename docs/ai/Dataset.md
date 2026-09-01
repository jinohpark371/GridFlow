# 라벨 데이터 로딩 (`Ai/dataset.py`)

> 작성일: 2026-08-27 · 작성자: 진오 · 관련 이슈: test/mlp-학습-파이프라인/4

## 📌 목적
`Ai/data/label_pairs.json`의 라벨 쌍(theme, pos, neg)을 읽어 `build_feature_vector`로 피처화하고, 학습 루프에 바로 넣을 수 있는 배치 텐서로 만든다.

## 🧭 파이프라인 상 위치
"MLP 모델 설계" 단계와 (아직 미구현인) 학습 스크립트 사이의 데이터 로더.

- Layer: Layer 1 · 테마 적합도 스코어링 > 학습 데이터 로딩
- 이전 단계: 라벨 데이터(`Ai/data/label_pairs.json`) + `build_feature_vector`(`mlp.py`)
- 다음 단계: 학습 스크립트(`Ai/train_mlp.py`, 미구현) — `rank_forward` + `margin_ranking_loss`

## 🔧 입출력 스펙

| 함수 | 입력 | 출력 | 설명 |
|---|---|---|---|
| `load_label_pairs` | `path` (기본값 `Ai/data/label_pairs.json`) | `list[dict]` | `{theme, pos, neg}` 라벨 쌍을 그대로 반환 |
| `build_pair_features` | `pairs: list[dict]` | `(feats_pos, feats_neg)` (각 `torch.Tensor`, shape `(N, 11)`) | 쌍마다 pos/neg 사진을 `build_feature_vector`로 피처화해 배치로 묶음 |

## 🧠 설계 결정과 이유

- 결정: `build_pair_features`는 사진마다 `build_feature_vector`를 그대로 재사용 (CLIP/색감 피처를 직접 다시 호출하지 않음)
  - 이유: 피처 추출 로직(11d 구성)의 단일 소스를 `mlp.py`에 유지하기 위해 — 두 곳에서 같은 로직을 따로 구현하면 나중에 `INPUT_DIM`이 바뀔 때 한쪽만 갱신되는 버그가 생기기 쉬움
- 결정: 라벨 쌍의 `pos`/`neg` 경로는 저장소 루트 기준 상대 경로(`"samples/..."`)로 저장돼 있고, `REPO_ROOT`(= `Ai/`의 부모 디렉터리)를 기준으로 절대 경로로 바꿔 읽음
  - 이유: `pytest`(작업 디렉터리가 저장소 루트)와 `python Ai/dataset.py`(작업 디렉터리가 `Ai/`일 수 있음)처럼 실행 방식에 따라 현재 작업 디렉터리(cwd)가 달라져도 항상 같은 파일을 가리키게 하기 위해
- 결정: `feats_pos`/`feats_neg`를 각각 리스트로 모은 뒤 `np.stack`으로 `(N, 11)` 배열을 만들고 `torch.from_numpy`로 변환
  - 이유: `rank_forward`/`margin_ranking_loss`가 배치 입력을 기대하므로, 쌍 하나하나를 개별 처리하지 않고 N개를 한 번에 forward pass 돌릴 수 있는 형태로 미리 묶어둠

## ⚙️ 동작 흐름

```python
pairs = load_label_pairs()  # Ai/data/label_pairs.json -> [{theme, pos, neg}, ...]
feats_pos, feats_neg = build_pair_features(pairs)  # (N, 11), (N, 11)

# 학습 스크립트(Ai/train_mlp.py)에서:
# model, loss_history = train(feats_pos, feats_neg)
```

## ⚠️ 알려진 제약 / TODO

- [ ] 라벨 파일 하나(`Ai/data/label_pairs.json`)만 지원 — 여러 라벨 파일을 합치거나 증분 라벨을 병합하는 기능은 없음
- [ ] 같은 사진이 여러 쌍에 등장해도 그때마다 CLIP 임베딩을 다시 계산함 — 지금은 라벨이 12쌍뿐이라 문제없지만, 데이터가 늘어나면 사진별 피처 캐싱을 고려해야 함
- [x] 학습 스크립트는 `Ai/train_mlp.py`에 구현됨 — 이 모듈은 그 입력 텐서를 만드는 데까지만 책임지는 역할 분리 유지

## 🧪 사용 예시

```bash
python Ai/dataset.py
# 출력 예: loaded 12 pairs -> feats_pos (12, 11), feats_neg (12, 11)
```

## 🔗 참고

- `docs/ai/Mlp_scoring.md` — `build_feature_vector`, 라벨 데이터 포맷(JSON) 선택 이유
- `Ai/data/label_pairs.json` — 실제 라벨 쌍 데이터
- GitHub 이슈 #4 — MLP 스코어링 모델 학습 파이프라인 구축
