"""Ai/clip.py + build_feature_vector 통합 테스트.

실제 CLIP 모델(openai/clip-vit-base-patch32) 다운로드와 네트워크가 필요해 느림.
기본 `pytest` 실행에서는 제외되며(pytest.ini의 addopts), 명시적으로 실행하려면:

    pytest -m integration
"""

from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.integration

SAMPLE_PHOTO = Path(__file__).resolve().parents[2] / "samples" / "photo1.JPG"


def test_get_theme_score_is_a_valid_cosine_similarity():
    from clip import get_theme_score

    score = get_theme_score(SAMPLE_PHOTO, "미니멀한 감성 사진")

    assert -1.0 <= score <= 1.0


def test_build_feature_vector_matches_scoring_mlp_input_dim():
    from mlp import INPUT_DIM, build_feature_vector

    feats = build_feature_vector(SAMPLE_PHOTO, "미니멀한 감성 사진")

    assert feats.shape == (INPUT_DIM,)
    assert np.isfinite(feats).all()
