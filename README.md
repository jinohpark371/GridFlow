# GridFlow

AI 기반 피드 미적 분석 및 업로드 순서 추천 서비스

사진 묶음과 테마 문장을 입력하면, ① 테마에 안 맞는 사진을 걸러내고 ② 남은 사진들을 서로 잘 어울리는 순서로 배치해 추천하는 것을 목표로 하는 개인 프로젝트입니다.

## 📌 현재 상태

AI 파이프라인(`Ai/`) 설계·검증 단계가 진행 중이며, `Backend/`·`Frontend/`는 아직 착수 전입니다.

| 단계 | 상태 | 설명 |
|---|---|---|
| 색감 피처 추출 | ✅ | OpenCV 기반 색감 피처(hue/saturation/value 등 10차원) |
| CLIP 콜드스타트 baseline | ✅ | 사진-테마 텍스트 유사도(1차원) |
| 테마 적합도 스코어링 (`ScoringMLP`) | ✅ | 부적합 사진 제외 "제안" + 유지 사진 점수화, 체크포인트 저장됨 |
| 전이 비용 학습 (`TransitionCostModel`) | ✅ | 사진 두 장의 어울림을 학습하는 페어와이즈 모델, 체크포인트 저장됨 |
| 사진 N장 정렬 알고리즘 | ⚠️ 재구현 필요 | 학습된 비용 모델을 실제로 그룹 정렬에 쓰는 조합 최적화 로직 미구현 |
| 학습 데이터 수집 | ✅ | Unsplash API 기반 준자동 수집(`Ai/collect_unsplash_data.py`) |
| 백엔드(API 서버) | ❌ 미착수 | 프레임워크/구조 미정 |
| 프론트엔드 | ❌ 미착수 | 미정 |
| 실사용자 피드백 루프 | ❌ 미착수 | 드래그 재정렬 등으로 실 데이터 수집 예정 |

## 🧭 아키텍처

전체 파이프라인은 두 계층으로 나뉩니다.

**Layer 1 · 테마 적합도 스코어링** — "이 사진이 이 테마에 얼마나 맞는가"
```
사진 + 테마 문장
  → CLIP 유사도(1d) + 색감 피처(10d) = 11차원 입력 벡터
  → ScoringMLP → 적합도 점수
  → 부적합 사진 "제외 제안" (자동 삭제 아님, 최종 결정은 사용자)
```

**Layer 2 · 전이 비용 배치** — "남은 사진들을 어떤 순서로 배치할까"
```
사진 두 장의 11차원 피처
  → TransitionCostModel(|A - B|) → 전이 비용 점수 (낮을수록 자연스러움)
  → (재구현 필요) 그룹 내 정렬 + 그룹 간 정렬 → 최종 순서
```

두 모델 모두 절대적인 정답 라벨이 아니라 **상대 비교(pairwise ranking)** 로 학습합니다. 사용자에게 "이 사진 0.7점"을 받을 방법은 없지만 "이 사진 유지, 저 사진 제외"나 "이 두 사진은 잘 어울린다/안 어울린다" 같은 상대적 피드백은 자연스럽게 쌓이기 때문입니다.

## 🛠 기술 스택

- **모델**: PyTorch, Hugging Face `transformers`(CLIP `openai/clip-vit-base-patch32`)
- **이미지 처리**: Pillow, OpenCV
- **데이터 수집**: Unsplash API, `httpx`
- **테스트**: `pytest`
- **시각화**: `matplotlib`

## 🚀 시작하기

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash 기준

# 의존성 설치
pip install -r requirements.txt

# 테스트 실행 (네트워크 필요한 통합 테스트는 기본 제외)
python -m pytest

# 개별 모듈 실행 예시
python Ai/mlp.py samples/photo1.JPG "미니멀한 감성 사진"
```

Unsplash 데이터 수집·재학습 스크립트를 실행하려면 저장소 루트에 `.env` 파일을 만들고 `UNSPLASH_ACCESS_KEY=<발급받은 키>`를 추가해야 합니다.

## 📁 프로젝트 구조

```
Ai/                    AI 파이프라인 (패키지가 아닌 스크립트 스타일)
  clip.py               CLIP 이미지/텍스트 임베딩
  features.py            색감 피처 추출
  mlp.py                 ScoringMLP (테마 적합도)
  transition_cost_model.py  TransitionCostModel (전이 비용, 페어와이즈)
  dataset.py              학습 데이터 로더
  collect_unsplash_data.py  Unsplash 데이터 수집
  checkpoints/             학습된 모델 가중치
  data/                    학습용 라벨/피처 데이터
Backend/                [미정] 아직 비어있음
Frontend/               [미정] 아직 비어있음
docs/ai/                모듈별 설계 결정 문서 (WHY 중심)
tests/ai/                모듈별 단위/통합 테스트
samples/                 개발용 샘플 사진
```

## 📚 문서

- 각 모듈의 설계 결정과 이유는 `docs/ai/<모듈명>.md`에 정리돼 있습니다 (예: [`docs/ai/Mlp_scoring.md`](docs/ai/Mlp_scoring.md), [`docs/ai/Transition_cost_model.md`](docs/ai/Transition_cost_model.md))
- 코딩 에이전트/협업 규칙은 [`AGENTS.md`](AGENTS.md) 참고
