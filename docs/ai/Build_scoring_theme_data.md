# 교차 clip_sim 수집 (`Ai/build_scoring_theme_data.py`)

> 작성일: 2026-09-22 · 최종 수정: 2026-11-02 · 작성자: 진오 · 관련 이슈: #13, #23

## 📌 목적
`ScoringMLP`를 테마마다 따로 학습하려면, 사진 90장(테마당 30장) 각각을 **테마 문장 3개 모두로 잰 CLIP 유사도**가 필요하다. `photos.csv`에는 "그 사진이 수집된 테마" 기준 값 하나뿐이라, 원본 이미지를 다시 받아 나머지를 채운 `cross_clip_sim.csv`를 만든다.

## 🧭 파이프라인 상 위치
`Ai/collect_unsplash_data.py`(원본 다중 테마 데이터)와 `Ai/dataset.py`(테마별 학습 쌍 구성) 사이의 일회성 데이터 보강 스크립트.

- Layer: Layer 1 · 테마 적합도 스코어링 > 학습 데이터 준비
- 이전 단계: `Ai/collect_unsplash_data.py`가 만든 `Ai/data/unsplash/photos.csv`
- 다음 단계: `Ai/dataset.py`(`load_cross_clip_sim`, `build_theme_pairs`)가 이 스크립트의 출력을 읽음

## 🔧 입출력 스펙

| 함수 | 입력 | 출력 | 설명 |
|---|---|---|---|
| `load_source_rows` | `path`(기본 `photos.csv`) | `list[dict]` | 원본 다중 테마 데이터를 그대로 읽음 |
| `load_done_photo_ids` | `path`(기본 `cross_clip_sim.csv`) | `set[str]` | 이미 계산한 사진 — 파일이 없으면 빈 집합 |
| `pending_rows` | `source_rows, done_ids, limit` | `list[dict]` | 아직 안 한 사진을 `photos.csv` 순서대로 `limit`장까지 |
| `fetch_image` | `photo_id, access_key` | `PIL.Image` | Unsplash "Get a photo" API로 원본 URL 조회 후 다운로드 |
| `cross_clip_row` | `photo_id, image_vec, theme_vecs` | `dict` | `{photo_id, clip_mono, clip_vivid, clip_golden}` 한 행 |
| `append_cross_clip_row` | `row, path` | `None` | CSV 끝에 한 줄 덧붙임(파일이 없으면 헤더부터) |

## 🧠 설계 결정과 이유

- 결정(변경, 2026-11-02): 흑백 테마 하나 기준으로 neg 15장만 재계산하던 방식을 **사진 90장 x 테마 문장 3개 전부**를 재는 방식으로 바꿈
  - 이유: 흑백 데이터로만 학습한 단일 `ScoringMLP`가 테마와 상관없이 "채도가 낮을수록 높은 점수"만 배워, 어떤 테마를 골라도 흑백 사진만 통과하는 문제가 드러남(#23). 테마마다 모델을 따로 학습하기로 했고, 그러려면 다른 테마 사진을 각 테마 문장으로 잰 값이 모두 있어야 함 — 자세한 경위는 `docs/ai/Mlp_scoring.md`
- 결정: 결과를 `photos.csv`에 컬럼으로 추가하지 않고 별도 파일 `cross_clip_sim.csv`로 저장
  - 이유: `photos.csv`는 `TransitionCostModel`도 읽는 원본 데이터라 건드리지 않음. 컬럼명은 `mlp.THEME_KEYS`의 짧은 키(`mono`/`vivid`/`golden`)를 써서 테마별 모델 파일명과 맞춤
- 결정: 한 번 실행에 최대 `MAX_PHOTOS_PER_RUN = 45`장, 한 장 계산할 때마다 바로 CSV에 덧붙이고, 이미 있는 사진은 건너뜀
  - 이유: "Get a photo" API가 시간당 50회 제한이라 90장을 한 번에 받을 수 없음(45장씩 두 번, 5회는 재시도 여유). 끝에 한꺼번에 저장하면 중간에 제한·네트워크 오류로 멈췄을 때 받은 것까지 날아가는데, 바로 덧붙이면 다시 실행만 하면 이어서 채워짐 — 실제로 2회차가 40장째에 중단됐지만 재실행으로 남은 5장만 받아 마무리함
- 결정: 사진당 CLIP 이미지 벡터는 한 번만 계산하고 테마 문장 3개와 각각 코사인 유사도를 냄
  - 이유: 기존 `clip.get_theme_score`를 테마마다 부르면 같은 사진을 이미지 인코더에 세 번 넣게 됨
- 결정: `photo_id`로 Unsplash "Get a photo"(`/photos/:id`) API를 다시 호출해 이미지 URL을 구함 (유지)
  - 이유: `photos.csv`의 `unsplash_url`은 추적용 웹페이지 링크(`photo.links.html`)라 바로 다운로드할 수 없고, 원본 이미지 자체는 로컬에 남기지 않기로 한 설계(`docs/ai/Collect_unsplash_data.md`)

## ⚙️ 동작 흐름

```python
done_ids = load_done_photo_ids()                       # 이미 받은 사진
todo = pending_rows(load_source_rows(), done_ids, 45)  # 이번 실행에서 받을 사진
theme_vecs = {t: get_text_embedding(t) for t in THEME_KEYS}
for row in todo:
    image = fetch_image(row["photo_id"], access_key)   # 403/429면 중단 -> 1시간 뒤 재실행
    append_cross_clip_row(cross_clip_row(row["photo_id"], get_image_embedding(image), theme_vecs))
```

## ⚠️ 알려진 제약 / TODO

- [x] 실행 완료(2026-11-02) — `cross_clip_sim.csv` 90장 x 3테마. 같은 사진·같은 문장 값을 기존 값과 비교해 검증: 자기 테마 값 vs `photos.csv`의 `clip_sim` 45장 평균 차이 0.0004(최대 0.0042), 흑백 문장 값 vs 이전 재계산 값 6장 최대 0.0017 — 다운로드할 때마다 이미지 압축이 미세하게 달라지는 수준
- [ ] 테마를 추가하면 `mlp.THEME_KEYS`에 넣고 이 스크립트를 처음부터 다시 돌려야 함(기존 행에는 새 컬럼이 없음) — 지금은 프론트 테마가 3개로 고정이라 재수집 기능은 만들지 않음

## 🧪 사용 예시

```bash
python Ai/build_scoring_theme_data.py
# 출력 예: cross_clip_sim.csv: 이번에 45장 추가, 전체 45/90장
#          남은 사진이 있음 — 1시간쯤 뒤에 다시 실행하면 이어서 채운다
```

## 🔗 참고

- `docs/ai/Dataset.md` — `cross_clip_sim.csv`를 읽어 테마별 학습 쌍을 만드는 로더
- `docs/ai/Mlp_scoring.md` — 테마별 모델로 바꾼 이유와 결과
- `docs/ai/Collect_unsplash_data.md` — `photos.csv`를 만드는 원본 수집 스크립트
