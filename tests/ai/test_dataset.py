"""Ai/dataset.py 학습 데이터 로딩·구성 단위 테스트.

CSV 파싱 + 딕셔너리 조회만 하므로 CLIP·네트워크 없이 빠르게 실행됨
(collect_unsplash_data.py가 피처를 이미 계산해 photos.csv에 저장해 두기 때문).
"""

import random

import numpy as np
import torch
from dataset import (
    DEFAULT_CROSS_CLIP_PATH,
    DEFAULT_PHOTOS_PATH,
    FEATURE_FIELDS,
    load_photo_pool,
    build_theme_labeled,
    build_theme_pairs,
    load_cross_clip_sim,
    sample_theme_pair_features,
    split_photos,
    theme_feature,
)


def _write_photos_csv(path, rows):
    import csv

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["photo_id", "query", "unsplash_url"] + FEATURE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


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


def test_default_photos_path_still_points_to_full_transition_data():
    """DEFAULT_PHOTOS_PATH(photos.csv)는 TransitionCostModel용 — scoring 데이터와 분리돼 있어야 함."""
    features, by_theme = load_photo_pool(DEFAULT_PHOTOS_PATH)

    assert len(features) > len(by_theme)  # 여러 테마에 걸쳐 다수의 사진이 있어야 함
    assert len(by_theme) >= 2


# --- 테마별 ScoringMLP 데이터 (cross_clip_sim.csv + photos.csv) ---

MONO = "black and white monochrome photography"
VIVID = "vibrant colorful photography"
GOLDEN = "warm golden hour sunset photography"


def _toy_pool():
    """테마마다 2장. 색감 피처는 사진마다 다른 값, photos.csv의 자기 테마 clip_sim은 -1로 둬서 교체 여부를 알 수 있게 함."""
    by_theme = {MONO: ["m1", "m2"], VIVID: ["v1", "v2"], GOLDEN: ["g1", "g2"]}
    features = {}
    for i, pid in enumerate(["m1", "m2", "v1", "v2", "g1", "g2"]):
        features[pid] = np.array([-1.0] + [float(i)] * (len(FEATURE_FIELDS) - 1), dtype=np.float32)
    # 사진 x 테마 문장 유사도: 사진 번호 * 0.1 + 테마별 오프셋
    offset = {MONO: 0.01, VIVID: 0.02, GOLDEN: 0.03}
    cross = {pid: {t: i * 0.1 + offset[t] for t in offset} for i, pid in enumerate(features)}
    return features, by_theme, cross


def test_load_cross_clip_sim_maps_columns_back_to_theme_text(tmp_path):
    import csv

    path = tmp_path / "cross_clip_sim.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["photo_id", "clip_mono", "clip_vivid", "clip_golden"])
        writer.writerow(["p1", "0.1", "0.2", "0.3"])

    cross = load_cross_clip_sim(path)

    assert cross == {"p1": {MONO: 0.1, VIVID: 0.2, GOLDEN: 0.3}}


def test_split_photos_holds_out_n_per_theme_without_overlap():
    by_theme = {t: [f"{t[:1]}{i}" for i in range(10)] for t in (MONO, VIVID, GOLDEN)}

    train, val = split_photos(by_theme, n_val=3, seed=0)

    for theme, ids in by_theme.items():
        assert len(val[theme]) == 3
        assert len(train[theme]) == 7
        assert set(train[theme]).isdisjoint(val[theme])
        assert set(train[theme]) | set(val[theme]) == set(ids)
    assert split_photos(by_theme, n_val=3, seed=0) == (train, val)  # 같은 seed면 같은 분할


def test_theme_feature_swaps_in_clip_sim_for_the_target_theme():
    features, _, cross = _toy_pool()

    feat = theme_feature("v1", MONO, features, cross)

    assert feat[0] == np.float32(cross["v1"][MONO])  # 비비드 사진을 흑백 문장으로 잰 값
    np.testing.assert_array_equal(feat[1:], features["v1"][1:])  # 색감 10d는 그대로
    assert features["v1"][0] == -1.0  # 원본 딕셔너리는 건드리지 않음


def test_build_theme_pairs_pairs_every_theme_photo_with_every_other_photo():
    features, by_theme, cross = _toy_pool()

    feats_pos, feats_neg = build_theme_pairs(VIVID, by_theme, features, cross)

    assert feats_pos.shape == (2 * 4, len(FEATURE_FIELDS))  # 비비드 2장 x 다른 테마 4장
    assert feats_neg.shape == (2 * 4, len(FEATURE_FIELDS))
    pos_colors = {round(v, 3) for v in feats_pos[:, 1].tolist()}
    neg_colors = {round(v, 3) for v in feats_neg[:, 1].tolist()}
    assert pos_colors == {2.0, 3.0}  # v1, v2
    assert neg_colors == {0.0, 1.0, 4.0, 5.0}  # m1, m2, g1, g2
    expected_clip = {round(cross[pid][VIVID], 3) for pid in ("m1", "m2", "g1", "g2")}
    assert {round(v, 3) for v in feats_neg[:, 0].tolist()} == expected_clip  # neg도 비비드 문장 기준


def test_build_theme_labeled_marks_only_the_target_theme_as_one():
    features, by_theme, cross = _toy_pool()

    feats, labels = build_theme_labeled(GOLDEN, by_theme, features, cross)

    assert feats.shape == (6, len(FEATURE_FIELDS))
    assert labels.tolist() == [0, 0, 0, 0, 1, 1]  # by_theme 순서: 흑백, 비비드, 골든아워


def test_committed_cross_clip_sim_covers_every_photo_for_every_theme():
    """저장소에 커밋된 cross_clip_sim.csv가 photos.csv의 모든 사진을 빠짐없이, 한 번씩 담고 있는지."""
    features, by_theme = load_photo_pool(DEFAULT_PHOTOS_PATH)
    cross = load_cross_clip_sim(DEFAULT_CROSS_CLIP_PATH)

    assert set(cross) == set(features)
    for sims in cross.values():
        assert set(sims) == set(by_theme)
        assert all(np.isfinite(v) for v in sims.values())
