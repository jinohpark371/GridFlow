"""Ai/build_scoring_theme_data.py 단일 고정 테마 데이터 구성 로직 단위 테스트.

네트워크·Unsplash API 키 없이 순수 로직만 검증 — recompute_clip_sim은 목(mock) 처리.
"""

import random
from unittest.mock import patch

from build_scoring_theme_data import build_scoring_rows, sample_scoring_pairs
from collect_unsplash_data import FEATURE_FIELDS


def _fake_source_row(photo_id: str, theme: str) -> dict:
    row = {"photo_id": photo_id, "query": theme, "unsplash_url": f"https://unsplash.com/photos/{photo_id}"}
    for i, field in enumerate(FEATURE_FIELDS):
        row[field] = str(float(i))
    return row


def test_build_scoring_rows_keeps_pos_clip_sim_and_recomputes_neg_clip_sim():
    theme = "black and white monochrome photography"
    other_theme = "vibrant colorful photography"
    source_rows = (
        [_fake_source_row(f"bw{i}", theme) for i in range(3)]
        + [_fake_source_row(f"vc{i}", other_theme) for i in range(3)]
    )

    with patch("build_scoring_theme_data.recompute_clip_sim", return_value=0.999) as mock_recompute:
        rows = build_scoring_rows(source_rows, theme, n_pairs=2, access_key="dummy", rng=random.Random(0))

    pos_rows = [r for r in rows if r["photo_id"].startswith("bw")]
    neg_rows = [r for r in rows if r["photo_id"].startswith("vc")]

    assert len(pos_rows) == 3  # 흑백 테마 사진 전부가 pos 후보
    assert len(neg_rows) == 2  # n_pairs만큼만 neg로 뽑힘
    assert all(r["clip_sim"] == "0.0" for r in pos_rows)  # pos는 원래 clip_sim 그대로(재계산 안 함)
    assert all(r["clip_sim"] == 0.999 for r in neg_rows)  # neg는 recompute_clip_sim 결과로 대체됨
    assert mock_recompute.call_count == 2  # 딱 선택된 neg 수만큼만 재계산(불필요한 호출 없음)


def test_sample_scoring_pairs_pairs_pos_and_neg_ids_one_to_one():
    pos_ids = ["p1", "p2", "p3"]
    neg_ids = ["n1", "n2", "n3"]

    pairs = sample_scoring_pairs(pos_ids, neg_ids, "테마", rng=random.Random(0))

    assert len(pairs) == 3
    assert {p["pos"] for p in pairs} == set(pos_ids)
    assert {p["neg"] for p in pairs} == set(neg_ids)
    assert all(p["theme"] == "테마" for p in pairs)
