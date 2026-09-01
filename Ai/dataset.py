"""라벨 데이터(pos/neg 쌍)를 읽어 build_feature_vector로 피처화 (MLP 학습 입력 준비).

흐름: Ai/data/label_pairs.json({theme, pos, neg} 목록) -> 저장소 루트 기준으로
      사진을 열어 build_feature_vector로 피처화 -> (feats_pos, feats_neg) 텐서 쌍
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch

from mlp import build_feature_vector

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LABEL_PATH = Path(__file__).resolve().parent / "data" / "label_pairs.json"


def load_label_pairs(path: str | Path = DEFAULT_LABEL_PATH) -> list[dict]:
    """라벨 JSON({theme, pos, neg} 리스트)을 읽어 그대로 반환."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_pair_features(pairs: list[dict]) -> tuple[torch.Tensor, torch.Tensor]:
    """라벨 쌍 목록 -> (feats_pos, feats_neg) 텐서. mlp.rank_forward에 바로 사용 가능.

    쌍의 pos/neg 경로는 저장소 루트 기준 상대 경로("samples/...")로 저장돼 있어
    REPO_ROOT를 기준으로 절대 경로로 바꿔 읽는다.
    """
    feats_pos = [build_feature_vector(REPO_ROOT / pair["pos"], pair["theme"]) for pair in pairs]
    feats_neg = [build_feature_vector(REPO_ROOT / pair["neg"], pair["theme"]) for pair in pairs]

    return torch.from_numpy(np.stack(feats_pos)), torch.from_numpy(np.stack(feats_neg))


if __name__ == "__main__":
    pairs = load_label_pairs()
    feats_pos, feats_neg = build_pair_features(pairs)
    print(f"loaded {len(pairs)} pairs -> feats_pos {tuple(feats_pos.shape)}, feats_neg {tuple(feats_neg.shape)}")
