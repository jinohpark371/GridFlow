# 프론트엔드 + 배포(CI/CD) 설계

> 작성일: 2026-10-12 · 작성자: 진오 · 관련 이슈: #18(비용 표 부분만 흡수)

## 📌 목적

인스타그램 사용자가 휴대폰 브라우저에서 **게시물 하나에 넣을 사진**을 고르면, 테마에 안 맞는 사진을 알려주고 캐러셀 안에서 넘겨 볼 순서를 추천하는 실서비스를 만든다. 지금까지 만든 `Ai/` 파이프라인과 `Backend/`의 `POST /arrange`를 그대로 쓰고, 프론트엔드를 새로 만들어 AWS(백엔드) + Netlify(프론트)에 CI/CD로 배포한다.

**성공 기준**
- 휴대폰에서 공개 URL로 접속해 "테마 선택 → 사진 고르기(최대 20장) → 결과 → 그리드에 쌓기"가 끝까지 동작한다
- 사진 20장 요청이 t3.small에서 60초(CloudFront 대기 한도) 안에 응답한다
- `main` 머지만으로 프론트·백엔드가 자동 배포되고, 이전 버전으로 되돌릴 수 있다

## 🧭 범위

**포함**
- `Frontend/` Next.js 앱 (정적 내보내기)
- 백엔드 변경: `order_items` 비용 표 미리 계산, CORS, 업로드 제한
- 배포: EC2 + CloudFront(백엔드), Netlify(프론트)
- CI(PR 검사) / CD(`main` 머지 시 배포)
- 문서: `docs/backend/Deploy.md`, 관련 기존 문서 갱신

**제외 (다음 단계)**
- #18의 나머지: 배치 추론, `async def arrange`의 이벤트 루프 블로킹
- 여러 게시물을 한 번에 정렬, 게시물끼리의 올릴 순서 추천
- 로그인, 서버·기기 저장(소개 모달 "봤음" 표시 1개 제외), 기존 피드 사진 불러오기
- 제거 후보를 다시 넣어 재정렬
- 자동 그룹핑, 자유 텍스트 테마
- Terraform 등 IaC, 커스텀 도메인, 모니터링 도구, 무중단 배포

## 🧠 설계 결정과 이유

| 결정 | 이유 | 포기한 것 |
|---|---|---|
| 모바일 우선 반응형 웹 | 설치 없이 접속, 배포가 단순 | 인스타 자동 업로드·갤러리 순서 저장(네이티브 앱) |
| 테마는 프리셋 3개 | ScoringMLP가 이 3개 문장으로만 학습됨 — 범위 밖 문장은 점수 신뢰도 미검증 | 자유 입력 |
| 요청 1번 = 게시물 1개 | 사용자는 게시물을 하나씩 만든다. 그룹 간 시간이 누적되지 않음 | 게시물 간 순서 추천 |
| 그리드는 만든 순서대로 왼쪽 위에 쌓기, 탭 안에서만 유지 | 인스타 프로필과 같은 모양, 저장 없음 원칙 | 새로고침 후 복원 |
| 프론트에서 긴 변 512px로 리사이즈 후 전송 | 실측: 장당 피처 추출 2.08초 → 0.50초. 19장 기준 점수 최대 차 0.028, 제거 판정 불일치 0, 점수 순위 동일 | 원본 해상도 분석 |
| `order_items`에서 비용 표(n×n) 한 번만 계산 | 실측: 8장 전체 탐색 82초(비용 함수 282,240회 호출, 고유 쌍은 56개). 표로 바꾸면 호출 n(n−1)회 | — (전체 탐색 기준 8장 유지, 결과 동일) |
| Next.js(TypeScript, `output: 'export'`) | 업계 표준 프레임워크 학습. 정적 파일이라 Netlify에 그대로 올라감 | React+Vite의 단순함 |
| CSS Modules + CSS 변수 | Next 내장, 빌드 시 일반 CSS. 런타임 CSS-in-JS(styled-components)는 App Router와 궁합이 나쁘고 유지보수 모드 | Tailwind의 작성 속도 |
| 한 페이지(`/`) 안에서 단계 전환 + `history.pushState` | 단계 사이에 File/Blob을 넘기기 쉬움, 뒤로가기 지원 | 단계별 URL |
| 백엔드 EC2 t3.small(x86) | 서버를 직접 다뤄보는 학습 목적. x86이라 `torch==2.5.1+cpu` 고정 유지 | Lambda의 거의 0원 비용, ARM(t4g)의 저렴함 |
| EC2 앞에 CloudFront(백엔드 전용) | 도메인·인증서 없이 HTTPS(`*.cloudfront.net`), EC2를 CloudFront에서만 접근 가능하게 막음 | 단일 주소(CORS 없음) |
| 프론트는 Netlify | 무료, GitHub 연동 자동 배포. Vercel Hobby는 비상업 용도 제한 | 전부 AWS로 통일 |
| CI/CD: GitHub Actions + ECR + SSM Run Command, OIDC 인증 | 2GB EC2에서 빌드하면 느리고 OOM 위험. 비밀키 저장 없음(OIDC), 22번 포트 닫음(SSM) | 구성 단순함(EC2 직접 빌드 + SSH) |
| Playwright E2E를 CI에 포함 | 6단계 화면 전환·뒤로가기 연결부와 실제 브라우저 리사이즈는 단위 테스트로 못 잡음 | CI 시간 1~2분 |

