"""Ai/collect_unsplash_data.py 트리플렛 샘플링 로직 단위 테스트.

네트워크·Unsplash API 키 없이 순수 로직만 검증 — 빠르게 실행됨.
"""

import random
from pathlib import Path

import pytest
from collect_unsplash_data import sample_triplets, write_csv


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
