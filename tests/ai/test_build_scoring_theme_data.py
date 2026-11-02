"""Ai/build_scoring_theme_data.py 교차 clip_sim 수집 로직 단위 테스트.

네트워크·Unsplash API 키·CLIP 모델 없이 순수 로직만 검증 — 임베딩은 손으로 만든 벡터를 쓴다.
"""

import numpy as np
import pytest

from build_scoring_theme_data import (
    CROSS_CLIP_FIELDS,
    append_cross_clip_row,
    cross_clip_row,
    load_done_photo_ids,
    pending_rows,
)
from collect_unsplash_data import THEMES
from mlp import THEME_KEYS


def test_theme_keys_cover_exactly_the_collected_themes():
    assert set(THEME_KEYS) == set(THEMES)
    assert sorted(THEME_KEYS.values()) == ["golden", "mono", "vivid"]


def test_cross_clip_row_has_one_similarity_column_per_theme():
    image_vec = np.array([1.0, 0.0])
    theme_vecs = {
        "black and white monochrome photography": np.array([1.0, 0.0]),  # 같은 방향 -> 1.0
        "vibrant colorful photography": np.array([0.0, 1.0]),  # 직각 -> 0.0
        "warm golden hour sunset photography": np.array([-1.0, 0.0]),  # 반대 방향 -> -1.0
    }

    row = cross_clip_row("abc", image_vec, theme_vecs)

    assert list(row) == CROSS_CLIP_FIELDS
    assert row["photo_id"] == "abc"
    assert row["clip_mono"] == pytest.approx(1.0)
    assert row["clip_vivid"] == pytest.approx(0.0)
    assert row["clip_golden"] == pytest.approx(-1.0)


def test_pending_rows_skips_done_photos_and_stops_at_limit():
    source_rows = [{"photo_id": f"p{i}"} for i in range(5)]

    rows = pending_rows(source_rows, done_ids={"p0", "p2"}, limit=2)

    assert [r["photo_id"] for r in rows] == ["p1", "p3"]


def test_load_done_photo_ids_is_empty_when_file_missing(tmp_path):
    assert load_done_photo_ids(tmp_path / "cross_clip_sim.csv") == set()


def test_append_cross_clip_row_writes_header_once_and_resumes(tmp_path):
    path = tmp_path / "cross_clip_sim.csv"
    first = {"photo_id": "a", "clip_mono": 0.1, "clip_vivid": 0.2, "clip_golden": 0.3}
    second = {"photo_id": "b", "clip_mono": 0.4, "clip_vivid": 0.5, "clip_golden": 0.6}

    append_cross_clip_row(first, path)
    append_cross_clip_row(second, path)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == ",".join(CROSS_CLIP_FIELDS)
    assert len(lines) == 3  # 헤더 1줄 + 행 2줄 (헤더가 두 번 쓰이지 않음)
    assert load_done_photo_ids(path) == {"a", "b"}