## ⚙️ 전체 구조

```
[휴대폰 브라우저]
   │ ① 화면  (HTTPS)  → Netlify: Frontend/out 정적 파일
   │ ② POST /arrange (HTTPS)
   ▼
[CloudFront xxxx.cloudfront.net]  캐시 끔 · 대기 60초 · Origin 헤더 전달
   │ ③ HTTP :8000 (보안 그룹: CloudFront 관리형 접두사 목록만 허용)
   ▼
[EC2 t3.small] Docker 컨테이너 → uvicorn → Backend/main.py → Ai/
```

### 요청 한 번의 흐름

1. 테마 선택: 한글 카드 → `lib/themes.ts`의 영어 문장
2. 사진 선택: 최대 20장, 초과분은 담지 않음
3. `lib/resize.ts`: `createImageBitmap(file, { imageOrientation: "from-image" })` → canvas 긴 변 512px → JPEG(0.85). 이름을 `0.jpg`, `1.jpg`, …로 새로 붙여 서버의 중복 파일명 거절을 피함
4. `lib/api.ts`: `FormData{ theme, photos, group_ids(전부 0) }` → `POST {NEXT_PUBLIC_API_BASE_URL}/arrange`, `AbortController` 65초
5. 서버: 기존 `/arrange` 그대로 (피처 → 0.35 미만 제거 후보 → 비용 표 정렬)
6. 응답 해석: `groups[0].order` → 캐러셀 순서, `removed_candidates` → 빼는 걸 추천, `skipped` → 분석 못 한 사진. 번호(`3.jpg`)를 썸네일로 되돌림
7. "그리드에 추가" → 게시물 목록 맨 앞에 삽입 → 그리드 왼쪽 위에 칸 생성

**API 계약(요청·응답 형태)은 바꾸지 않는다.**

## 🔧 백엔드 변경

### `Ai/arrange_photos.py` — `order_items`

```python
def order_items(feats, cost_fn, brute_force_max=8):
    n = len(feats)
    if n <= 1:
        return list(range(n))
    table = [[cost_fn(feats[i], feats[j]) if i != j else 0.0 for j in range(n)] for i in range(n)]
    ids = list(range(n))
    lookup = lambda i, j: table[i][j]
    if n <= brute_force_max:
        return _brute_force_order(n, ids, lookup)
    return _two_opt(_nearest_neighbor_order(n, ids, lookup), ids, lookup)
```

