# Unsplash 전이 비용 학습 데이터 수집 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unsplash API로 테마별 사진을 수집해, `TransitionCostModel`(2단계) 학습에 쓸 `{theme, pos, neg}` 트리플렛 라벨 데이터를 준자동으로 만드는 `Ai/collect_unsplash_data.py`를 구현한다.

**Architecture:** 테마 3개를 Unsplash `/search/photos`로 검색 → 사진마다 `mlp.py`의 `build_feature_vector`(11d: CLIP 유사도 1 + 색감 피처 10)를 재사용해 피처만 추출하고 원본 이미지는 버림 → `Ai/data/unsplash/photos.csv`에 저장 → 같은 테마=pos, 다른 테마=neg로 트리플렛을 무작위 샘플링해 `Ai/data/unsplash/pairs.csv`에 저장.

**Tech Stack:** `httpx`(HTTP, 기존 의존성 재사용), `python-dotenv`(신규 추가, `.env`의 `UNSPLASH_ACCESS_KEY` 로드), `mlp.py`/`clip.py`/`features.py`(기존 피처 추출 재사용), 표준 라이브러리 `csv`, `random`.

**Spec:** Notion "Unsplash API 기반 전이 비용 학습 데이터 수집 설계" — https://app.notion.com/p/3d0d1ebe485381fc8a38c149a77e7e8c (GridFlow / Ai)

## Global Constraints

- `Ai/`는 패키지가 아니라 스크립트 스타일 — `__init__.py` 없음, 모듈 간 bare import(`from mlp import build_feature_vector`) 사용, `python Ai/collect_unsplash_data.py`로 단독 실행 가능해야 함
- `requirements.txt`는 알파벳 순 정렬 + 버전 고정(`==`) 유지 — `python-dotenv`만 신규 추가, 그 외 기존 의존성(`httpx`, `pillow`, `numpy`) 재사용, `torch==2.5.1+cpu` 등 기존 고정 버전은 건드리지 않음
- 테마(확정): `minimalist aesthetic photography`, `vintage retro film photography`, `moody urban night photography` — Unsplash 검색 쿼리와 CLIP 텍스트 인코더 입력에 동일하게 재사용
- 규모(확정): 테마당 사진 30장(`per_page=30`, API 요청 테마당 1회) × 3테마 = 90장, 테마당 트리플렛 15개 × 3테마 = 45행
- 이미지는 로컬에 저장하지 않음 — 메모리에서 피처만 추출하고 폐기. 추적용 `unsplash_url`만 CSV에 보관
- API 키는 `.env`의 `UNSPLASH_ACCESS_KEY`(Access Key만, Secret Key/OAuth 불필요), `.env`는 이미 `.gitignore`에 있음
- 저장 경로(확정): `Ai/data/unsplash/photos.csv`, `Ai/data/unsplash/pairs.csv`
- 테스트는 `tests/ai/test_<module>.py`(순수 로직, 기본 실행) / `tests/ai/test_<module>_integration.py`(네트워크·API 키 필요, `pytestmark = pytest.mark.integration`)로 분리 — 이 저장소의 `test_clip.py`/`test_clip_integration.py` 분리 컨벤션을 그대로 따름
- **커밋은 태스크마다 하지 않는다** — 이 저장소는 `Ai/` 변경을 코드+테스트+`docs/ai/<Module>.md` 문서와 함께 `/ai-commit` 절차(사용자 승인 후 실행)로 한 번에 정리하는 컨벤션이 있음. 각 태스크의 "커밋" 단계는 생략하고, 전체 구현이 끝난 뒤 마지막 태스크에서 `/ai-commit`으로 진행

---

## File Structure

- **Create:** `Ai/collect_unsplash_data.py` — Unsplash 검색, 피처 추출, CSV 저장, 트리플렛 샘플링을 담당하는 단일 스크립트 모듈 (기존 `Ai/` 모듈들과 같은 스타일)
- **Create:** `tests/ai/test_collect_unsplash_data.py` — `sample_triplets` 순수 로직 유닛 테스트 (네트워크 불필요)
- **Create:** `tests/ai/test_collect_unsplash_data_integration.py` — `search_photos`/`photo_to_row` 통합 테스트 (네트워크 + `UNSPLASH_ACCESS_KEY` 필요, 키 없으면 skip)
- **Modify:** `requirements.txt` — `python-dotenv` 알파벳 순 위치에 추가
- **Create (런타임 산출물, 코드 아님):** `Ai/data/unsplash/photos.csv`, `Ai/data/unsplash/pairs.csv` — 실제 파일럿 실행 시 생성됨

