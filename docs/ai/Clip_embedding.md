# CLIP 임베딩 추출 및 테마 적합도 계산 (`Ai/clip.py`)

> 작성일: 2026-08-06 · 작성자: 진오 · 관련 이슈: feature/mlp-적합도-스코어링/1

## 📌 목적
사진 한 장과 테마 문장(예: "미니멀한 감성 사진")을 입력받아, CLIP을 이용해 두 벡터를 뽑고 코사인 유사도로 **테마 적합도 점수(0~1)** 를 계산한다.

## 🧭 파이프라인 상 위치
전체 아키텍처 순서도 기준 "CLIP 임베딩 추출" 단계이며, Layer 1(테마 적합도 스코어링)의 **콜드스타트 baseline**으로 사용된다.

- Layer: Layer 1 · 테마 적합도 스코어링
- 이전 단계: 그룹별 사진 선택 · 사용자 지정
- 다음 단계: MLP 적합도 필터링 (사용자 피드백 누적 후 CLIP 유사도 → MLP로 전환)

## 🔧 입출력 스펙

| 함수 | 입력 | 출력 | 설명 |
|---|---|---|---|
| `get_image_embedding` | `Image.Image \| str \| Path` | `np.ndarray` (512d) | 사진 → 이미지 벡터 |
| `get_text_embedding` | `str` | `np.ndarray` (512d) | 테마 문장 → 테마 벡터 |
| `cosine_similarity` | `np.ndarray, np.ndarray` | `float` | 두 벡터 간 코사인 유사도 |
| `get_theme_score` | `image, theme_text` | `float` | 사진-테마 적합도 점수 (위 세 함수 결합) |

## 🧠 설계 결정과 이유

- 결정: 모델로 `openai/clip-vit-base-patch32` 사용
  - 이유: 이미지·텍스트 벡터를 모두 512차원으로 투영하는 경량 버전. LG Gram CPU 추론 환경에 적합하며, 아키텍처 문서상 512d 스펙과 일치
- 결정: `@lru_cache(maxsize=1)`로 모델 로딩 캐싱
  - 이유: 모델 로딩이 무거운 작업이라 매번 다시 부르면 성능 저하. 최초 1회만 로드 후 재사용
- 결정: 벡터 L2 정규화 후 코사인 유사도 계산
  - 이유: 벡터 길이를 1로 맞춰 방향(의미)만 비교하도록 함
- 결정: `get_image_embedding`이 `PIL.Image` 객체와 파일 경로(`str`/`Path`)를 모두 받도록 설계
  - 이유: 그룹 내 여러 사진을 순회하며 반복 스코어링할 때 이미 열려 있는 이미지 객체를 재사용할 수 있어 파일 재오픈 비용 절감
- 결정: `torch.no_grad()`로 그래디언트 계산 비활성화
  - 이유: 학습이 아닌 추론 전용이므로 메모리·속도 최적화
- 결정: 콜드스타트 단계에서는 MLP 대신 CLIP 유사도만으로 baseline 스코어링
  - 이유: 사용자 피드백(include/exclude)이 쌓이기 전까지는 학습 데이터가 없으므로, 사전학습된 CLIP의 zero-shot 유사도로 대체

## ⚙️ 동작 흐름

```python
# 1) 사진 → CLIP 이미지 인코더(ViT) → 이미지 벡터(512d)
image_vec = get_image_embedding(image)

# 2) 테마 문장 → CLIP 텍스트 인코더(Transformer) → 테마 벡터(512d)
theme_vec = get_text_embedding(theme_text)

# 3) 두 벡터의 Cosine Similarity → 테마 적합도 점수
score = cosine_similarity(image_vec, theme_vec)
```

## ⚠️ 알려진 제약 / TODO

- [ ] 파일명 `clip.py`가 `transformers` 등 외부 `clip` 관련 모듈명과 충돌 가능성 있음 → `clip_embedding.py` 등으로 리네이밍 검토
- [ ] 현재는 사진 1장 단위 처리만 지원 → 그룹 단위 배치(batch) 처리 최적화 필요 (다수 사진 순회 시 속도 개선 여지)
- [ ] MLP 스코어링으로 전환하는 시점(threshold) 검증 로직 미구현
- [ ] GPU 미보유 환경(LG Gram) 기준 실제 추론 속도 벤치마크 필요

## 🧪 사용 예시

```bash
python Ai/clip.py photo.jpg "미니멀 감성"
# 출력 예: 미니멀 감성 0.27
```

## 🔗 참고

- 관련 이슈: MLP 적합도 필터링 (feature/mlp-적합도-스코어링/1)
- 전체 아키텍처: `docs/architecture.md` (예정)