- 내부 함수는 `cost_fn(feats[a], feats[b])` 형태로만 비용을 물으므로, `feats` 자리에 번호 목록, `cost_fn` 자리에 표 조회를 넣어 **내부 함수는 수정하지 않는다**
- 시그니처·반환값·`brute_force_max=8` 유지. 같은 값으로 비교하므로 결과 순서 동일
- 대칭을 가정하지 않고 양방향 모두 계산(20장 = 380회, 약 0.1초)

### `Backend/main.py`

- CORS: `ALLOWED_ORIGINS` 환경변수(쉼표 구분, 기본값 `http://localhost:3000`) → `CORSMiddleware(allow_methods=["GET", "POST"], allow_headers=["*"])`
- `MAX_PHOTOS = 20`: 초과 시 `400`(한국어 메시지)
- `MAX_PHOTO_BYTES = 5 * 1024 * 1024`: 초과한 사진만 `skipped`(이유: 용량 초과), 나머지는 정상 처리

## 🖥️ 프론트 구성 (`Frontend/`)

### 화면 (단계)

| 단계 | 화면 | 내용 |
|---|---|---|
| `home` | 그리드 홈 | 3열 그리드(최신이 왼쪽 위), 칸 = 1번째 사진, 2장 이상이면 캐러셀 아이콘. 빈 상태 안내. "+ 새 게시물", `?`(소개 다시 보기) |
| `theme` | 테마 선택 | 카드 3장(흑백·비비드·골든아워), 한 줄 설명, 예시 색감 |
| `pick` | 사진 고르기 | 갤러리 선택, 썸네일·`n/20`·개별 삭제, "분석하기"(1장 이상) |
| `analyzing` | 분석 중 | 단계 문구(줄이는 중 → 보내는 중 → 분석 중), 10초 초과 시 "서버를 깨우는 중일 수 있어요". 에러 시 이 자리에 에러 카드 |
| `result` | 결과 | 캐러셀 순서(번호, 가로 스크롤), 빼는 걸 추천(점수), 분석 못 한 사진, "그리드에 추가" / "사진 다시 고르기" |
| `detail` | 게시물 상세 시트 | 캐러셀 순서, 테마, 삭제(시트 안에서 한 번 더 확인 — 브라우저 `confirm` 사용 안 함) |

- **소개 모달**: 첫 방문 시 슬라이드 3장(고르면 → 골라내고 → 순서 추천) + "시작하기". `localStorage`에 "봤음" 표시 하나만 저장, 읽기/쓰기 `try/catch` — 실패하면 매번 표시
- **뒤로가기**: 단계 전환마다 `history.pushState`, `popstate`에서 이전 단계로. `analyzing` 중 뒤로가기 = 요청 취소 후 `pick`
- **특수 경우**: 전부 제거 후보 → "이 테마와 어울리는 사진이 없어요" + 다른 테마로 해보기(그리드 추가 숨김). 1장 → 그 1장 + 제거 추천 여부만

### 파일

```
Frontend/
  app/layout.tsx, app/page.tsx (GridFlowApp: useReducer로 단계·게시물 관리), app/globals.css (CSS 변수, 라이트/다크)
  components/  FeedGrid · ThemePicker · PhotoPicker · AnalyzingView · ResultView · PostSheet · IntroModal (+ 각 .module.css)
  lib/         themes.ts · resize.ts · api.ts · state.ts · limits.ts(MAX_PHOTOS = 20)
```

- 컴포넌트는 그리기만 하고, 서버 호출·상태 변경 로직은 `lib/`에 둔다
- 썸네일은 리사이즈한 Blob의 `URL.createObjectURL`, 게시물 삭제 시 `revokeObjectURL`
- 디자인 방향: 사진이 주인공 — 무채색 바탕, 선 최소화, 강조색은 테마 카드·주요 버튼에만. 라이트/다크는 기기 설정을 따름. 세부는 구현 시 `frontend-design` 스킬로 다듬는다

## ⚠️ 에러 처리

원칙: 고른 사진은 에러가 나도 잃지 않는다. 다음 행동을 버튼으로 알려준다.

