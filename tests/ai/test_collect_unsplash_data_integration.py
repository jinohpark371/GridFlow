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
