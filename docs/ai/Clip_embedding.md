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
- [ ] 콜드스타트 baseline이 특정 사진 유형(저조도, 매크로 클로즈업 등)에서 상식과 다른 순위를 낼 수 있음 → 아래 "실전 테스트 결과" 참고, MLP 전환 시 보정 대상 후보

## 🧪 실전 테스트 결과 (2026-08-06)

같은 테마 문장을 서로 다른 두 사진에 적용해 점수를 비교. (참고: 여러 **테마 간** 점수 차이는 설계상 중요하지 않음 — 실제 서비스에서는 사용자가 테마 하나를 고정한 뒤 **같은 테마, 여러 사진 간** 순위만 사용하기 때문. 아래는 baseline의 방향성 점검용 참고 자료)

**photo1 (버드나무 사이로 강·다리가 보이는 대낮 풍경)**

| 테마 | 점수 |
|---|---|
| green color | 0.23 |
| travel snapshot | 0.23 |
| vintage film look | 0.22 |
| minimalist aesthetic | 0.21 |
| dark moody photography | 0.19 |

→ 순위가 사진 내용과 상식적으로 일치 (초록/여행 톤 높음, dark moody 낮음)

**photo2 (어두운 배경에 조명 받은 장미 매크로 클로즈업)**

| 테마 | 점수 |
|---|---|
| travel snapshot | 0.24 |
| dark moody photography | 0.22 |
| minimalist aesthetic | 0.22 |
| vintage film look | 0.21 |
| green color | 0.20 |

→ "green color" 최하위는 납득되나, "travel snapshot"이 1위로 나온 건 사진 내용(어두운 배경 매크로 샷)과 불일치. "dark moody photography"가 더 높아야 자연스러움

**해석**: CLIP 코사인 유사도는 원래 좁은 범위(대략 0.15~0.35)에 몰리는 특성이 있음(모달리티 갭). photo1처럼 일반적인 풍경 사진에서는 순위가 잘 맞았지만, photo2처럼 저조도·매크로 등 특이한 촬영 조건에서는 CLIP 단독 판단이 흔들릴 수 있음이 실측으로 확인됨. 이는 콜드스타트 baseline의 한계를 보여주는 사례이며, 사용자 피드백 기반 MLP 전환이 필요한 이유를 뒷받침함. 추후 MLP 성능 평가 시 이 photo2 케이스를 "CLIP이 틀렸던 사례"로 참고 가능.

## 🧪 사용 예시

```bash
python Ai/clip.py photo.jpg "미니멀 감성"
# 출력 예: 미니멀 감성 0.27
```

## 🔗 참고

- 관련 이슈: MLP 적합도 필터링 (feature/mlp-적합도-스코어링/1)
- 전체 아키텍처: `docs/architecture.md` (예정)