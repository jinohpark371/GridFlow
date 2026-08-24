---
description: 현재 브랜치의 변경사항으로 PR 제목/본문을 작성하고, 가능하면 실제로 생성한다
allowed-tools: Bash(git status), Bash(git branch *), Bash(git log *), Bash(git diff *), Bash(git remote *), Bash(git push *), Bash(gh --version), Bash(gh auth status), Bash(gh pr create *), Read
---

# PR 생성

현재 브랜치의 변경사항을 정리해 PR 제목/본문을 작성하고, 가능하면 실제로 PR을 생성한다.

---

## Phase 1: 사전 확인

1. `git status` — 커밋 안 된 변경이 있으면 먼저 알린다. 임의로 커밋하지 않고, 필요하면 `/ai-commit` 등 별도 커맨드를 안내
2. `git branch --show-current` — 현재 브랜치 확인
3. **base 브랜치 결정** — 이 저장소는 git-flow 스타일(`main` / `develop` / `feature/*` / `hotfix/*`)을 쓴다
   - `feature/*`(대부분의 작업 브랜치) → `develop`
   - `hotfix/*`, `release/*` → `main`
   - 애매하면 넘겨짚지 말고 사용자에게 확인
4. `git log --oneline <base>..<현재 브랜치>` — 이 PR에 포함될 커밋 **전체**를 확인한다 (마지막 커밋 하나만 보고 판단하지 않는다)
5. `git diff <base>...HEAD` — 실제 변경 내용을 확인한다
6. 로컬이 원격보다 앞서 있으면(`git status`의 "ahead" 메시지) push가 필요 — push는 공유 상태를 바꾸는 행동이므로 실행 전 사용자 승인이 필요

---

## Phase 2: PR 제목/본문 작성

1. **본문은 반드시 `.github/pull_request_template.md`의 양식을 그대로 따른다.** 이 저장소는 해당 템플릿이 있으므로 임의의 자유 형식(요약 섹션 재구성, 섹션 생략/추가 등)으로 대체하지 않는다. `Read`로 템플릿을 먼저 읽고, 그 섹션 제목과 순서를 그대로 유지한 채 각 섹션을 채운다:
   - `📌 작업 개요` — 무엇을 했는지 간략히
   - `📌 작업 상세 내용` — 구체적으로 어떤 기능/변경이 이루어졌는지
   - `📌 관련 이슈` — 있으면 이슈/브랜치명 등, 없으면 "없음"으로 명시
   - `📌 스크린샷 (선택)` — UI 변경이 없으면 섹션은 남기고 "해당 없음"
   - `📌 기타 참고사항` — 리뷰어가 알아야 할 추가 사항 (테스트 계획은 여기에 포함)
   - 템플릿 파일 자체가 바뀌어 있을 수 있으니, 과거 대화나 기억이 아니라 **매번 다시 읽어서** 최신 섹션 구성을 기준으로 삼는다
2. **제목**은 70자 이내. 브랜치 전체의 커밋/diff를 아우르는 요약이지, 마지막 커밋 메시지를 그대로 베끼는 게 아니다
3. 각 섹션은 커밋 메시지를 나열하지 말고 "무엇을 / 왜"로 종합해서 서술
4. `기타 참고사항`(또는 테스트 계획 관련 섹션)에는 실제로 실행해서 확인한 것만 적는다 (예: `python -m pytest -v` 통과, `-m integration` 통과). 실행하지 않았다면 "미실행"이라고 명시하지, 했다고 적지 않는다

---

## Phase 3: 생성 — `gh` CLI 유무로 분기

1. `gh --version`으로 설치 여부 확인 (이 환경에는 기본적으로 설치돼 있지 않음 — Bash와 PowerShell 양쪽에서 미설치 확인됨. 새로 설치됐을 수 있으니 매번 다시 확인한다)

2. **`gh`가 있고 인증돼 있으면** (`gh auth status`로 확인)
   - 작성한 제목/본문을 사용자에게 보여주고 **승인받은 뒤**
   - `gh pr create --base <base> --title "<제목>" --body "$(cat <<'EOF'
     <본문>
     EOF
     )"` 실행
   - 생성된 PR URL을 사용자에게 전달

3. **`gh`가 없거나 미인증이면** (현재 기본 상황)
   - 사용자 승인 후 현재 브랜치를 원격에 push (`git push -u origin <브랜치>`, 이미 push돼 있으면 생략)
   - `git remote get-url origin`에서 `<owner>/<repo>`를 파싱해 Compare URL을 만들어 전달:
     `https://github.com/<owner>/<repo>/compare/<base>...<브랜치>?expand=1`
   - 작성한 제목/본문 텍스트를 그대로 보여줘서, 사용자가 그 URL을 열어 붙여넣기만 하면 되게 한다

---

## 주의사항

- PR 생성과 push는 되돌리기 번거로운 공유 행동 — **제목/본문을 반드시 먼저 보여주고 승인받는다**
- 커밋되지 않은 변경이 있어도 임의로 커밋하지 않는다
- draft PR, 리뷰어 지정, 라벨 등은 사용자가 명시적으로 요청했을 때만 추가
- base 브랜치를 임의로 `main`으로 넘겨짚지 않는다 — 이 저장소의 작업 브랜치는 보통 `develop`을 향한다
