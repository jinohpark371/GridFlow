# Backend/main.py(FastAPI) 배포용 이미지. Ai/를 sys.path로 불러와 재사용하는 구조라
# 빌드 컨텍스트는 저장소 루트이고, Ai/와 Backend/를 함께 담는다.
FROM python:3.11-slim

WORKDIR /app

# Ai/features.py가 쓰는 cv2(opencv-python)가 slim 이미지엔 없는 libGL을 요구함
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 의존성 레이어를 코드보다 먼저 캐싱 — requirements.txt가 안 바뀌면 재빌드 시 재설치 스킵.
# torch/torchvision의 +cpu 빌드는 기본 PyPI가 아니라 PyTorch 전용 인덱스에만 있어서
# --extra-index-url이 없으면 설치가 실패한다(torch==2.5.1+cpu 고정 이유는 Ai/CLAUDE.md 참고).
COPY requirements.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# CLIP 가중치를 빌드 시점에 이미지에 구워 넣음 — 런타임에 네트워크 없이 바로 뜨게 하기 위함
RUN python -c "from transformers import CLIPModel, CLIPProcessor; \
    CLIPModel.from_pretrained('openai/clip-vit-base-patch32', use_safetensors=True); \
    CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')"

COPY Ai/ Ai/
COPY Backend/ Backend/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--app-dir", "Backend", "--host", "0.0.0.0", "--port", "8000"]
