# AGENTS.md

## 목적

이 문서는 코딩 에이전트가 `GridFlow` 저장소에 들어왔을 때 바로 작업을 시작할 수 있도록 프로젝트 구조, 실행 방법, 코드 작성 규칙, 검증 방식, 협업 규칙을 전달하기 위한 가이드다. 이 중 놓치면 손해가 큰 항목만 [`CLAUDE.md`](CLAUDE.md)에 요약돼 있다.

## 프로젝트 구조

- `Ai/` — AI 파이프라인 코드. **패키지가 아니라 스크립트 스타일**(`__init__.py` 없음). 모듈끼리 `from clip import ...`처럼 같은 디렉터리 기준 bare import를 쓰고, `python <module>.py`로 직접 실행 가능하게 설계됨. 새 모듈을 추가할 때도 이 스타일을 유지한다 (패키지화·상대 import로 임의 전환하지 않는다)
- `tests/ai/test_<module>.py` — `Ai/<module>.py` 하나당 테스트 파일 하나. `tests/conftest.py`가 `Ai/`를 `sys.path`에 추가해서 bare import를 그대로 재사용
- `docs/ai/<Module>.md` — `Ai/<module>.py`의 설계 결정 문서. `docs/templete.md` 구조를 따르고, **코드로 알 수 있는 WHAT이 아니라 WHY**만 적는다 (라이브러리/모델 선택 이유, 트레이드오프)
- `Backend/`, `Frontend/` — 아직 비어있음
- `samples/` — 개발·테스트용 샘플 사진 (`photo1.JPG`, `photo2.JPG`, ... 순번 컨벤션)

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

## 착수 전 확인

- `git status`, `git branch --show-current`로 현재 상태 확인 — 브랜치 전략은 git-flow: `main` / `develop` / `feature/*`(→ `develop`) / `hotfix/*`, `release/*`(→ `main`)
- 관련 작업이 이미 이슈로 있는지 `gh issue list --search "<키워드>"`로 가볍게 확인 (중복 방지)
- PR을 만들 계획이면 base 브랜치를 넘겨짚지 않는다 — `feature/*`는 보통 `develop`을 향하고, `hotfix/*`/`release/*`만 `main`을 향한다. 애매하면 확인한다

## 작업 원칙

- 기존 구조와 패턴(스크립트 스타일, bare import, 테스트/문서 1:1 대응)을 먼저 따르고, 필요가 명확할 때만 새 패턴을 추가한다
- 변경 범위는 가능한 한 작게 유지한다 — `Ai/` 코드 변경과 그에 대응하는 `docs/ai/` 문서 변경을 하나의 논리 단위로 묶고, 서로 독립적인 변경은 커밋을 분리한다
- 하이퍼파라미터, 데이터 포맷, 스키마처럼 여러 선택지가 가능한 결정 지점은 구현 전에 가정을 명시하거나 먼저 물어본다 (`CLAUDE.md` 참고) — 이슈 체크리스트에 있는 항목이라도 예외 아니다
- `Backend/`, `Frontend/` 등 아직 비어있는 영역에 새 구조를 임의로 만들지 않는다 — 실제로 필요해질 때 정한다

## 코드 스타일 규칙

- `Ai/` 모듈끼리는 상대 import가 아니라 bare import(`from mlp import ScoringMLP`)를 쓴다 — 패키지화하지 않았기 때문
- 함수/모듈 docstring은 "무엇을(WHAT)"이 아니라 파이프라인 상 위치와 흐름(예: "사진 -> CLIP 이미지 인코더 -> 이미지 벡터")을 한두 줄로 적는다
- 새 모듈을 추가하면 `tests/ai/test_<module>.py`와 (설계 결정이 있다면) `docs/ai/<Module>.md`를 함께 추가한다

## 검증 기준

- 새 로직은 커밋 전에 관련 테스트를 실행해 통과를 확인한다 (`python -m pytest`, 필요하면 `-m integration`까지)
- CLIP·torch 모델을 실제로 태우는 검증은 느리므로(수십 초~수 분), 가능하면 unit 레벨(무작위 텐서 등)로 로직을 먼저 검증하고, 통합 테스트는 shape·finite 여부처럼 가벼운 assertion 위주로 최소한만 태운다
- 실행하지 못한 테스트가 있으면 결과 보고 시 명시한다 ("미실행"이라고 밝히지, 실행한 것처럼 적지 않는다)

## 커밋 규칙

- 한글로 작성하고, 형식은 `<type>(<scope>): <subject>` (`body`는 필요할 때만)
  - `type`: `feat` · `fix` · `docs` · `style` · `refactor` · `test` · `chore`
  - `scope`: 예) `clip`, `scoring`, `mlp`, `data`, `docs` — 애매하면 생략
- `Co-Authored-By` 줄은 추가하지 않는다
- 사용자가 명시적으로 요청하지 않는 한 커밋·푸시를 임의로 실행하지 않는다
- `Ai/` 변경 + 대응 `docs/ai/` 문서 반영 + 커밋은 `/ai-commit` 커맨드 절차를 따른다

## PR 작성 규칙

- `.github/pull_request_template.md` 양식을 **반드시** 그대로 따른다 (섹션 생략·재구성 금지)
- 절차는 `/pr` 커맨드(`.claude/commands/pr.md`) 참고. 제목/본문을 먼저 보여주고 승인받은 뒤 생성·push한다
- `기타 참고사항`에는 실제로 실행해서 확인한 것만 적는다 — 실행하지 않았으면 "미실행"이라고 명시

## Issue 작성 규칙

- `.github/ISSUE_TEMPLATE/issue-form.md` 양식을 **반드시** 그대로 따른다 (섹션 생략·재구성 금지)
- 절차는 `/issue` 커맨드(`.claude/commands/issue.md`) 참고. 제목/본문을 먼저 보여주고 승인받은 뒤 생성한다

## 언어

- 사용자와의 대화, 커밋 메시지, 문서(`docs/`)는 모두 한글로 작성한다

