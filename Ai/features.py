"""사진의 색감 피처 추출 (MLP 테마 적합도 스코어링 입력용).

흐름: 사진 -> HSV 변환 -> 평균 색상/채도·명도 편차/대비/색상 히스토그램 -> 색감 벡터(10d)
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image

HUE_HIST_BINS = 4
COLOR_FEATURE_DIM = 6 + HUE_HIST_BINS  # mean_h, mean_s, mean_v, sat_std, val_std, contrast + hue histogram


def _to_bgr_array(image: Image.Image | str | Path) -> np.ndarray:
    if isinstance(image, (str, Path)):
        image = Image.open(image)
    rgb = np.array(image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def extract_color_features(image: Image.Image | str | Path) -> np.ndarray:
    """사진 -> 색감 피처 벡터(10d).

    [mean_h, mean_s, mean_v, sat_std, val_std, contrast, hue_hist(4)] 를 모두 0~1로 정규화.
    """
    bgr = _to_bgr_array(image)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]

    mean_h, mean_s, mean_v = h.mean() / 179.0, s.mean() / 255.0, v.mean() / 255.0
    sat_std, val_std = s.std() / 255.0, v.std() / 255.0

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    contrast = gray.std() / 255.0

    hue_hist, _ = np.histogram(h, bins=HUE_HIST_BINS, range=(0, 180))
    hue_hist = hue_hist.astype(np.float32) / hue_hist.sum()

    return np.concatenate(
        [[mean_h, mean_s, mean_v, sat_std, val_std, contrast], hue_hist]
    ).astype(np.float32)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: python features.py <image_path>")
        raise SystemExit(1)

    feats = extract_color_features(sys.argv[1])
    print(f"color_features({len(feats)}d): {feats}")
