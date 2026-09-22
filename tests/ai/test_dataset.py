"""Ai/dataset.py 트리플렛/피처 로딩 단위 테스트.

CSV 파싱 + 딕셔너리 조회만 하므로 CLIP·네트워크 없이 빠르게 실행됨
(collect_unsplash_data.py가 피처를 이미 계산해 photos.csv에 저장해 두기 때문).
"""

import random

import numpy as np
import torch
from dataset import (
    DEFAULT_PAIRS_PATH,
    DEFAULT_PHOTOS_PATH,
    FEATURE_FIELDS,
    build_pair_features,
    load_label_pairs,
    load_photo_features,
    load_photo_pool,
    sample_theme_pair_features,
)


def _write_photos_csv(path, rows):
    import csv

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["photo_id", "query", "unsplash_url"] + FEATURE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _write_pairs_csv(path, rows):
    import csv

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["theme", "pos", "neg"])
        writer.writeheader()
        writer.writerows(rows)


def test_load_label_pairs_returns_theme_pos_neg_dicts(tmp_path):
    pairs_path = tmp_path / "pairs.csv"
    _write_pairs_csv(pairs_path, [{"theme": "minimal", "pos": "p1", "neg": "p2"}])

    pairs = load_label_pairs(pairs_path)

    assert pairs == [{"theme": "minimal", "pos": "p1", "neg": "p2"}]


def test_load_photo_features_maps_photo_id_to_11d_vector(tmp_path):
    photos_path = tmp_path / "photos.csv"
    feat_values = {field: str(i) for i, field in enumerate(FEATURE_FIELDS)}
    _write_photos_csv(photos_path, [{"photo_id": "p1", "query": "minimal", "unsplash_url": "u", **feat_values}])

    features = load_photo_features(photos_path)

    assert list(features.keys()) == ["p1"]
    np.testing.assert_array_equal(features["p1"], np.arange(len(FEATURE_FIELDS), dtype=np.float32))


def test_build_pair_features_looks_up_by_photo_id_not_by_reopening_images():
    pairs = [{"theme": "minimal", "pos": "p1", "neg": "p2"}]
    photo_features = {
        "p1": np.array([1.0] * len(FEATURE_FIELDS), dtype=np.float32),
        "p2": np.array([2.0] * len(FEATURE_FIELDS), dtype=np.float32),
    }

    feats_pos, feats_neg = build_pair_features(pairs, photo_features)

    assert feats_pos.shape == (1, len(FEATURE_FIELDS))
    assert feats_neg.shape == (1, len(FEATURE_FIELDS))
    assert torch.equal(feats_pos[0], torch.from_numpy(photo_features["p1"]))
    assert torch.equal(feats_neg[0], torch.from_numpy(photo_features["p2"]))


def test_load_photo_pool_groups_photo_ids_by_theme(tmp_path):
    photos_path = tmp_path / "photos.csv"
    feat_values = {field: "1.0" for field in FEATURE_FIELDS}
    _write_photos_csv(
        photos_path,
        [
            {"photo_id": "a1", "query": "minimal", "unsplash_url": "u", **feat_values},
            {"photo_id": "a2", "query": "minimal", "unsplash_url": "u", **feat_values},
            {"photo_id": "b1", "query": "vintage", "unsplash_url": "u", **feat_values},
        ],
    )

    features, by_theme = load_photo_pool(photos_path)

    assert set(features.keys()) == {"a1", "a2", "b1"}
    assert by_theme == {"minimal": ["a1", "a2"], "vintage": ["b1"]}


def test_sample_theme_pair_features_pos_pair_shares_theme_and_neg_pair_does_not():
    features = {pid: np.array([float(i)] * len(FEATURE_FIELDS), dtype=np.float32) for i, pid in enumerate(["a1", "a2", "b1", "b2"])}
    by_theme = {"a": ["a1", "a2"], "b": ["b1", "b2"]}
    id_by_feature_value = {0.0: "a1", 1.0: "a2", 2.0: "b1", 3.0: "b2"}
    theme_of = {"a1": "a", "a2": "a", "b1": "b", "b2": "b"}

    pos_a, pos_b, neg_a, neg_b = sample_theme_pair_features(features, by_theme, n_pairs=10, rng=random.Random(0))

    assert pos_a.shape == (10, len(FEATURE_FIELDS))
    for i in range(10):
        pos_a_id = id_by_feature_value[pos_a[i, 0].item()]
        pos_b_id = id_by_feature_value[pos_b[i, 0].item()]
        neg_a_id = id_by_feature_value[neg_a[i, 0].item()]
        neg_b_id = id_by_feature_value[neg_b[i, 0].item()]
        assert theme_of[pos_a_id] == theme_of[pos_b_id]
        assert theme_of[neg_a_id] != theme_of[neg_b_id]


def test_default_paths_point_to_valid_committed_data():
    """저장소에 커밋된 실제 데이터(Ai/data/unsplash/*.csv)가 스키마를 지키는지 확인."""
    pairs = load_label_pairs(DEFAULT_PAIRS_PATH)
    photo_features = load_photo_features(DEFAULT_PHOTOS_PATH)

    assert len(pairs) > 0
    for pair in pairs:
        assert pair.keys() == {"theme", "pos", "neg"}
        assert pair["pos"] in photo_features
        assert pair["neg"] in photo_features

    feats_pos, feats_neg = build_pair_features(pairs, photo_features)
    assert feats_pos.shape == (len(pairs), len(FEATURE_FIELDS))
    assert feats_neg.shape == (len(pairs), len(FEATURE_FIELDS))
    assert torch.isfinite(feats_pos).all()
    assert torch.isfinite(feats_neg).all()
