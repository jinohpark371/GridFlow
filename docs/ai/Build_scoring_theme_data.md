# 고정 테마 ScoringMLP 데이터 구성 (`Ai/build_scoring_theme_data.py`)

> 작성일: 2026-09-22 · 작성자: 진오 · 관련 이슈: #13

## 📌 목적
`Ai/collect_unsplash_data.py`가 만든 Unsplash 파일럿 데이터(`photos.csv`)를 재활용해, `ScoringMLP`(`Ai/mlp.py`) 학습에 맞는 **테마 하나로 고정된** `{theme, pos, neg}` 데이터를 만든다. `label_pairs.json`(초기 프로토타입 시절 "미니멀한 감성 사진" 테마)을 복원하는 대신, 현재 프로젝트가 쓰는 Unsplash 테마 중 하나를 그대로 재사용한다.

## 🧭 파이프라인 상 위치
`Ai/collect_unsplash_data.py`(원본 다중 테마 데이터)와 `Ai/train_mlp.py`/`Ai/evaluate_mlp.py`(단일 테마 학습) 사이의 일회성 데이터 변환 스크립트.

- Layer: Layer 1 · 테마 적합도 스코어링 > 학습 데이터 준비
- 이전 단계: `Ai/collect_unsplash_data.py`가 만든 `Ai/data/unsplash/photos.csv`
- 다음 단계: `Ai/dataset.py`(`load_label_pairs`/`load_photo_features`)가 이 스크립트의 출력을 읽음

## 🔧 입출력 스펙

| 함수 | 입력 | 출력 | 설명 |
|---|---|---|---|
| `load_source_rows` | `path`(기본 `photos.csv`) | `list[dict]` | 원본 다중 테마 데이터를 그대로 읽음 |
| `fetch_image_url` | `photo_id, access_key` | `str` (이미지 URL) | Unsplash "Get a photo" API로 원본 이미지 다운로드 URL 재조회 |
| `recompute_clip_sim` | `row, theme_text, access_key` | `float` | 사진을 다시 받아 고정 테마 기준 CLIP 유사도 재계산 |
| `build_scoring_rows` | `source_rows, theme_text, n_pairs, access_key, rng` | `list[dict]` | pos(고정 테마 사진, clip_sim 그대로) + neg(다른 테마 사진 일부, clip_sim 재계산) 행 목록 |
| `sample_scoring_pairs` | `pos_ids, neg_ids, theme_text, rng` | `list[dict]` | pos/neg id를 1:1로 섞어 `{theme, pos, neg}` 생성 |

## 🧠 설계 결정과 이유

- 결정: `label_pairs.json` 복원 대신 기존 Unsplash 테마(`black and white monochrome photography`) 중 하나를 `ScoringMLP`의 고정 테마로 재사용
  - 이유: `label_pairs.json`의 테마("미니멀한 감성 사진")는 초기 프로토타입 시절 테마라 현재 방향(흑백/컬러풀/따뜻한 색조)과 안 맞는다는 지적(대화 중)에 따라, 이미 검증된 Unsplash 테마를 그대로 씀
- 결정: pos(고정 테마로 수집된 사진)의 `clip_sim`은 그대로 재사용하고, neg(다른 테마 사진)의 `clip_sim`만 원본 이미지를 다시 받아 재계산
  - 이유: `photos.csv`의 `clip_sim`은 **그 사진이 수집될 때 배정된 테마** 기준으로 계산돼 있어(예: "vibrant colorful" 사진의 clip_sim은 그 문장 기준), 다른 고정 테마(예: "black and white...")로 재평가하려면 그 사진만 다시 계산해야 함. pos는 애초에 고정 테마 기준으로 이미 정확해서 재계산 불필요. 색감 피처(10d)는 테마와 무관한 사진 고유값이라 pos/neg 모두 재계산하지 않음
- 결정: `photo_id`로 Unsplash "Get a photo"(`/photos/:id`) API를 다시 호출해 이미지 URL을 구함
  - 이유: `photos.csv`의 `unsplash_url`은 추적용 웹페이지 링크(`photo.links.html`)라 바로 다운로드할 수 없음 — 원본 이미지 URL(`urls.regular`)은 애초에 저장해 두지 않았기 때문(이미지 자체를 로컬에 안 남기기로 한 설계 결정, `docs/ai/Collect_unsplash_data.md` 참고)
- 결정: neg 후보를 `n_pairs`(15)개만 뽑아서 그만큼만 재계산 — 다른 테마 사진 전부(30장)를 재계산하지 않음
  - 이유: 재다운로드 + CLIP 계산 비용을 필요한 만큼만 쓰기 위해. `label_pairs.json`의 12쌍과 비슷한 규모(15쌍)로 맞춤

## ⚙️ 동작 흐름

```python
source_rows = load_source_rows()  # photos.csv -> 다중 테마 원본 데이터

scoring_rows = build_scoring_rows(source_rows, FIXED_THEME, N_PAIRS, access_key, rng)
# pos: 고정 테마 사진(clip_sim 그대로) + neg: 다른 테마 일부(clip_sim 재계산)

pairs = sample_scoring_pairs(pos_ids, neg_ids, FIXED_THEME, rng)
# {theme, pos, neg} 15쌍 -> scoring_pairs.csv
```

## ⚠️ 알려진 제약 / TODO

- [x] 실행 완료(2026-09-22) — `scoring_photos.csv` 45장(고정 테마 전체 30장을 pos 후보로, 재계산한 neg 15장을 더함 — `photos.csv` 자체가 테마당 30장이라 pos 후보도 30장임, `filter_representative_photos`로 거른 15장은 `pairs.csv` 트리플렛에만 적용되고 `photos.csv`엔 반영 안 됨), `scoring_pairs.csv` 15쌍 생성, `Ai/evaluate_mlp.py`로 재학습 시 val ranking accuracy 100%(3/3)
- [ ] 지금은 `FIXED_THEME`을 코드 상수로 고정(`black and white monochrome photography`) — 다른 테마로 바꾸려면 코드 수정 필요, CLI 인자화는 안 함(1회성 스크립트라 YAGNI)
- [ ] 재실행하면 neg 후보가 매번 다시 다운로드·재계산됨(캐싱 없음) — 데이터가 이미 committed돼 있어 일상적으로 재실행할 필요는 없음

## 🧪 사용 예시

```bash
python Ai/build_scoring_theme_data.py
# 출력 예: scoring_photos.csv: 45장 저장
#          scoring_pairs.csv: 15쌍 저장 (theme=black and white monochrome photography)
```

## 🔗 참고

- `docs/ai/Collect_unsplash_data.md` — 원본 `photos.csv`를 만드는 수집 스크립트
- `docs/ai/Mlp_scoring.md` — `ScoringMLP`가 왜 테마 하나 고정 데이터가 필요한지
- `docs/ai/Dataset.md` — `scoring_pairs.csv`/`scoring_photos.csv`를 읽는 로더
- GitHub 이슈 #13 — MLP val ranking accuracy 개선
