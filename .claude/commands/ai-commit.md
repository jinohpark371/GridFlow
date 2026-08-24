---
description: Ai/ 변경사항을 docs/ai/ 문서에 반영하고 커밋
allowed-tools: Bash(git status), Bash(git diff *), Bash(git log *), Bash(git add *), Bash(git commit *), Read, Write, Edit, Glob, Grep
---

# Ai 커밋

`Ai/` 폴더의 변경사항을 확인하고, 필요하면 `docs/ai/`에 문서를 반영한 뒤, 프로젝트 컨벤션에 맞춰 커밋한다.

---

## Phase 1: 변경사항 파악

1. `git status`로 변경/추가된 파일 확인
2. `git diff HEAD -- Ai/`로 실제 변경 내용 확인 (스테이징 여부 관계없이 전체 diff)
3. `git log --oneline -5`로 최근 커밋 스타일 참고
4. `Ai/` 밖의 변경(`Backend/`, `Frontend/` 등)이 섞여 있으면 이 커맨드 범위 밖이므로 사용자에게 분리 여부를 확인

---

## Phase 2: 문서화 (설계 결정이 바뀌었을 때만, 선택적)

1. 변경된 `Ai/<module>.py`에 대응하는 `docs/ai/<Module>.md`가 있는지 확인
2. **없으면**: `docs/templete.md` 구조를 그대로 따라 새로 작성
3. **있으면**: 바뀐 부분만 갱신 — 특히 아래 섹션 위주
   - `🔧 입출력 스펙` (함수 시그니처가 바뀐 경우)
   - `🧠 설계 결정과 이유` (라이브러리/모델/방식을 바꾼 경우 — **왜** 바꿨는지가 핵심)
   - `⚠️ 알려진 제약 / TODO` (해결된 항목 체크, 새로 발견한 제약 추가)
4. 실전 테스트(정확도, 속도 등)를 진행했다면 `🧪 실전 테스트 결과 (YYYY-MM-DD)` 섹션을 추가
5. 원칙: 억지로 내용을 늘리지 않는다. 코드를 읽으면 알 수 있는 내용(WHAT)이 아니라, 코드만 봐서는 알 수 없는 배경(WHY)만 적는다
6. 사소한 변경(오타 수정, 리팩토링 등 설계 결정에 영향 없는 경우)은 문서화 생략 가능

---

## Phase 3: 커밋

1. `git status` / `git diff`로 최종 커밋 대상 확인
2. `Ai/` 코드 변경과 그에 대응하는 `docs/ai/` 문서 변경은 하나의 논리 단위로 묶는다. 서로 독립적인 변경(예: 별개 함수 두 개를 각각 수정)은 별도 커밋으로 분리
3. 커밋 메시지 형식 (Co-Authored-By 줄은 추가하지 않는다):
   ```text
   <type>(<scope>): <subject>

   <body>
   ```
   - `type`: `feat`(새 기능) · `fix`(버그 수정) · `docs`(문서 변경) · `style`(코드 포맷팅) · `refactor`(리팩토링) · `test`(테스트 추가/수정) · `chore`(기타 변경)
   - `scope`: 변경이 속한 영역. 애매하면 생략 가능(`<type>: <subject>`)
     - 예시: `clip`(CLIP 임베딩/`Ai/clip.py`) · `scoring`(테마 적합도 스코어링 전반) · `mlp`(MLP 적합도 필터링, 도입 후) · `data`(테스트용 사진 등 샘플 데이터) · `docs`(`docs/ai/` 문서)
   - `subject`: 한글로 간결하게 (예: `transformers 5.x API 변경에 맞춰 CLIP 임베딩 추출 로직 수정`)
   - `body`: 왜 바꿨는지 설명이 필요할 때만 작성 (한두 줄이면 생략 가능)
4. **커밋 전에 그룹핑 계획과 각 커밋 메시지를 사용자에게 보여주고 승인받는다**
5. 승인 후 그룹별로 `git add <관련 파일>` → `git commit -m "..."` 순서로 실행
6. 커밋 후 `git status`로 완료 확인

---

## 주의사항

- `__pycache__/` 등은 이미 `.gitignore` 대상이라 별도로 신경 쓸 필요 없음
- 사용자가 명시적으로 요청하지 않는 한 커밋을 임의로 실행하지 않는다
- push는 이 커맨드의 범위 밖 — 별도로 요청받았을 때만 수행