---

## Task 1: 트리플렛 샘플링 로직 (`sample_triplets`)

순수 로직만 다루는 태스크 — 네트워크·API 키 없이 TDD로 먼저 검증한다. `photo_rows`는 이후 Task 2가 만들 `photo_to_row` 결과와 같은 모양(`{"photo_id": str, "query": str, ...}`)의 딕셔너리 리스트라고 가정한다.

**Files:**
- Create: `Ai/collect_unsplash_data.py` (이 태스크에서는 `sample_triplets`만 작성)
- Test: `tests/ai/test_collect_unsplash_data.py`

**Interfaces:**
- Produces: `sample_triplets(photo_rows: list[dict], triplets_per_theme: int, rng: random.Random) -> list[dict]` — 반환값은 `{"theme": str, "pos": str, "neg": str}` 딕셔너리 리스트. `photo_rows`의 각 원소는 최소 `"photo_id"`, `"query"` 키를 가짐. 테마별 사용 가능한 사진 수가 `triplets_per_theme`보다 적으면 `ValueError` 발생

- [ ] **Step 1: 실패하는 테스트 작성**

```python
"""Ai/collect_unsplash_data.py 트리플렛 샘플링 로직 단위 테스트.

네트워크·Unsplash API 키 없이 순수 로직만 검증 — 빠르게 실행됨.
"""

import random

import pytest
from collect_unsplash_data import sample_triplets


def _fake_photo_rows(theme: str, count: int) -> list[dict]:
    return [{"photo_id": f"{theme}_{i}", "query": theme} for i in range(count)]


def test_sample_triplets_returns_requested_count_per_theme():
    rows = _fake_photo_rows("minimal", 5) + _fake_photo_rows("vintage", 5) + _fake_photo_rows("urban", 5)

    triplets = sample_triplets(rows, triplets_per_theme=3, rng=random.Random(0))

    assert len(triplets) == 3 * 3
    assert sum(1 for t in triplets if t["theme"] == "minimal") == 3
    assert sum(1 for t in triplets if t["theme"] == "vintage") == 3
    assert sum(1 for t in triplets if t["theme"] == "urban") == 3


def test_sample_triplets_pos_belongs_to_theme_and_neg_does_not():
    rows = _fake_photo_rows("minimal", 5) + _fake_photo_rows("vintage", 5) + _fake_photo_rows("urban", 5)
    by_id = {r["photo_id"]: r["query"] for r in rows}

    triplets = sample_triplets(rows, triplets_per_theme=3, rng=random.Random(0))

    for t in triplets:
        assert by_id[t["pos"]] == t["theme"]
        assert by_id[t["neg"]] != t["theme"]


def test_sample_triplets_raises_when_theme_pool_too_small():
    rows = _fake_photo_rows("minimal", 2) + _fake_photo_rows("vintage", 5)

    with pytest.raises(ValueError):
        sample_triplets(rows, triplets_per_theme=3, rng=random.Random(0))
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/ai/test_collect_unsplash_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'collect_unsplash_data'` (아직 파일이 없음)

- [ ] **Step 3: 최소 구현 작성**

`Ai/collect_unsplash_data.py` 새 파일 시작 부분에 작성:

