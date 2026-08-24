"""Ai/features.py 색감 피처 추출 단위 테스트. 네트워크·모델 다운로드 없이 빠르게 실행됨."""

from pathlib import Path

import numpy as np
import pytest
from features import COLOR_FEATURE_DIM, HUE_HIST_BINS, extract_color_features
from PIL import Image

SAMPLE_PHOTO = Path(__file__).resolve().parents[2] / "samples" / "photo1.JPG"


def test_output_shape_matches_declared_dim():
    feats = extract_color_features(SAMPLE_PHOTO)
    assert feats.shape == (COLOR_FEATURE_DIM,)
    assert COLOR_FEATURE_DIM == 6 + HUE_HIST_BINS


def test_values_are_normalized_to_unit_range():
    feats = extract_color_features(SAMPLE_PHOTO)
    assert np.all(feats >= 0.0)
    assert np.all(feats <= 1.0 + 1e-6)


def test_hue_histogram_is_a_probability_distribution():
    feats = extract_color_features(SAMPLE_PHOTO)
    hue_hist = feats[-HUE_HIST_BINS:]
    assert hue_hist.sum() == pytest.approx(1.0, abs=1e-5)


def test_deterministic_for_same_input():
    a = extract_color_features(SAMPLE_PHOTO)
    b = extract_color_features(SAMPLE_PHOTO)
    np.testing.assert_array_equal(a, b)


def test_path_and_pil_image_input_produce_same_result():
    from_path = extract_color_features(SAMPLE_PHOTO)
    from_image = extract_color_features(Image.open(SAMPLE_PHOTO))
    np.testing.assert_allclose(from_path, from_image, atol=1e-6)