| 시점 | 상황 | 처리 / 표시 |
|---|---|---|
| 선택 | 20장 초과 | 앞 20장만 담음, "최대 20장까지 고를 수 있어요" |
| 리사이즈 | 브라우저가 못 여는 형식 | 그 사진만 빼고 "열 수 없는 사진 n장을 뺐어요" |
| 전송 | 연결 실패(오프라인·서버 다운·CORS) | `network` → "서버에 연결할 수 없어요" + 다시 시도 |
| 대기 | 65초 초과 / 504 | `timeout` → "분석이 너무 오래 걸려요. 사진 수를 줄여 보세요" + 다시 시도 |
| 응답 | 400 | `bad_request` → 서버 메시지 표시 + 사진 다시 고르기 (정상 흐름에선 버그) |
| 응답 | 500·502·503 | `server` → "잠시 문제가 생겼어요" + 다시 시도 |
| 결과 | `skipped` 있음 | 결과 아래 "분석하지 못한 사진 n장" |

- 에러 카드 버튼: **다시 시도**(이미 줄인 사진 그대로 재전송), **사진 다시 고르기**(고른 사진 유지한 채 `pick`)
- 서버 로그는 uvicorn 기본 출력 → `docker logs`

## 🚀 배포

리전: 서울(`ap-northeast-2`). 처음 한 번 하는 설정과 문제 해결 절차는 `docs/backend/Deploy.md`에 따라 할 수 있게 쓴다.

### AWS 계정
- 루트 MFA, 작업용 IAM 사용자. AWS Budgets 알림 $5 / $20 / $30

### EC2
- t3.small, Ubuntu 24.04 LTS, gp3 30GB, 스왑 2GB, 탄력적 IP(재시작해도 퍼블릭 DNS 고정 — CloudFront 오리진은 도메인 이름만 받음)
- 보안 그룹: 8000 ← `com.amazonaws.global.cloudfront.origin-facing` 만. **22번은 열지 않음**(Session Manager로 접속)
- IAM 역할(인스턴스 프로파일): `AmazonSSMManagedInstanceCore`, `AmazonEC2ContainerRegistryReadOnly`
- 실행: `docker run -d --name gridflow --restart unless-stopped -p 8000:8000 -e ALLOWED_ORIGINS=https://<netlify 주소> <ECR>/gridflow:<커밋 해시>`

### CloudFront (백엔드 전용)
- 오리진: EC2 퍼블릭 DNS, HTTP, 포트 8000, 응답 대기 60초
- 뷰어: HTTP → HTTPS 리다이렉트. 허용 메서드: GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE
- 캐시 정책 `CachingDisabled`, 오리진 요청 정책 `AllViewerExceptHostHeader`

### Netlify
- base `Frontend`, 빌드 `npm run build`, 게시 `Frontend/out`, `main` 자동 배포
- 환경변수 `NEXT_PUBLIC_API_BASE_URL` = CloudFront 주소
- PR 미리보기 주소는 CORS 허용 목록에 넣지 않음 — 미리보기에선 화면만 확인

### CI — `.github/workflows/ci.yml`
- 트리거: `develop`·`main` 대상 PR, 두 브랜치 push. 경로 필터로 바뀐 쪽만 실행
- 백엔드: `pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt` → `python -m pytest -m "not integration"`
- 프론트: `npm ci` → `tsc --noEmit` → 린트 → `vitest run` → `next build` → Playwright(Chromium)

### CD — `.github/workflows/deploy-backend.yml`
- 트리거: `main` push 중 `Ai/`, `Backend/`, `Dockerfile`, `requirements.txt` 변경 시 + `workflow_dispatch`(이미지 태그 입력 → 되돌리기)
- 단계: pytest → OIDC로 역할 획득 → `docker build`(GHA 캐시) → ECR push(`gridflow:<커밋 해시>`) → SSM Run Command(pull → 기존 컨테이너 삭제 → 실행) → CloudFront `/health` 200 확인(최대 3분)
- OIDC 신뢰 조건: `repo:jinohpark371/GridFlow:ref:refs/heads/main`
- ECR 수명 주기: 최근 이미지 3개 유지
- 업데이트 시 모델 로딩으로 1~2분 끊김 — 감수
- `develop`은 CI만, `main` 머지가 곧 배포 승인

