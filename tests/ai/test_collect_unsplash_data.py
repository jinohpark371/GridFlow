"""Ai/collect_unsplash_data.py 트리플렛 샘플링 로직 단위 테스트.

네트워크·Unsplash API 키 없이 순수 로직만 검증 — 빠르게 실행됨.
"""

import random
from pathlib import Path
from unittest.mock import patch

import pytest
from collect_unsplash_data import collect_all_photos, sample_triplets, write_csv


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


def test_collect_all_photos_dedupes_cross_theme_photo_ids():
    """같은 photo_id가 여러 테마 검색 결과에 걸리면 먼저 등장한 테마 쪽만 남아야 함."""
    theme_a = "minimalist aesthetic photography"
    theme_b = "vintage retro film photography"

    search_results = {
        theme_a: [{"id": "shared_1"}, {"id": "only_a"}],
        theme_b: [{"id": "shared_1"}, {"id": "only_b"}],
    }

    def fake_search_photos(theme, access_key, per_page):
        return search_results[theme]

    def fake_photo_to_row(photo, theme):
        return {"photo_id": photo["id"], "query": theme}

    with patch("collect_unsplash_data.search_photos", side_effect=fake_search_photos), \
            patch("collect_unsplash_data.photo_to_row", side_effect=fake_photo_to_row):
        rows = collect_all_photos([theme_a, theme_b], access_key="dummy", per_page=2)

    photo_ids = [row["photo_id"] for row in rows]
    assert photo_ids.count("shared_1") == 1

    shared_row = next(row for row in rows if row["photo_id"] == "shared_1")
    assert shared_row["query"] == theme_a

    assert {row["photo_id"] for row in rows} == {"shared_1", "only_a", "only_b"}


def test_write_csv_writes_header_and_rows_to_file(tmp_path: Path):
    """write_csv가 헤더와 데이터 행을 올바르게 저장하는지 확인."""
    rows = [
        {"id": "1", "name": "photo_a"},
        {"id": "2", "name": "photo_b"},
    ]
    fieldnames = ["id", "name"]
    csv_path = tmp_path / "test.csv"

    write_csv(rows, csv_path, fieldnames)

    assert csv_path.exists()
    content = csv_path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")
    assert lines[0] == "id,name"
    assert lines[1] == "1,photo_a"
    assert lines[2] == "2,photo_b"
