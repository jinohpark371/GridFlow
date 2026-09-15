# Unsplash 전이 비용 학습 데이터 수집 (`Ai/collect_unsplash_data.py`)

> 작성일: 2026-09-14 · 작성자: 진오 · 관련 이슈: #9

## 📌 목적
`transition.py`의 고정 가중치(w1=w2=w3=1.0)를 실제 취향에 맞게 학습시킬 2단계 `TransitionCostModel`용 라벨 데이터를, 실사용자 트래픽 없이 Unsplash API로 준자동 생성한다. 같은 테마 검색 쿼리 결과끼리는 이미 같은 무드로 묶여 있다는 점을 약한 지도(weak supervision) 신호로 삼아 `{theme, pos, neg}` 트리플렛을 만든다.

## 🧭 파이프라인 상 위치
전체 아키텍처 순서도 기준 "Unsplash API 기반 전이 비용 학습 데이터 수집 설계" 단계이며, `mlp.py`의 `build_feature_vector`(CLIP 유사도 + 색감 피처)를 재사용해 사진 피처를 뽑고, 그 결과물(`Ai/data/unsplash/*.csv`)은 이후 별도 이슈에서 진행할 `TransitionCostModel` 학습의 입력이 된다.

- Layer: Layer 2 · 배치(순서 결정) — 학습 데이터 준비 단계
- 이전 단계: 없음 (Unsplash가 원본 데이터 소스)
- 다음 단계: `TransitionCostModel` 학습 스크립트 (별도 이슈, 이 모듈 책임 밖)

## 🔧 입출력 스펙

| 함수 | 입력 | 출력 | 설명 |
|---|---|---|---|
| `search_photos` | `theme: str, access_key: str, per_page=30` | `list[dict]` | Unsplash `/search/photos` 원본 결과 |
| `photo_to_row` | `photo: dict, theme: str` | `dict \| None` | 사진 1장 → 11차원 피처 행. 다운로드/피처 추출 실패 시 `None`(해당 사진만 건너뜀) |
| `collect_all_photos` | `themes: list[str], access_key: str, per_page: int` | `list[dict]` | 테마 전체를 검색·피처화한 행 리스트 (`None`은 제외됨) |
| `sample_triplets` | `photo_rows: list[dict], triplets_per_theme: int, rng: random.Random` | `list[dict]` | `{theme, pos, neg}` 트리플렛. 테마별 사진 수가 부족하면 `ValueError` |
| `write_csv` | `rows: list[dict], path: Path, fieldnames: list[str]` | `None` | 딕셔너리 행 리스트를 CSV로 저장 (디렉터리 자동 생성) |

## 🧠 설계 결정과 이유