### 예상 비용 (월, 크레딧 소진 후 — 계정 생성 후 요금 계산기로 재확인)

| 항목 | 금액 |
|---|---|
| EC2 t3.small | 약 $19 |
| EBS gp3 30GB | 약 $2.7 |
| 공인 IPv4 | 약 $3.6 |
| ECR | $1 미만 |
| CloudFront · Netlify · GitHub Actions | $0 |
| 합계 | 약 $26 |

## 🧪 테스트

### 백엔드·AI (pytest)
- `tests/ai/test_arrange_photos.py`
  - 새 `order_items` 결과 == 원래 방식으로 내부 함수를 직접 부른 결과 (5장 전체 탐색, 10장 근사 탐색)
  - 호출 횟수 세는 비용 함수로 정확히 n(n−1)회 호출 확인
  - 기존 테스트 수정 없이 통과
- `tests/backend/test_main.py`
  - CORS: 허용 Origin의 OPTIONS → `Access-Control-Allow-Origin` 있음, 비허용 → 없음
  - 21장 → 400, 5MB 초과 사진 → 그 사진만 `skipped`
- 속도: 변경 전후 측정값을 `docs/ai/Arrange_photos.md`에 기록

### 프론트
- Vitest: `themes.ts`(학습 문장 3개와 정확히 일치), `api.ts`(가짜 fetch로 네 가지 에러 분류, 응답 → 썸네일 순서 변환), `state.ts`(추가는 맨 앞, 삭제, 단계 전환)
- Testing Library: 결과 화면(순서 번호·제거 추천·건너뛴 사진), 전부 제거 안내, 빈 그리드
- Playwright(휴대폰 뷰포트, API는 route 가로채기로 가짜 응답): 소개 모달 → 새 게시물 → 테마 → 사진 3장 → 결과 → 그리드 칸 1개 → 상세 → 삭제 → 빈 그리드, 뒤로가기, 전송된 사진 긴 변 ≤ 512px

### 수동
- 실기기: 아이폰 사파리(HEIC → JPEG 변환, EXIF 회전), 안드로이드 크롬 다중 선택, 뒤로가기, 다크 모드
- 배포 후: CloudFront `/health`, Netlify에서 실제 분석(CORS), EC2 IP:8000 직접 접속 차단, `docker stats` 메모리, t3.small에서 8장·20장 응답 시간 → `MAX_PHOTOS` 확정

## ⚠️ 알려진 제약

- 서버는 프로세스 하나라 동시 요청은 줄을 선다(#18 이벤트 루프 블로킹). 2GB로는 다중 워커 불가
- CloudFront ↔ EC2 구간은 HTTP
- 콜드 스타트(서버 시작) 약 1분: import·체크포인트 56초 + 첫 CLIP 호출 11초(로컬 실측) — 배포 직후에만 해당
- t3.small 메모리(2GB) 충분 여부 미실측 — 배포 태스크에서 확인
- 위 실측(장당 0.5초, 8장 82초)은 로컬 PC(12스레드) 기준. t3.small은 더 느릴 수 있음

## 📎 문서 갱신

- `docs/ai/Arrange_photos.md`: 비용 표 결정·실측, 알려진 제약 갱신
- `Backend/CLAUDE.md`: CORS 환경변수, 업로드 제한, 배포 범위 문구
- `AGENTS.md`: Backend 요약("로컬 실행까지만") 수정, Frontend 파트 확정(Next.js·CSS Modules) + `Frontend/CLAUDE.md` 추가
- `docs/backend/Deploy.md` 신규
- #18에 "비용 표는 이번에 처리, 나머지는 남음" 코멘트 (승인 후)
