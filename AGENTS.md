# AGENTS.md

## 목적

이 문서는 코딩 에이전트가 `GridFlow` 저장소에 들어왔을 때 바로 작업을 시작할 수 있도록 프로젝트 구조와 협업 규칙을 전달하기 위한 가이드다. 파트별(Ai/Frontend/Backend) 세부 지침은 아래 각 파트 절과, 파트 디렉터리 안의 `CLAUDE.md`(있는 경우)에 있다. 이 중 놓치면 손해가 큰 항목만 [`CLAUDE.md`](CLAUDE.md)에 요약돼 있다.

## 프로젝트 구조

- `Ai/` — AI 파이프라인 코드. 세부는 [Ai 파트](#ai-파트), [`Ai/CLAUDE.md`](Ai/CLAUDE.md) 참고
- `Backend/` — [미정] 아직 비어있음. [Backend 파트](#backend-파트) 참고
- `Frontend/` — [미정] 아직 비어있음. [Frontend 파트](#frontend-파트) 참고
- `samples/` — 개발·테스트용 샘플 사진 (`photo1.JPG`, `photo2.JPG`, ... 순번 컨벤션)
- `docs/` — 파트별 설계 문서. 현재는 `docs/ai/`만 있음 (`docs/frontend/`, `docs/backend/` 등은 해당 파트 착수 시 정함)

## 착수 전 확인

- `git status`, `git branch --show-current`로 현재 상태 확인 — 브랜치 전략은 git-flow: `main` / `develop` / `feature/*`(→ `develop`) / `hotfix/*`, `release/*`(→ `main`)
- 관련 작업이 이미 이슈로 있는지 `gh issue list --search "<키워드>"`로 가볍게 확인 (중복 방지)
- PR을 만들 계획이면 base 브랜치를 넘겨짚지 않는다 — `feature/*`는 보통 `develop`을 향하고, `hotfix/*`/`release/*`만 `main`을 향한다. 애매하면 확인한다

## 작업 원칙

- 기존 구조와 패턴을 먼저 따르고, 필요가 명확할 때만 새 패턴을 추가한다
- 변경 범위는 가능한 한 작게 유지한다 — 코드 변경과 그에 대응하는 문서 변경을 하나의 논리 단위로 묶고, 서로 독립적인 변경은 커밋을 분리한다
- 하이퍼파라미터, 데이터 포맷, 스키마처럼 여러 선택지가 가능한 결정 지점은 구현 전에 가정을 명시하거나 먼저 물어본다 (`CLAUDE.md` 참고) — 이슈 체크리스트에 있는 항목이라도 예외 아니다
- 아직 비어있는 파트(Frontend/Backend)에 새 구조를 임의로 만들지 않는다 — 실제로 필요해질 때 정한다

---

## Ai 파트

- 구조·개발 환경·빌드/테스트 명령어·코드 스타일·검증 기준 등 세부 지침은 [`Ai/CLAUDE.md`](Ai/CLAUDE.md)에 있다 (`Ai/` 안에서 작업할 때 함께 참고)
- 요약: 패키지가 아닌 스크립트 스타일(bare import), `torch==2.5.1+cpu` 고정, 테스트/문서는 모듈당 1:1 대응(`tests/ai/test_<module>.py`, `docs/ai/<Module>.md`)

## Frontend 파트

[미정] 아직 코드가 없다. 프레임워크, 디렉터리 구조, 스타일 가이드 등 전부 미결정 상태 — 실제로 착수할 때 사용자와 먼저 정하고, 정해지면 `Frontend/CLAUDE.md`를 이 절과 함께 추가한다.

## Backend 파트

[미정] 아직 코드가 없다. 프레임워크, API 구조, DB 등 전부 미결정 상태 — 실제로 착수할 때 사용자와 먼저 정하고, 정해지면 `Backend/CLAUDE.md`를 이 절과 함께 추가한다.

---

## 커밋 규칙

- 한글로 작성하고, 형식은 `<type>(<scope>): <subject>` (`body`는 필요할 때만)
  - `type`: `feat` · `fix` · `docs` · `style` · `refactor` · `test` · `chore`
  - `scope`: 파트/모듈 단위로 붙인다. 애매하면 생략. 파트별 예시는 해당 파트의 `CLAUDE.md` 참고 (예: [`Ai/CLAUDE.md`](Ai/CLAUDE.md))
- 커밋 메시지 끝에는 Claude를 기여자로 표시하는 `Co-Authored-By` 트레일러를 포함한다 (임의로 빼지 않는다)
- 사용자가 명시적으로 요청하지 않는 한 커밋·푸시를 임의로 실행하지 않는다

## PR 작성 규칙

- `.github/pull_request_template.md` 양식을 **반드시** 그대로 따른다 (섹션 생략·재구성 금지)
- 절차는 `/pr` 커맨드(`.claude/commands/pr.md`) 참고. 제목/본문을 먼저 보여주고 승인받은 뒤 생성·push한다
- `기타 참고사항`에는 실제로 실행해서 확인한 것만 적는다 — 실행하지 않았으면 "미실행"이라고 명시

## Issue 작성 규칙

- `.github/ISSUE_TEMPLATE/issue-form.md` 양식을 **반드시** 그대로 따른다 (섹션 생략·재구성 금지)
- 절차는 `/issue` 커맨드(`.claude/commands/issue.md`) 참고. 제목/본문을 먼저 보여주고 승인받은 뒤 생성한다

## 언어

- 사용자와의 대화, 커밋 메시지, 문서(`docs/`)는 모두 한글로 작성한다
