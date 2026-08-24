# 색감 피처 추출 (`Ai/features.py`)

> 작성일: 2026-08-24 · 작성자: 진오 · 관련 이슈: feature/mlp-적합도-스코어링/1

## 📌 목적
사진 한 장을 받아 HSV 색감 특성(평균 색상/채도·명도 편차/대비/색상 분포)을 벡터화한다. MLP 스코어링(`Ai/mlp.py`)의 입력 피처 중 CLIP 유사도를 제외한 나머지 부분을 담당한다.

## 🧭 파이프라인 상 위치
Layer 1(테마 적합도 스코어링) 안에서 MLP 입력 피처를 준비하는 단계.

- Layer: Layer 1 · 테마 적합도 스코어링 > MLP 입력 피처 준비
- 이전 단계: CLIP 유사도 계산(`clip.py`)
- 다음 단계: `mlp.py`의 `build_feature_vector`에서 CLIP 유사도와 concat되어 `ScoringMLP` 입력(11d)이 됨

## 🔧 입출력 스펙

| 함수 | 입력 | 출력 | 설명 |
|---|---|---|---|
| `extract_color_features` | `Image.Image \| str \| Path` | `np.ndarray` (10d) | `[mean_h, mean_s, mean_v, sat_std, val_std, contrast, hue_hist(4)]`, 모두 0~1 정규화 |

## 🧠 설계 결정과 이유

- 결정: RGB가 아닌 HSV로 변환해 피처 추출
  - 이유: 색상(H)·채도(S)·명도(V)를 분리해서 다룰 수 있어 "채도가 높아서 제외" 같은 근거를 사용자에게 설명하기 쉬움 (Notion 설계 문서 7절 "제외 제안 근거"와 연결)
- 결정: `opencv-python`(cv2) 사용
  - 이유: `requirements.txt`에 이미 포함되어 있고, HSV 변환·히스토그램 계산이 표준적으로 지원됨
- 결정: 모든 값을 0~1로 정규화 (H는 179, S/V는 255로 나눔)
  - 이유: MLP 입력 스케일을 맞추기 위함 — 정규화 없이 넣으면 H/S/V 값 범위가 서로 달라 학습이 불안정해질 수 있음
- 결정: hue 히스토그램을 4bin으로 설정
  - 이유: Notion 설계 문서가 전체 입력을 "약 11차원"으로 명시(CLIP 유사도 1 + 색감 피처 10). 스칼라 6개(mean_h/s/v, sat_std, val_std, contrast)에 히스토그램 4bin을 더해 10차원을 맞춤. bin 수 자체에 실험적 근거는 없어 추후 조정 가능
- 결정: "직전 사진과의 색감 차이" 같은 피드 컨텍스트 피처는 포함하지 않음
  - 이유: Notion 설계 문서에서 해당 피처는 전이 비용(배치) 단계로 역할을 명시적으로 분리함 — 이 모듈은 사진 자체의 색감만 다룸

## ⚙️ 동작 흐름

```python
# 1) 사진 -> BGR ndarray -> HSV 변환
hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

# 2) 평균 색상 / 채도·명도 편차
mean_h, mean_s, mean_v = h.mean() / 179.0, s.mean() / 255.0, v.mean() / 255.0
sat_std, val_std = s.std() / 255.0, v.std() / 255.0

# 3) 대비 (grayscale 표준편차)
contrast = gray.std() / 255.0

# 4) hue 히스토그램(4bin, 정규화)
hue_hist = np.histogram(h, bins=4, range=(0, 180))[0]
hue_hist = hue_hist / hue_hist.sum()
```

## ⚠️ 알려진 제약 / TODO

- [ ] hue 히스토그램 bin 수(4), 정규화 방식 등은 실험적 근거 없이 "~11차원" 스펙에 맞춰 정한 값 — 실제 학습 데이터로 유효성 검증 필요
- [ ] contrast를 grayscale 표준편차(RMS contrast)로 근사 — Michelson contrast 등 다른 정의는 검토하지 않음
- [ ] 사진 1장 단위 처리만 지원 — 그룹 단위 배치 처리 최적화는 `clip.py`와 동일하게 미구현

## 🧪 사용 예시

```bash
python Ai/features.py photo.jpg
# 출력 예: color_features(10d): [0.36 0.26 ...]
```

## 🔗 참고

- Notion "MLP 모델 설계" 문서(흐름도 > MLP 모델 설계)
- `Ai/mlp.py` — 이 피처를 CLIP 유사도와 결합해 `ScoringMLP` 입력을 만듦
