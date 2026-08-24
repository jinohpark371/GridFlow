"""CLIP 기반 이미지/텍스트 임베딩 추출 및 테마 적합도 계산.

흐름: 사진 -> CLIP 이미지 인코더(ViT) -> 이미지 벡터(512d)
      테마 문장 -> CLIP 텍스트 인코더(Transformer) -> 테마 벡터(512d)
      두 벡터의 Cosine Similarity -> 테마 적합도 점수
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

# clip-vit-base-patch32: 이미지/텍스트 벡터 모두 512차원으로 투영됨(순서도의 512d와 일치)
MODEL_NAME = "openai/clip-vit-base-patch32"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=1)
def _load_model() -> tuple[CLIPModel, CLIPProcessor]:
    model = CLIPModel.from_pretrained(MODEL_NAME, use_safetensors=True).to(DEVICE).eval()    
    processor = CLIPProcessor.from_pretrained(MODEL_NAME)
    return model, processor


def get_image_embedding(image: Image.Image | str | Path) -> np.ndarray:
    """사진 입력 -> CLIP 이미지 인코더(ViT) -> 이미지 벡터(512d)."""
    model, processor = _load_model()

    if isinstance(image, (str, Path)):
        image = Image.open(image).convert("RGB")

    inputs = processor(images=image, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        # transformers>=5: get_image_features가 512d 텐서 대신 BaseModelOutputWithPooling을
        # 반환하고, 투영된(512d) 벡터는 .pooler_output에 담겨 있음
        features = model.get_image_features(**inputs).pooler_output

    features = features / features.norm(p=2, dim=-1, keepdim=True)
    return features.squeeze(0).cpu().numpy()


def get_text_embedding(text: str) -> np.ndarray:
    """테마 문장 입력 -> CLIP 텍스트 인코더(Transformer) -> 테마 벡터(512d)."""
    model, processor = _load_model()

    inputs = processor(text=[text], return_tensors="pt", padding=True, truncation=True).to(DEVICE)
    with torch.no_grad():
        features = model.get_text_features(**inputs).pooler_output

    features = features / features.norm(p=2, dim=-1, keepdim=True)
    return features.squeeze(0).cpu().numpy()


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """이미지 벡터 vs 테마 벡터 Cosine Similarity 계산."""
    return float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))


def get_theme_score(image: Image.Image | str | Path, theme_text: str) -> float:
    """사진과 테마 문장을 받아 테마 적합도 점수를 반환."""
    image_vec = get_image_embedding(image)
    theme_vec = get_text_embedding(theme_text)
    return cosine_similarity(image_vec, theme_vec)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("usage: python clip.py <image_path> <theme_text>")
        raise SystemExit(1)

    score = get_theme_score(sys.argv[1], sys.argv[2])
    print(f"{sys.argv[2]} {score:.2f}")
