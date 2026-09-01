"""Ai/dataset.py + build_feature_vector 통합 테스트.

실제 CLIP 모델(openai/clip-vit-base-patch32) 다운로드와 네트워크가 필요해 느림.
기본 `pytest` 실행에서는 제외되며(pytest.ini의 addopts), 명시적으로 실행하려면:

    pytest -m integration
"""

import pytest
import torch

pytestmark = pytest.mark.integration


def test_build_pair_features_shapes_match_input_dim():
    from dataset import build_pair_features, load_label_pairs
    from mlp import INPUT_DIM

    pairs = load_label_pairs()[:2]  # 전체 12쌍을 다 태우면 느려서 shape 검증엔 일부만 사용
    feats_pos, feats_neg = build_pair_features(pairs)

    assert feats_pos.shape == (len(pairs), INPUT_DIM)
    assert feats_neg.shape == (len(pairs), INPUT_DIM)
    assert torch.isfinite(feats_pos).all()
    assert torch.isfinite(feats_neg).all()