- 결정: 실제 드래그 재정렬 데이터(이슈 #8) 대신 Unsplash API로 데이터를 만듦
  - 이유: 실사용자 트래픽이 없는 개인 프로젝트라 드래그 재정렬 데이터가 쌓이길 기다릴 수 없음. `mlp.py`가 12쌍 수동 라벨링으로 학습 루프를 먼저 검증했던 것과 같은 패턴(대화 중 사용자가 직접 제안)
- 결정: 초안이었던 핀터레스트 스크래핑 대신 Unsplash API 사용
  - 이유: 키워드 검색이 정확하고 사진 품질이 균일하며, Unsplash License가 연구/학습용으로 관대해 저작권 리스크가 낮음(사용자 제공 근거로 결정)
- 결정: 모델 입력을 색감 피처(10d)만이 아니라 `mlp.py`와 동일한 11차원(CLIP 유사도 1 + 색감 10, `build_feature_vector`)으로 확장
  - 이유: 처음엔 `transition_cost`가 색감 피처만 쓴다는 점 때문에 10d만 모으려 했으나, 2단계 `TransitionCostModel`을 실제로 학습 가능한 형태로 만들려면 더 풍부한 입력이 필요하다고 판단(대화 중 결정). 이 때문에 사진마다 CLIP 유사도도 함께 계산해야 해서, Unsplash 검색 쿼리와 CLIP 텍스트 인코더 입력을 동일한 영어 문구로 통일함(`openai/clip-vit-base-patch32`가 영어 위주로 학습돼 있어 한글보다 정확도가 나음)
- 결정: `{theme, pos, neg}` 트리플렛 스키마 — `pairs.csv`가 `photo_id_a, photo_id_b, label` 같은 대칭 쌍이 아니라 `mlp.py`의 `label_pairs.json`과 동일한 트리플렛 구조를 따름
  - 이유: 사용자가 "테마 하나에 대해 pos(그 테마 사진)/neg(다른 테마 사진)로 구성해야 논리가 맞다"고 명시적으로 요청 — 기존 라벨링 스키마 철학과 일관성을 맞춤
- 결정: 원본 이미지는 로컬에 저장하지 않고, 메모리에서 피처만 뽑고 버림 — CSV에는 피처값과 `unsplash_url`(추적용)만 저장
  - 이유: 사용자가 "이미지로 하면 용량이 너무 많이 든다"고 지적 — 사진 자체보다 피처값만 있으면 학습에 충분하고, URL만 남겨도 출처 추적은 가능
- 결정: 테마 3개(`minimalist aesthetic photography`, `vintage retro film photography`, `moody urban night photography`), 테마당 사진 30장, 테마당 트리플렛 15개(총 45행)
  - 이유: 파일럿 규모로 API 요청(테마당 1회, 총 3회)이 무료 티어(시간당 50회) 한도에 여유 있게 들어오면서도, `mlp.py`의 12쌍보다 큰 규모로 학습 데이터 다양성을 확보(대화 중 확정)
- 결정: `sample_triplets`는 pos를 해당 테마에서 중복 없이(`rng.sample`) 뽑고, neg는 다른 테마 전체 풀에서 무작위(`rng.choice`, 중복 허용)로 뽑음
  - 이유: pos는 정확히 `triplets_per_theme`개가 필요해 비복원추출이 자연스럽고, neg는 다른 테마 사진이 많아 복원추출로도 다양성이 충분함
- 결정: API 키는 `.env`의 `UNSPLASH_ACCESS_KEY`(Access Key만, `python-dotenv`로 로드)
  - 이유: 공개 검색 API라 OAuth/Secret Key 불필요. `.env`는 이미 `.gitignore`에 있어 별도 설정 없이 안전
- 결정: `photo_to_row`가 개별 사진의 다운로드/피처 추출 실패를 `except Exception`으로 잡아 `None` 반환(해당 사진만 건너뜀)하되, `search_photos`(테마 검색 자체) 실패는 별도로 잡지 않음
  - 이유: 개별 사진 단위 실패는 흔할 수 있어(네트워크 오류 등) 전체 수집을 막지 않는 게 맞지만, 테마 검색 자체가 실패하면(예: 키 오류) 그 테마 데이터가 통째로 비어버리는 심각한 문제라 조용히 넘기지 않고 전체 스크립트가 실패하는 쪽을 선택 — 알려진 트레이드오프(테마 1개라도 네트워크 오류면 전체 실행이 중단됨)이며, 재시도 로직은 요청 수가 총 3회뿐이라 도입하지 않음

## ⚙️ 동작 흐름

```python
# 1) .env의 UNSPLASH_ACCESS_KEY 로드
load_dotenv()
access_key = os.environ["UNSPLASH_ACCESS_KEY"]

# 2) 테마 3개 전체 검색 -> 사진마다 11차원 피처 추출(다운로드 실패는 건너뜀)
photo_rows = collect_all_photos(THEMES, access_key, PHOTOS_PER_THEME)
write_csv(photo_rows, DATA_DIR / "photos.csv", PHOTOS_CSV_FIELDS)

# 3) 같은 테마=pos, 다른 테마=neg로 트리플렛 샘플링
triplets = sample_triplets(photo_rows, TRIPLETS_PER_THEME, random.Random())
write_csv(triplets, DATA_DIR / "pairs.csv", PAIRS_CSV_FIELDS)
```

## ⚠️ 알려진 제약 / TODO

- [x] 파일럿 실행 완료(2026-09-14) — `photos.csv` 90행(테마당 30장), `pairs.csv` 45행(테마당 15개), 전체 트리플렛에 대해 pos/neg 테마 소속을 스크립트로 검증(위반 0건)
- [ ] `collect_all_photos`는 `search_photos` 실패를 잡지 않아 테마 하나라도 네트워크 오류가 나면 전체 스크립트가 중단됨 — 요청 수가 적어 지금은 문제되지 않지만, 테마 수가 늘어나면 재검토
- [ ] `TransitionCostModel` 학습 스크립트는 이 모듈 책임 밖 — 이 데이터가 준비된 뒤 별도 이슈로 진행
- [ ] Unsplash 이미지는 로컬에 저장하지 않으므로, 피처 추출 로직(`build_feature_vector`)이 바뀌면 전체 사진을 다시 다운로드해서 재수집해야 함

## 🧪 사용 예시

```bash
python Ai/collect_unsplash_data.py
# 출력 예: photos.csv: 90장 저장
#          pairs.csv: 45행 저장
```

## 🔗 참고

- Notion "Unsplash API 기반 전이 비용 학습 데이터 수집 설계" — https://app.notion.com/p/3d0d1ebe485381fc8a38c149a77e7e8c
- `docs/ai/Mlp_scoring.md` — `build_feature_vector`(11d) 세부 설계, `{theme, pos, neg}` 스키마 철학의 원형
- `docs/ai/Transition.md` — 이 데이터로 학습할 `TransitionCostModel`이 대체할 1단계 고정 가중치 설계
- 관련 이슈: #9
