# Frontend/CLAUDE.md

`Frontend/`에서 작업할 때 적용되는 세부 지침이다. 공통 규칙은 루트 [`AGENTS.md`](../AGENTS.md), 설계는 `docs/superpowers/specs/2026-10-12-frontend-deploy-design.md` 참고.

## 구조

- Next.js(App Router, TypeScript), `output: "export"` 정적 내보내기 → `out/`을 Netlify가 배포
- 주소는 `/` 하나. `components/GridFlowApp.tsx`가 `lib/state.ts` 리듀서로 단계(home → theme → pick → analyzing → result)를 전환한다
- `lib/`: 로직(순수 함수·API·리듀서). `components/`: 그리기 전용 — 서버 호출·상태 변경 로직을 넣지 않는다
- 스타일: 컴포넌트별 `*.module.css` + `app/globals.css`의 CSS 변수. Tailwind·CSS-in-JS 쓰지 않음
- `Frontend/AGENTS.md`는 Next.js가 자동 생성·유지하는 파일(번들 문서를 먼저 읽으라는 안내)이라 지우지 않는다 — 지워도 `next dev`가 다시 만든다

## 개발 환경

- Node 22(`.nvmrc`), 의존성은 정확한 버전 고정(`.npmrc`의 `save-exact=true`)
- 개발 서버: `npm run dev`(http://localhost:3000). 백엔드는 `uvicorn main:app --reload --app-dir Backend`(기본 CORS가 localhost:3000 허용)
- API 주소: 빌드 시 `NEXT_PUBLIC_API_BASE_URL`(없으면 `http://localhost:8000`)

## 테스트

- `npm test`(Vitest + Testing Library), `npm run typecheck`, `npm run lint`
- `npm run e2e`: 빌드 후 Playwright(Pixel 7 화면, API는 가짜 응답)
- 백엔드와 맞춰야 하는 값은 테스트가 원본 파일을 읽어 비교한다: `MAX_PHOTOS`(`Backend/main.py`), 테마 문장(`Ai/collect_unsplash_data.py`의 `THEMES`)
