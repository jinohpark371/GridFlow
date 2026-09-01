# Ai/CLAUDE.md

`Ai/` 디렉터리에서 작업할 때 적용되는 세부 지침이다. 프로젝트 공통 규칙은 루트 [`AGENTS.md`](../AGENTS.md), 놓치면 손해가 큰 3가지는 루트 [`CLAUDE.md`](../CLAUDE.md) 참고.

## 구조

- **패키지가 아니라 스크립트 스타일**(`__init__.py` 없음). 모듈끼리 `from clip import ...`처럼 같은 디렉터리 기준 bare import를 쓰고, `python <module>.py`로 직접 실행 가능하게 설계됨. 새 모듈을 추가할 때도 이 스타일을 유지한다 (패키지화·상대 import로 임의 전환하지 않는다)
- `tests/ai/test_<module>.py` — `Ai/<module>.py` 하나당 테스트 파일 하나. `tests/conftest.py`가 `Ai/`를 `sys.path`에 추가해서 bare import를 그대로 재사용
- `docs/ai/<Module>.md` — `Ai/<module>.py`의 설계 결정 문서. `docs/templete.md` 구조를 따르고, **코드로 알 수 있는 WHAT이 아니라 WHY**만 적는다 (라이브러리/모델 선택 이유, 트레이드오프)
- `docs/ai/output/` — 학습 loss curve, 점수 분포 등 시각화 결과물(PNG) 저장 위치. [미정: git에 커밋할지 여부 — 문서와 나란히 두는 취지로 우선 커밋하는 쪽으로 진행하되, 실행마다 그래프 값이 달라져 커밋 diff가 잦아지면 `.gitignore` 전환을 재검토한다]

## 개발 환경

- OS: Windows, Python 3.11.7
- 가상환경: `.venv`
  - 활성화(PowerShell): `.venv\Scripts\Activate.ps1`
  - 활성화(Git Bash): `source .venv/Scripts/activate`
  - 활성화가 안 됐는지 확인: `which python`(Git Bash) / `Get-Command python`(PowerShell)이 `.venv` 경로를 가리키는지 확인. anaconda 등 시스템 파이썬이 PATH 앞에 있으면 활성화해도 `pytest`/`python` 명령이 여전히 시스템 쪽을 가리킬 수 있음 — 그럴 땐 `.venv/Scripts/python.exe -m pytest`처럼 인터프리터를 직접 지정
- `requirements.txt`는 알파벳 순 정렬 유지, 버전 고정(`==`)
- `torch==2.5.1+cpu`로 고정돼 있음 — Windows에서 최신 버전이 `c10.dll` 로딩 오류를 일으켜서 다운그레이드한 것. 임의로 올리지 않는다

## 빌드 및 테스트 명령어

```bash
source .venv/Scripts/activate      # 가상환경 활성화 (Git Bash)
python -m pytest                   # 기본 실행: integration 마커 제외 (pytest.ini의 addopts)
python -m pytest -v -m integration # 통합 테스트까지 포함 (CLIP 모델 다운로드·네트워크 필요, 느림)
python Ai/<module>.py <args>       # 모듈 단독 실행 (스크립트 스타일이라 바로 실행 가능)
```

CLIP처럼 실제 모델 다운로드·네트워크가 필요한 무거운 테스트만 `@pytest.mark.integration`으로 분리한다. 순수 로직(피처 추출, MLP forward/loss, 데이터 로딩 등)은 마커 없이 빠르게 돈다. 자세한 절차는 `/ai-test` 커맨드(`.claude/commands/ai-test.md`) 참고.

## 코드 스타일 규칙

- `Ai/` 모듈끼리는 상대 import가 아니라 bare import(`from mlp import ScoringMLP`)를 쓴다 — 패키지화하지 않았기 때문
- 함수/모듈 docstring은 "무엇을(WHAT)"이 아니라 파이프라인 상 위치와 흐름(예: "사진 -> CLIP 이미지 인코더 -> 이미지 벡터")을 한두 줄로 적는다
- 새 모듈에 설계 결정이 있다면 `docs/ai/<Module>.md`를 함께 추가한다
- 테스트 코드(`tests/ai/test_<module>.py`)는 실제로 필요한 상황(복잡한 로직, 버그 재현, 수식/분기 검증 등)일 때만 작성한다 — 새 모듈을 추가할 때마다 자동으로 만들지 않고, 필요 여부가 애매하면 작성 전에 사용자에게 먼저 확인한다

## 검증 기준

- 새 로직은 커밋 전에 관련 테스트를 실행해 통과를 확인한다 (`python -m pytest`, 필요하면 `-m integration`까지)
- CLIP·torch 모델을 실제로 태우는 검증은 느리므로(수십 초~수 분), 가능하면 unit 레벨(무작위 텐서 등)로 로직을 먼저 검증하고, 통합 테스트는 shape·finite 여부처럼 가벼운 assertion 위주로 최소한만 태운다
- 실행하지 못한 테스트가 있으면 결과 보고 시 명시한다 ("미실행"이라고 밝히지, 실행한 것처럼 적지 않는다)

## 커밋 규칙 (Ai 관련 보충)

- `scope` 예시: `clip`(CLIP 임베딩/`Ai/clip.py`) · `scoring`(테마 적합도 스코어링 전반) · `mlp`(MLP 적합도 필터링) · `data`(테스트용 사진 등 샘플 데이터) · `docs`(`docs/ai/` 문서)
- `Ai/` 변경 + 대응 `docs/ai/` 문서 반영 + 커밋은 `/ai-commit` 커맨드 절차를 따른다
- 공통 커밋 형식(타입, 한글 작성, 승인 후 실행 등)은 루트 [`AGENTS.md`](../AGENTS.md) 참고

## 참고

- 이슈 체크리스트에 있는 항목이라도, 하이퍼파라미터/데이터 포맷/스키마처럼 여러 선택지가 있는 결정은 구현 전에 확인한다 (루트 `CLAUDE.md` 참고)
- `Backend/`, `Frontend/` 등 아직 비어있는 영역에 새 구조를 임의로 만들지 않는다