```python
"""Unsplash API 기반 전이 비용 학습 데이터 수집 (흐름도 > Unsplash API 기반 전이 비용 학습 데이터 수집 설계).

흐름: 테마 검색어 -> Unsplash /search/photos -> 사진마다 build_feature_vector(11d)로 피처만 추출
      -> photos.csv 저장 -> 같은 테마=pos/다른 테마=neg로 트리플렛 샘플링 -> pairs.csv 저장

2단계 TransitionCostModel 학습용 라벨 데이터를 실사용자 트래픽 없이 준자동으로 만들기 위한 수집 스크립트.
"""

from __future__ import annotations

import random

THEMES = [
    "minimalist aesthetic photography",
    "vintage retro film photography",
    "moody urban night photography",
]
PHOTOS_PER_THEME = 30
TRIPLETS_PER_THEME = 15


def sample_triplets(photo_rows: list[dict], triplets_per_theme: int, rng: random.Random) -> list[dict]:
    """같은 테마 사진=pos, 다른 테마 사진=neg로 {theme, pos, neg} 트리플렛을 무작위 샘플링."""
    by_theme: dict[str, list[str]] = {}
    for row in photo_rows:
        by_theme.setdefault(row["query"], []).append(row["photo_id"])

    triplets = []
    for theme, photo_ids in by_theme.items():
        if len(photo_ids) < triplets_per_theme:
            raise ValueError(
                f"테마 '{theme}'의 사진 수({len(photo_ids)})가 triplets_per_theme({triplets_per_theme})보다 적음"
            )
        pos_picks = rng.sample(photo_ids, triplets_per_theme)
        other_photo_ids = [pid for t, ids in by_theme.items() if t != theme for pid in ids]
        for pos in pos_picks:
            neg = rng.choice(other_photo_ids)
            triplets.append({"theme": theme, "pos": pos, "neg": neg})
    return triplets
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/ai/test_collect_unsplash_data.py -v`
Expected: PASS (3개 테스트 모두)

---

## Task 2: Unsplash 검색 + 사진 → 11차원 피처 행 변환

**Files:**
- Modify: `Ai/collect_unsplash_data.py` (Task 1 파일에 이어서 작성)
- Modify: `requirements.txt` — `python-dotenv` 추가
- Test: `tests/ai/test_collect_unsplash_data_integration.py`

**Interfaces:**
- Consumes: `mlp.py`의 `build_feature_vector(image, theme_text) -> np.ndarray`(11d), `features.py`의 `HUE_HIST_BINS`(hue_hist 컬럼 수 결정에 사용)
- Produces: `search_photos(theme: str, access_key: str, per_page: int = PHOTOS_PER_THEME) -> list[dict]` (Unsplash API 원본 결과 리스트), `photo_to_row(photo: dict, theme: str) -> dict | None` (다운로드·피처 추출 실패 시 `None`, 성공 시 `{"photo_id", "query", "unsplash_url", "clip_sim", "mean_h", "mean_s", "mean_v", "sat_std", "val_std", "contrast", "hue_hist_0"..."hue_hist_3"}`)

- [ ] **Step 1: `requirements.txt`에 `python-dotenv` 추가**

`fsspec==2026.7.0` 다음 줄, `h11==0.16.0` 앞에 알파벳 순으로 삽입 — 정확한 버전은 설치 시 `pip index versions python-dotenv`로 최신 안정 버전 확인 후 고정(`==`)한다. 확인이 어려우면 `python-dotenv==1.0.1`로 우선 고정.

- [ ] **Step 2: 실패하는 통합 테스트 작성**

```python
"""Ai/collect_unsplash_data.py의 Unsplash API 호출 + 피처 추출 통합 테스트.

실제 네트워크와 UNSPLASH_ACCESS_KEY(.env)가 필요해 느림/조건부.
기본 `pytest` 실행에서는 제외되며(pytest.ini의 addopts), 명시적으로 실행하려면:

    pytest -m integration
"""

import os

import numpy as np
import pytest
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.integration

ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
requires_key = pytest.mark.skipif(not ACCESS_KEY, reason="UNSPLASH_ACCESS_KEY가 .env에 없음")


@requires_key
def test_search_photos_returns_requested_count():
    from collect_unsplash_data import search_photos

    results = search_photos("minimalist aesthetic photography", ACCESS_KEY, per_page=5)

    assert len(results) == 5
    assert all("id" in p and "urls" in p and "links" in p for p in results)


@requires_key
def test_photo_to_row_has_11d_feature_columns():
    from collect_unsplash_data import photo_to_row, search_photos

    photo = search_photos("minimalist aesthetic photography", ACCESS_KEY, per_page=1)[0]

    row = photo_to_row(photo, "minimalist aesthetic photography")

    assert row is not None
    feature_keys = [
        "clip_sim", "mean_h", "mean_s", "mean_v", "sat_std", "val_std", "contrast",
        "hue_hist_0", "hue_hist_1", "hue_hist_2", "hue_hist_3",
    ]
    for key in feature_keys:
        assert np.isfinite(row[key])
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `python -m pytest tests/ai/test_collect_unsplash_data_integration.py -v -m integration`
Expected: FAIL — `ImportError: cannot import name 'search_photos'`

- [ ] **Step 4: 구현 작성**

`Ai/collect_unsplash_data.py`에 아래 함수들과 상단 import 추가:

```python
from io import BytesIO

