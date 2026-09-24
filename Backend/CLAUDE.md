# Backend/CLAUDE.md

`Backend/` 디렉터리에서 작업할 때 적용되는 세부 지침이다. 프로젝트 공통 규칙은 루트 [`AGENTS.md`](../AGENTS.md) 참고.

## 구조

- FastAPI 앱, `Backend/main.py`가 진입점
- `Ai/`는 패키지가 아니라 bare import 스크립트 스타일이라, `sys.path`에 `Ai/` 경로를 추가한 뒤 bare import로 재사용한다(`Backend/main.py` 상단 참고) — `Ai/` 쪽 컨벤션(상대 import 금지 등)은 건드리지 않는다
- 별도 가상환경을 만들지 않는다 — 저장소 루트 `.venv`/`requirements.txt`를 그대로 사용

## 개발 환경

- 실행: `uvicorn main:app --reload --app-dir Backend`
- 체크포인트(`Ai/checkpoints/scoring_mlp.pt`, `Ai/checkpoints/transition_cost_model.pt`)가 없으면 서버 시작이 실패한다 — 먼저 `Ai/evaluate_mlp.py`, `Ai/evaluate_transition_cost_model.py`를 실행해 체크포인트를 만들어야 한다

## 테스트

- `tests/backend/test_main.py`에 FastAPI `TestClient`로 작성. `python -m pytest`로 `tests/ai/`와 함께 실행됨(같은 `pytest.ini` 기준)

## 범위

- 이번 단계는 로컬 실행까지만 — Docker/클라우드 배포는 범위 밖(필요해지면 이 문서에 절 추가)
- 사진은 저장하지 않는다 — 업로드된 사진은 메모리에서 피처만 뽑고 버린다(S3 등 오브젝트 스토리지 없음)