import httpx
import numpy as np
from PIL import Image

from features import HUE_HIST_BINS
from mlp import build_feature_vector

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"


def search_photos(theme: str, access_key: str, per_page: int = PHOTOS_PER_THEME) -> list[dict]:
    """테마 검색어 -> Unsplash /search/photos -> 사진 메타데이터 리스트(raw JSON)."""
    response = httpx.get(
        UNSPLASH_SEARCH_URL,
        params={"query": theme, "per_page": per_page},
        headers={"Authorization": f"Client-ID {access_key}"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["results"]


def photo_to_row(photo: dict, theme: str) -> dict | None:
    """Unsplash 사진 1장 -> 11차원 피처(clip_sim + 색감 10) 행. 다운로드/피처 추출 실패 시 None."""
    try:
        image_response = httpx.get(photo["urls"]["regular"], timeout=30.0)
        image_response.raise_for_status()
        image = Image.open(BytesIO(image_response.content)).convert("RGB")
        feats = build_feature_vector(image, theme)
    except Exception as exc:  # 네트워크/디코딩 실패는 이 사진만 건너뜀
        print(f"[skip] {photo.get('id')}: {exc}")
        return None

    row = {
        "photo_id": photo["id"],
        "query": theme,
        "unsplash_url": photo["links"]["html"],
        "clip_sim": float(feats[0]),
        "mean_h": float(feats[1]),
        "mean_s": float(feats[2]),
        "mean_v": float(feats[3]),
        "sat_std": float(feats[4]),
        "val_std": float(feats[5]),
        "contrast": float(feats[6]),
    }
    for i in range(HUE_HIST_BINS):
        row[f"hue_hist_{i}"] = float(feats[7 + i])
    return row
```

**주의:** `build_feature_vector`가 반환하는 11차원 배열의 순서는 `[clip_score, *color_feats]`이고 `color_feats`는 `features.py`의 `extract_color_features` 순서(`mean_h, mean_s, mean_v, sat_std, val_std, contrast, hue_hist(4)`)를 그대로 따른다 — 위 인덱스(`feats[0]`=clip, `feats[1..6]`=6개 스칼라, `feats[7:]`=hue_hist)가 실제 구현과 일치하는지 `Ai/mlp.py`의 `build_feature_vector`와 `Ai/features.py`의 `extract_color_features`를 다시 읽고 확인할 것.

- [ ] **Step 5: 테스트 통과 확인 (API 키가 있을 때)**

Run: `python -m pytest tests/ai/test_collect_unsplash_data_integration.py -v -m integration`
Expected: PASS (키가 `.env`에 있으면), 없으면 SKIPPED

---

## Task 3: CSV 저장 + 전체 오케스트레이션 (`__main__`) + 파일럿 실행

**Files:**
- Modify: `Ai/collect_unsplash_data.py` (Task 1·2 함수를 엮는 메인 흐름 추가)

**Interfaces:**
- Consumes: Task 1의 `sample_triplets`, Task 2의 `search_photos`/`photo_to_row`, `THEMES`/`PHOTOS_PER_THEME`/`TRIPLETS_PER_THEME`
- Produces: `collect_all_photos(themes: list[str], access_key: str, per_page: int) -> list[dict]`, `write_csv(rows: list[dict], path: str, fieldnames: list[str]) -> None`, 스크립트 실행 시 `Ai/data/unsplash/photos.csv`·`Ai/data/unsplash/pairs.csv` 생성

- [ ] **Step 1: 오케스트레이션·저장 함수 작성**

`Ai/collect_unsplash_data.py`에 추가:

```python
import csv
import os
from pathlib import Path

from dotenv import load_dotenv

DATA_DIR = Path(__file__).parent / "data" / "unsplash"
PHOTOS_CSV_FIELDS = [
    "photo_id", "query", "unsplash_url", "clip_sim",
    "mean_h", "mean_s", "mean_v", "sat_std", "val_std", "contrast",
    "hue_hist_0", "hue_hist_1", "hue_hist_2", "hue_hist_3",
]
PAIRS_CSV_FIELDS = ["theme", "pos", "neg"]


def collect_all_photos(themes: list[str], access_key: str, per_page: int) -> list[dict]:
    """테마 리스트 전체를 검색해 피처 행 리스트로 변환 (다운로드 실패 사진은 제외)."""
    rows = []
    for theme in themes:
        for photo in search_photos(theme, access_key, per_page):
            row = photo_to_row(photo, theme)
            if row is not None:
                rows.append(row)
    return rows


def write_csv(rows: list[dict], path: Path, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    load_dotenv()
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not access_key:
        print("UNSPLASH_ACCESS_KEY가 .env에 없음")
        raise SystemExit(1)

    photo_rows = collect_all_photos(THEMES, access_key, PHOTOS_PER_THEME)
    write_csv(photo_rows, DATA_DIR / "photos.csv", PHOTOS_CSV_FIELDS)
    print(f"photos.csv: {len(photo_rows)}장 저장")

    triplets = sample_triplets(photo_rows, TRIPLETS_PER_THEME, random.Random())
    write_csv(triplets, DATA_DIR / "pairs.csv", PAIRS_CSV_FIELDS)
    print(f"pairs.csv: {len(triplets)}행 저장")
```

- [ ] **Step 2: 전체 유닛 테스트 재확인**

Run: `python -m pytest tests/ai/test_collect_unsplash_data.py -v`
Expected: PASS (Task 1의 3개 테스트 그대로 유지)

- [ ] **Step 3: 파일럿 실행 (실제 API 키로, 사용자와 함께 확인)**

Run: `python Ai/collect_unsplash_data.py`
Expected: `Ai/data/unsplash/photos.csv`(약 90행), `Ai/data/unsplash/pairs.csv`(45행) 생성. 실행 중 `[skip]` 로그가 과도하게 많이 뜨면(예: 사진 수가 30장보다 훨씬 적게 성공) 사용자에게 보고하고 원인(네트워크/레이트리밋/키 문제) 확인

- [ ] **Step 4: 결과 CSV 육안 확인**

`photos.csv`/`pairs.csv`를 열어 컬럼 수·값 범위(`clip_sim`은 -1~1, 나머지 색감 피처는 0~1)가 설계와 맞는지 확인. 문제 있으면 다음 태스크로 넘어가지 말고 원인 파악

---

## Task 4: 문서화 + 커밋

**Files:**
- Create: `docs/ai/Collect_unsplash_data.md` (`docs/templete.md` 구조, WHY 중심 — 테마 3개를 왜 이걸로 골랐는지, 왜 CLIP까지 11차원으로 갔는지, 왜 이미지를 저장 안 하는지, 왜 `{theme, pos, neg}` 트리플렛 구조인지 등 이번 대화에서 확정된 결정들을 정리)
- 그 외 이 플랜에서 변경된 모든 파일(`Ai/collect_unsplash_data.py`, `tests/ai/test_collect_unsplash_data.py`, `tests/ai/test_collect_unsplash_data_integration.py`, `requirements.txt`)

- [ ] **Step 1: `/ai-commit` 절차로 진행**

`/ai-commit` 커맨드를 실행해 diff 검토 → `docs/ai/Collect_unsplash_data.md` 작성/반영 → 커밋 메시지 사용자 승인 → 커밋 순서를 따른다. Task 1~3에서 개별 커밋을 하지 않았으므로 이 태스크가 이 기능 전체의 첫 커밋이 된다.

- [ ] **Step 2: PR 생성 여부 확인**

이 작업 브랜치(`feature/unsplash-데이터-수집/9`)를 `develop`으로 머지할지, 이슈 #9를 어떻게 마무리할지 사용자에게 확인 (`/pr` 커맨드 활용 가능)
