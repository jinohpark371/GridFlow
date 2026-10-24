# 프론트엔드 + 배포(CI/CD) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 휴대폰 브라우저에서 게시물 하나 분량의 사진을 고르면 테마 부적합 사진과 캐러셀 순서를 추천하는 Next.js 프론트엔드를 만들고, 백엔드(EC2 + CloudFront)·프론트(Netlify)를 CI/CD로 배포한다.

**Architecture:** 백엔드는 API 계약을 그대로 두고 `order_items` 비용 표 미리 계산, CORS, 업로드 제한만 추가한다. 프론트는 `Frontend/`의 Next.js 정적 내보내기 앱으로, 한 페이지(`/`) 안에서 `useReducer` 상태로 단계를 전환하고, 로직은 `lib/`(순수 함수·API·리듀서)와 그리기 전용 `components/`로 나눈다. 배포는 GitHub Actions가 이미지를 빌드해 ECR에 올리고 SSM Run Command로 EC2 컨테이너를 교체하며, 프론트는 Netlify가 `main`을 자동 배포한다.

**Tech Stack:** FastAPI(기존), Next.js(App Router, TypeScript, `output: "export"`), CSS Modules, Vitest + Testing Library, Playwright, GitHub Actions, AWS(EC2 · ECR · SSM · CloudFront · IAM OIDC), Netlify

**Spec:** `docs/superpowers/specs/2026-10-12-frontend-deploy-design.md` (이슈 #22, 브랜치 `feature/프론트엔드-배포/22`)

## Global Constraints

- `Ai/`는 패키지가 아닌 스크립트 스타일(bare import) — 구조를 "개선"하지 않는다. `torch==2.5.1+cpu` 등 `requirements.txt` 고정 버전을 올리지 않는다
- 백엔드 API 계약(요청 `theme`·`photos`·`group_ids`, 응답 `removed_candidates`·`skipped`·`groups[].order/adjacency_costs`)은 바꾸지 않는다
- 사진은 서버에도 기기에도 저장하지 않는다. 기기 저장은 소개 모달 "봤음" 표시(`localStorage` 키 `gridflow:intro-seen`) 하나뿐
- 테마는 프리셋 3개, 영어 문장은 `Ai/collect_unsplash_data.py`의 `THEMES`와 글자 하나까지 같아야 한다: `black and white monochrome photography` / `vibrant colorful photography` / `warm golden hour sunset photography`
- 요청 1번 = 게시물 1개, `group_ids`는 전부 `0`. 최대 `MAX_PHOTOS = 20`장(프론트·백엔드 같은 값), 장당 `MAX_PHOTO_BYTES = 5MB`(백엔드)
- 프론트 리사이즈: 긴 변 `512`px, JPEG 품질 `0.85`, 파일명 `0.jpg`, `1.jpg`, …
- 프론트 요청 제한 시간 `65_000`ms, CloudFront 오리진 응답 대기 `60`초
- 스타일은 CSS Modules + `app/globals.css`의 CSS 변수. Tailwind·styled-components 사용 안 함
- npm 의존성은 정확한 버전으로 고정(`Frontend/.npmrc`의 `save-exact=true`), Node `22`(`Frontend/.nvmrc`)
- 화면 문구·커밋 메시지·문서는 한국어. 커밋 형식 `<type>(<scope>): <subject>`, `Co-Authored-By` 줄 없음
- 커밋·push·PR·이슈 코멘트·AWS/Netlify 콘솔 작업은 사용자 승인 후. 태스크 하나가 끝나면 `AGENTS.md`의 "작업 진행 방식" 형식으로 보고하고 멈춘다
- AWS 리전 `ap-northeast-2`, ECR 저장소 이름 `gridflow-backend`, 컨테이너 이름 `gridflow`, 배포 역할 `gridflow-github-deploy`, EC2 역할 `gridflow-ec2`

## Review Focus

- 루트 `.gitignore`의 `lib/`(Python 템플릿) 규칙이 `Frontend/lib/`를 무시해 커밋에서 빠진다 → 예외 규칙 추가 + `git check-ignore`로 확인 (Task 3)
- 사진 고르기를 여러 번 나눠 하면(15장 고르고 10장 더) 20장을 넘기거나, 빼고 다시 추가할 때 `0.jpg` 같은 id가 겹친다 → 남은 자리만큼만 받고, id는 증가하는 번호로 매긴다 (Task 6)
- 분석 중 뒤로가기로 취소한 요청의 응답이 늦게 도착해 다른 단계 화면을 덮어쓴다 → `analyzing`이 아닐 때 온 성공/실패는 무시 (Task 6)
- 서버 응답의 `order`·`removed_candidates`에 프론트가 모르는 id가 섞이면 화면이 깨진다 → 모르는 id는 걸러낸다 (Task 6)
- `localStorage`가 막힌 환경(사파리 시크릿 모드 등)에서 소개 모달을 닫아도 다시 떠서 앱을 못 쓴다 → 저장 실패 시 메모리에 기억 (Task 7)

---

## 파일 구조

| 파일 | 책임 |
|---|---|
| `Ai/arrange_photos.py` (수정) | `order_items`가 비용 표를 한 번 만들고 내부 탐색 함수에 표 조회를 넘김 |
| `Backend/main.py` (수정) | CORS 미들웨어, `MAX_PHOTOS`·`MAX_PHOTO_BYTES` 검사 |
| `Frontend/lib/limits.ts` | `MAX_PHOTOS` |
| `Frontend/lib/themes.ts` | 테마 3개(한글 이름·설명·영어 문장·색 견본) |
| `Frontend/lib/resize.ts` | `fitWithin`(크기 계산), `resizeImage`(canvas → JPEG Blob) |
| `Frontend/lib/api.ts` | `arrange()` 요청, 에러 4종 분류, 응답 → `ArrangeResult` |
| `Frontend/lib/state.ts` | 단계·초안·게시물 리듀서, `selectResultView`, `PREVIOUS_STEP` |
| `Frontend/lib/introSeen.ts` | 소개 모달 "봤음" 저장/구독 (`useSyncExternalStore`용) |
| `Frontend/components/*.tsx` | 그리기 전용 화면 조각 (`StepHeader`, `CarouselStrip`, `FeedGrid`, `PostSheet`, `IntroModal`, `ThemePicker`, `PhotoPicker`, `AnalyzingView`, `ResultView`) |
| `Frontend/components/GridFlowApp.tsx` | 리듀서·히스토리·API 호출을 묶는 최상위 클라이언트 컴포넌트 |
| `Frontend/e2e/flow.spec.ts` | Playwright 전체 흐름 |
| `.github/workflows/ci-backend.yml`, `ci-frontend.yml` | PR·push 검사 (spec의 `ci.yml`을 경로 필터가 단순하도록 두 파일로 나눔) |
| `.github/workflows/deploy-backend.yml` | `main` 머지 시 ECR push + SSM 배포 |
| `netlify.toml` | Netlify 빌드 설정 |
| `docs/backend/Deploy.md` | 처음 한 번 하는 설정 + 문제 해결 |

> spec과 다르게 정한 세부: ① spec의 `detail` 단계는 그리드 위에 뜨는 시트라 `step`이 아니라 `openPostId`로 표현한다. ② 사진 리사이즈는 "분석하기"가 아니라 사진을 고르는 순간 한다(썸네일도 작은 이미지로 그리기 위해). 그래서 분석 중 화면 문구는 "사진을 분석하고 있어요" 한 가지와 10초 후 안내로 단순화한다. ③ CI 파일을 둘로 나눈다.

---

### Task 1: `order_items` 비용 표 미리 계산

**Files:**
- Modify: `Ai/arrange_photos.py` (`order_items`)
- Test: `tests/ai/test_arrange_photos.py`
- Modify: `docs/ai/Arrange_photos.md`

**Interfaces:**
- Consumes: 없음
- Produces: `order_items(feats: list[np.ndarray], cost_fn: CostFn, brute_force_max: int = 8) -> list[int]` — 시그니처·반환값 그대로, `cost_fn` 호출이 정확히 `n*(n-1)`회

- [ ] **Step 1: 변경 전 속도 기록**

Run:
```bash
.venv/Scripts/python.exe -c "
import sys, time, functools
sys.path.insert(0, 'Ai')
import numpy as np
from transition_cost_model import load_checkpoint
from arrange_photos import model_cost_fn, order_items
model = load_checkpoint()
cost_fn = functools.partial(model_cost_fn, model)
rng = np.random.default_rng(0)
for n in [6, 8, 12, 20]:
    feats = [rng.random(11).astype(np.float32) for _ in range(n)]
    t = time.perf_counter()
    order_items(feats, cost_fn)
    print(f'{n}장: {time.perf_counter() - t:.2f}s')
"
```
Expected: 8장이 수십 초(이전 실측 82초). 출력값을 보고에 그대로 적는다.

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/ai/test_arrange_photos.py` 상단 import에 `_nearest_neighbor_order`를 추가하고(`_brute_force_order,` 다음 줄), 파일 끝에 추가:

```python
def test_order_items_calls_cost_fn_once_per_ordered_pair():
    """사진 쌍마다 비용을 한 번씩만 계산해야 한다 — 같은 쌍을 순서 후보마다 다시
    계산하면 8장 완전탐색에서 28만 번 넘게 호출돼 수십 초가 걸린다(이슈 #22 실측)."""
    calls = 0

    def cost_fn(a: np.ndarray, b: np.ndarray) -> float:
        nonlocal calls
        calls += 1
        return abs(float(a[0]) - float(b[0]))

    for n in [5, 10]:  # 5장 = 완전탐색, 10장 = greedy+2-opt
        calls = 0
        feats = [np.array([float(v)] + [0.0] * (INPUT_DIM - 1), dtype=np.float32) for v in range(n)]

        order_items(feats, cost_fn, brute_force_max=8)

        assert calls == n * (n - 1)


def test_order_items_matches_direct_search_results():
    """비용 표를 쓰도록 바꿔도 내부 탐색 함수를 원래 방식(사진 피처 + 비용 함수)으로
    직접 부른 결과와 같은 순서가 나와야 한다. 지금도 통과해야 하는 회귀 방지 테스트."""
    torch.manual_seed(0)
    model = TransitionCostModel()
    model.eval()
    cost_fn = functools.partial(model_cost_fn, model)

    feats5 = [_feat(i) for i in range(5)]
    assert order_items(feats5, cost_fn, brute_force_max=8) == _brute_force_order(5, feats5, cost_fn)

    feats10 = [_feat(i) for i in range(10)]
    expected10 = _two_opt(_nearest_neighbor_order(10, feats10, cost_fn), feats10, cost_fn)
    assert order_items(feats10, cost_fn, brute_force_max=8) == expected10
```

파일 상단 `import pytest` 다음 줄에 `import torch` 추가.

- [ ] **Step 3: 실패 확인**

Run: `.venv/Scripts/python.exe -m pytest tests/ai/test_arrange_photos.py -v`
Expected: `test_order_items_calls_cost_fn_once_per_ordered_pair` FAIL (`assert 480 == 20` 류), `test_order_items_matches_direct_search_results` PASS, 기존 테스트 PASS

- [ ] **Step 4: 구현**

`Ai/arrange_photos.py`의 `order_items`를 아래로 교체:

```python
def order_items(feats: list[np.ndarray], cost_fn: CostFn, brute_force_max: int = 8) -> list[int]:
    """전이 비용 총합이 최소가 되는 순서(원본 인덱스 리스트)를 반환.

    사진 수가 적으면(<= brute_force_max) 완전탐색, 많으면 greedy(최근접 이웃) + 2-opt.
    사진 쌍별 비용은 처음에 표로 한 번만 계산한다 — 내부 탐색 함수는 cost_fn(feats[a], feats[b])
    형태로만 비용을 묻기 때문에, feats 자리에 번호 목록을, cost_fn 자리에 표 조회를 넘기면
    내부 함수를 고치지 않고도 같은 쌍을 반복 계산하지 않게 된다(8장 완전탐색 282,240회 -> 56회).
    """
    n = len(feats)
    if n <= 1:
        return list(range(n))

    table = [[cost_fn(feats[i], feats[j]) if i != j else 0.0 for j in range(n)] for i in range(n)]

    def lookup(i: int, j: int) -> float:
        return table[i][j]

    ids = list(range(n))
    if n <= brute_force_max:
        return _brute_force_order(n, ids, lookup)
    return _two_opt(_nearest_neighbor_order(n, ids, lookup), ids, lookup)
```

- [ ] **Step 5: 통과 확인**

Run: `.venv/Scripts/python.exe -m pytest tests/ai/test_arrange_photos.py -v`
Expected: 전부 PASS (기존 9개 + 새 2개)

- [ ] **Step 6: 변경 후 속도 기록**

Step 1 명령을 다시 실행. Expected: 8장·20장 모두 1초 안팎. 전후 숫자를 보고와 문서에 적는다.

- [ ] **Step 7: 전체 테스트**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 전부 PASS (integration 제외)

- [ ] **Step 8: 문서 갱신**

`docs/ai/Arrange_photos.md`의 `## 🧠 설계 결정과 이유` 마지막 항목 뒤에 추가(숫자는 Step 1·6 실측값으로 채운다):

```markdown
- 결정: `order_items`가 시작할 때 사진 쌍별 비용 표(n×n)를 한 번만 만들고, 내부 탐색 함수에는 사진 대신 번호 목록과 표 조회 함수를 넘김 (이슈 #22)
  - 이유: 완전탐색은 순서 후보마다 인접 쌍 비용을 다시 계산해서, 8장 기준 고유한 쌍은 56개뿐인데 비용 함수(=TransitionCostModel 실행)를 282,240번 호출했다(로컬 실측 82초). 표를 쓰면 호출이 n(n−1)번으로 줄어 8장 <변경 후>초, 20장 <변경 후>초. 내부 함수(`_brute_force_order`, `_two_opt` 등)는 `cost_fn(feats[a], feats[b])` 형태로만 비용을 묻기 때문에 시그니처를 바꾸지 않고 적용할 수 있었다. 대칭은 가정하지 않고 양방향을 다 계산한다(20장도 380번)
```

`## ⚠️ 알려진 제약 / TODO`의 두 번째 항목(`brute_force_max=8` 초과 시 … 실측하지 않음)을 다음으로 교체:

```markdown
- [ ] 비용 표 이후 남은 병목은 장당 피처 추출(CLIP, 512px 기준 장당 약 0.5초)과 `async def arrange`의 이벤트 루프 블로킹 — #18에 남김
```

- [ ] **Step 9: 커밋 (승인 후)**

```bash
git add Ai/arrange_photos.py tests/ai/test_arrange_photos.py docs/ai/Arrange_photos.md
git commit -m "perf(arrange): order_items 사진 쌍 비용 표 미리 계산 (#22)"
```

- [ ] **Step 10: #18 코멘트 (승인 후)**

```bash
gh issue comment 18 --body "비용 표 미리 계산(\`order_items\`)은 #22에서 처리했습니다(8장 완전탐색 <변경 전>초 → <변경 후>초). 배치 추론과 \`async def arrange\` 이벤트 루프 블로킹은 이 이슈에 남겨 둡니다."
```

---

### Task 2: 백엔드 CORS + 업로드 제한

**Files:**
- Modify: `Backend/main.py`
- Test: `tests/backend/test_main.py`
- Modify: `Backend/CLAUDE.md`

**Interfaces:**
- Consumes: 없음
- Produces: `main.MAX_PHOTOS = 20`, `main.MAX_PHOTO_BYTES = 5 * 1024 * 1024`, `main.ALLOWED_ORIGINS: list[str]`(환경변수 `ALLOWED_ORIGINS`, 쉼표 구분, 기본 `http://localhost:3000`). 21장 이상 → 400 `detail` "사진은 최대 20장까지 보낼 수 있음", 5MB 초과 → `skipped`의 `reason` "용량 초과(5MB 제한)"

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/backend/test_main.py` 상단 import에 추가:

```python
import numpy as np
from mlp import INPUT_DIM
```

파일 끝에 추가:

```python
def test_cors_allows_configured_origin():
    from main import app

    with TestClient(app) as client:
        response = client.options(
            "/arrange",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_does_not_allow_unknown_origin():
    from main import app

    with TestClient(app) as client:
        response = client.options(
            "/arrange",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
        )

    assert "access-control-allow-origin" not in response.headers


def test_arrange_rejects_more_than_max_photos():
    from main import MAX_PHOTOS, app

    count = MAX_PHOTOS + 1
    with TestClient(app) as client:
        response = client.post(
            "/arrange",
            data={"theme": "테마", "group_ids": [0] * count},
            files=[("photos", (f"{i}.jpg", b"x", "image/jpeg")) for i in range(count)],
        )

    assert response.status_code == 400
    assert f"최대 {MAX_PHOTOS}장" in response.json()["detail"]


def test_arrange_skips_photo_over_size_limit(monkeypatch):
    """5MB를 넘는 사진은 그 사진만 skipped로 돌려보내고 나머지는 정상 처리한다.
    CLIP을 태우지 않도록 피처 추출을 고정 벡터로 바꾼다(그래서 integration 아님)."""
    import main

    monkeypatch.setattr(main, "build_feature_vector", lambda image, theme: np.zeros(INPUT_DIM, dtype=np.float32))
    monkeypatch.setattr(main, "THRESHOLD", -1e9)
    too_big = b"0" * (main.MAX_PHOTO_BYTES + 1)

    with TestClient(main.app) as client:
        response = client.post(
            "/arrange",
            data={"theme": "테마", "group_ids": [0, 0]},
            files=[
                ("photos", _sample_file("photo1.JPG")),
                ("photos", ("big.jpg", too_big, "image/jpeg")),
            ],
        )

    assert response.status_code == 200
    body = response.json()
    assert [item["photo_id"] for item in body["skipped"]] == ["big.jpg"]
    assert "용량" in body["skipped"][0]["reason"]
    assert body["groups"][0]["order"] == ["photo1.JPG"]
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/Scripts/python.exe -m pytest tests/backend/test_main.py -v`
Expected: 새 4개 FAIL (`ImportError: cannot import name 'MAX_PHOTOS'`, CORS 헤더 없음, `skipped` 이유가 이미지 열기 실패 메시지)

- [ ] **Step 3: 구현**

`Backend/main.py` 상단 `import sys` 위에 `import os` 추가, `from fastapi import FastAPI  # noqa: E402` 다음 줄에 추가:

```python
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
```

`app = FastAPI(lifespan=lifespan)` 다음에 추가:

```python
# 프론트(Netlify)는 백엔드(CloudFront)와 주소가 달라 브라우저가 CORS 허락을 확인한다.
# 허용 주소는 코드에 박지 않고 환경변수로 받는다 — 주소가 바뀌어도 재빌드 없이 docker run -e로 바꿀 수 있게
ALLOWED_ORIGINS = [
    origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

`BRUTE_FORCE_MAX = 8` 다음에 추가:

```python
MAX_PHOTOS = 20  # 인스타그램 캐러셀 최대치. Frontend/lib/limits.ts와 같은 값
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 프론트는 512px로 줄여 보내므로 정상 사용에선 안 걸림 — 원본 직접 전송 방어용
```

`arrange` 안 `if not photos:` 검사 다음에 추가:

```python
    if len(photos) > MAX_PHOTOS:
        raise HTTPException(400, f"사진은 최대 {MAX_PHOTOS}장까지 보낼 수 있음")
```

반복문의 `content = await photo.read()` 다음 줄에 추가:

```python
            if len(content) > MAX_PHOTO_BYTES:
                skipped.append(
                    {"photo_id": photo.filename, "reason": f"용량 초과({MAX_PHOTO_BYTES // (1024 * 1024)}MB 제한)"}
                )
                continue
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: 전부 PASS

- [ ] **Step 5: `Backend/CLAUDE.md` 갱신**

`## 테스트` 절 위에 추가:

```markdown
## 요청 제한 · CORS

- `MAX_PHOTOS = 20`: 요청 하나의 사진이 이보다 많으면 400. `Frontend/lib/limits.ts`의 같은 이름 상수와 값을 맞춘다(프론트 테스트가 이 파일을 읽어 비교함)
- `MAX_PHOTO_BYTES = 5MB`: 넘는 사진은 그 사진만 `skipped`(이유: 용량 초과)
- CORS 허용 주소는 환경변수 `ALLOWED_ORIGINS`(쉼표 구분). 기본값은 Next 개발 서버 `http://localhost:3000`. 운영에서는 `docker run -e ALLOWED_ORIGINS=https://<netlify 주소>`
```

- [ ] **Step 6: 커밋 (승인 후)**

```bash
git add Backend/main.py tests/backend/test_main.py Backend/CLAUDE.md
git commit -m "feat(backend): CORS 허용 주소 환경변수화 + 업로드 장수·용량 제한 (#22)"
```

---

### Task 3: `Frontend/` 초기 구성

**Files:**
- Create: `Frontend/` 전체(create-next-app), `Frontend/.npmrc`, `Frontend/.nvmrc`, `Frontend/next.config.ts`, `Frontend/vitest.config.mts`, `Frontend/vitest.setup.ts`, `Frontend/playwright.config.ts`, `Frontend/app/globals.css`, `Frontend/app/layout.tsx`, `Frontend/app/page.tsx`, `Frontend/lib/limits.ts`, `Frontend/lib/limits.test.ts`, `Frontend/CLAUDE.md`
- Modify: `.gitignore`, `AGENTS.md` (Frontend 파트)

**Interfaces:**
- Consumes: `Backend/main.py`의 `MAX_PHOTOS = 20` (Task 2)
- Produces: `@/lib/limits`의 `MAX_PHOTOS: number`; npm 스크립트 `dev`·`build`·`lint`·`typecheck`·`test`·`e2e`; 경로 별칭 `@/*` = `Frontend/*`

- [ ] **Step 1: Next.js 생성**

`Frontend/`가 비어 있는지 확인(`ls -A Frontend` 결과 없음) 후:

```bash
cd Frontend
npx create-next-app@latest . --ts --eslint --app --no-tailwind --no-src-dir --import-alias "@/*" --use-npm --yes
```

질문이 더 뜨면 기본값을 고른다(React Compiler 등). 생성된 Next.js·React 버전을 보고에 적는다.

- [ ] **Step 2: 버전 고정 + Node 버전**

```bash
printf "save-exact=true\n" > .npmrc
printf "22\n" > .nvmrc
node -e "const fs=require('fs');const p=require('./package.json');for(const k of ['dependencies','devDependencies'])for(const d in p[k]||{})p[k][d]=require('./node_modules/'+d+'/package.json').version;fs.writeFileSync('package.json',JSON.stringify(p,null,2)+'\n')"
npm install
```

Expected: `package.json`에 `^`가 없다(`grep -c "\^" package.json` → 0).

- [ ] **Step 3: 테스트 도구 설치**

```bash
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/dom @testing-library/user-event @testing-library/jest-dom @playwright/test serve
npx playwright install chromium
```

- [ ] **Step 4: 설정 파일 작성**

`Frontend/next.config.ts` (내용 전체 교체):

```ts
import type { NextConfig } from "next";

// 서버 기능 없이 정적 파일(out/)로 내보내 Netlify에 올린다 — 서버 역할은 FastAPI가 맡음
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
```

`Frontend/vitest.config.mts`:

```ts
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL(".", import.meta.url)) } },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", "e2e/**", ".next/**", "out/**"],
  },
});
```

`Frontend/vitest.setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());
```

`Frontend/playwright.config.ts`:

```ts
import { defineConfig, devices } from "@playwright/test";

// next build로 만든 out/을 정적 서버로 띄워 휴대폰 화면 크기로 검사한다. API는 테스트 안에서 가짜 응답으로 가로챔
export default defineConfig({
  testDir: "./e2e",
  use: { ...devices["Pixel 7"], baseURL: "http://localhost:3100" },
  webServer: {
    command: "npx serve out -l 3100",
    url: "http://localhost:3100",
    reuseExistingServer: !process.env.CI,
  },
});
```

`package.json`의 `scripts`를 다음으로 맞춘다(`dev`·`build`는 생성된 값 유지):

```json
"lint": "eslint .",
"typecheck": "tsc --noEmit",
"test": "vitest run",
"e2e": "next build && playwright test"
```

`eslint.config.mjs`의 내보내는 배열 끝에 규칙 객체를 추가한다(사진은 blob URL이라 `next/image` 최적화 대상이 아님):

```js
  {
    rules: { "@next/next/no-img-element": "off" },
  },
```

`Frontend/.gitignore` 끝에 추가:

```
# playwright
/test-results/
/playwright-report/
```

- [ ] **Step 5: 기본 화면·스타일 정리**

생성된 `app/page.module.css`와 `public/`의 예제 SVG를 지운다. `app/globals.css` 전체 교체:

```css
:root {
  --bg: #fafafa;
  --surface: #ffffff;
  --text: #111111;
  --text-muted: #6b6b6b;
  --border: #e5e5e5;
  --accent: #111111;
  --accent-text: #ffffff;
  --danger: #d92d20;
  --radius: 14px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --font: system-ui, -apple-system, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
  color-scheme: light dark;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0b0b0b;
    --surface: #161616;
    --text: #f2f2f2;
    --text-muted: #9a9a9a;
    --border: #262626;
    --accent: #f2f2f2;
    --accent-text: #0b0b0b;
    --danger: #ff6b5e;
  }
}

* {
  box-sizing: border-box;
  margin: 0;
}

html,
body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
}

body {
  min-height: 100dvh;
}

button {
  font: inherit;
  color: inherit;
  cursor: pointer;
}

button:disabled {
  cursor: default;
  opacity: 0.45;
}

img {
  display: block;
  max-width: 100%;
}

.app {
  max-width: 480px;
  margin: 0 auto;
  min-height: 100dvh;
  padding: 0 var(--space-4) 96px;
}
```

`app/layout.tsx` 전체 교체:

```tsx
import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GridFlow",
  description: "테마에 어울리는 사진을 골라 캐러셀 순서를 추천해요",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
```

`app/page.tsx` 전체 교체(Task 9에서 실제 앱으로 바꿈):

```tsx
export default function Page() {
  return (
    <main className="app">
      <h1>GridFlow</h1>
    </main>
  );
}
```

- [ ] **Step 6: `lib/` 무시 문제 수정**

Run: `cd .. && mkdir -p Frontend/lib && touch Frontend/lib/limits.ts && git check-ignore -v Frontend/lib/limits.ts`
Expected: `.gitignore:...:lib/` 출력(=무시되고 있음)

루트 `.gitignore`의 `lib/` 줄 바로 아래에 추가:

```
# 위 lib/는 Python 패키징 산출물용 — Frontend/lib(소스)는 무시하지 않는다
!Frontend/lib/
```

Run: `git check-ignore -v Frontend/lib/limits.ts; echo "exit=$?"`
Expected: 출력 없이 `exit=1`

- [ ] **Step 7: 실패하는 테스트 작성**

`Frontend/lib/limits.test.ts`:

```ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { MAX_PHOTOS } from "./limits";

describe("MAX_PHOTOS", () => {
  it("백엔드 Backend/main.py의 MAX_PHOTOS와 같다", () => {
    const source = readFileSync(fileURLToPath(new URL("../../Backend/main.py", import.meta.url)), "utf8");
    const match = source.match(/^MAX_PHOTOS = (\d+)/m);

    expect(match).not.toBeNull();
    expect(MAX_PHOTOS).toBe(Number(match![1]));
  });
});
```

Run: `cd Frontend && npm test`
Expected: FAIL (`MAX_PHOTOS`가 export되지 않음)

- [ ] **Step 8: 구현**

`Frontend/lib/limits.ts`:

```ts
/** 게시물 하나에 담을 수 있는 최대 사진 수(인스타그램 캐러셀 최대치). Backend/main.py의 MAX_PHOTOS와 같아야 한다 */
export const MAX_PHOTOS = 20;
```

- [ ] **Step 9: 전체 확인**

Run: `npm test && npm run typecheck && npm run lint && npm run build && ls out/index.html`
Expected: 테스트 1개 PASS, 타입·린트 에러 없음, `out/index.html` 존재

- [ ] **Step 10: 문서**

`Frontend/CLAUDE.md`:

```markdown
# Frontend/CLAUDE.md

`Frontend/`에서 작업할 때 적용되는 세부 지침이다. 공통 규칙은 루트 [`AGENTS.md`](../AGENTS.md), 설계는 `docs/superpowers/specs/2026-10-12-frontend-deploy-design.md` 참고.

## 구조

- Next.js(App Router, TypeScript), `output: "export"` 정적 내보내기 → `out/`을 Netlify가 배포
- 주소는 `/` 하나. `components/GridFlowApp.tsx`가 `lib/state.ts` 리듀서로 단계(home → theme → pick → analyzing → result)를 전환한다
- `lib/`: 로직(순수 함수·API·리듀서). `components/`: 그리기 전용 — 서버 호출·상태 변경 로직을 넣지 않는다
- 스타일: 컴포넌트별 `*.module.css` + `app/globals.css`의 CSS 변수. Tailwind·CSS-in-JS 쓰지 않음

## 개발 환경

- Node 22(`.nvmrc`), 의존성은 정확한 버전 고정(`.npmrc`의 `save-exact=true`)
- 개발 서버: `npm run dev`(http://localhost:3000). 백엔드는 `uvicorn main:app --reload --app-dir Backend`(기본 CORS가 localhost:3000 허용)
- API 주소: 빌드 시 `NEXT_PUBLIC_API_BASE_URL`(없으면 `http://localhost:8000`)

## 테스트

- `npm test`(Vitest + Testing Library), `npm run typecheck`, `npm run lint`
- `npm run e2e`: 빌드 후 Playwright(Pixel 7 화면, API는 가짜 응답)
- 백엔드와 맞춰야 하는 값은 테스트가 원본 파일을 읽어 비교한다: `MAX_PHOTOS`(`Backend/main.py`), 테마 문장(`Ai/collect_unsplash_data.py`의 `THEMES`)
```

`AGENTS.md`의 `## Frontend 파트` 절 본문을 다음으로 교체:

```markdown
- 구조·개발 환경·테스트 명령어 등 세부 지침은 [`Frontend/CLAUDE.md`](Frontend/CLAUDE.md)에 있다
- 요약: Next.js(App Router, TypeScript) 정적 내보내기, CSS Modules, 한 페이지 안에서 단계 전환, 로그인·저장 없음, Vitest + Playwright
```

`AGENTS.md` `## 프로젝트 구조`의 Frontend 줄을 `` - `Frontend/` — Next.js 앱. 세부는 [Frontend 파트](#frontend-파트), [`Frontend/CLAUDE.md`](Frontend/CLAUDE.md) 참고``로 교체.

- [ ] **Step 11: 커밋 (승인 후)**

```bash
cd ..
git add .gitignore AGENTS.md Frontend
git status --short Frontend | grep -c node_modules  # 0이어야 함
git commit -m "chore(frontend): Next.js 정적 내보내기 앱 초기 구성 + 테스트 도구 설정 (#22)"
```

---

### Task 4: 테마 · 리사이즈 (`lib/themes`, `lib/resize`)

**Files:**
- Create: `Frontend/lib/themes.ts`, `Frontend/lib/themes.test.ts`, `Frontend/lib/resize.ts`, `Frontend/lib/resize.test.ts`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `type ThemeId = "mono" | "vivid" | "golden"`, `interface Theme { id: ThemeId; label: string; description: string; prompt: string; swatch: readonly [string, string, string] }`, `THEMES: readonly Theme[]`, `getTheme(id: ThemeId): Theme`
  - `RESIZE_LONG_SIDE = 512`, `JPEG_QUALITY = 0.85`, `fitWithin(width: number, height: number, maxSide: number): { width: number; height: number }`, `resizeImage(file: Blob): Promise<Blob>`

- [ ] **Step 1: 실패하는 테스트 작성**

`Frontend/lib/themes.test.ts`:

```ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { getTheme, THEMES } from "./themes";

function trainedThemePrompts(): string[] {
  const source = readFileSync(fileURLToPath(new URL("../../Ai/collect_unsplash_data.py", import.meta.url)), "utf8");
  const block = source.match(/^THEMES = \[([\s\S]*?)\]/m);
  if (!block) throw new Error("Ai/collect_unsplash_data.py에서 THEMES를 찾지 못함");
  return [...block[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
}

describe("THEMES", () => {
  it("영어 문장이 ScoringMLP 학습 테마와 글자 하나까지 같다", () => {
    expect(THEMES.map((t) => t.prompt).sort()).toEqual(trainedThemePrompts().sort());
  });

  it("한글 이름 3개를 가진다", () => {
    expect(THEMES.map((t) => t.label)).toEqual(["흑백", "비비드", "골든아워"]);
  });

  it("getTheme으로 id에 맞는 테마를 찾는다", () => {
    expect(getTheme("golden").prompt).toBe("warm golden hour sunset photography");
  });
});
```

`Frontend/lib/resize.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { fitWithin, RESIZE_LONG_SIDE } from "./resize";

describe("fitWithin", () => {
  it("가로가 긴 사진은 가로를 512로 맞추고 비율을 유지한다", () => {
    expect(fitWithin(4032, 3024, RESIZE_LONG_SIDE)).toEqual({ width: 512, height: 384 });
  });

  it("세로가 긴 사진은 세로를 512로 맞춘다", () => {
    expect(fitWithin(3024, 4032, RESIZE_LONG_SIDE)).toEqual({ width: 384, height: 512 });
  });

  it("이미 작은 사진은 키우지 않는다", () => {
    expect(fitWithin(300, 200, RESIZE_LONG_SIDE)).toEqual({ width: 300, height: 200 });
  });

  it("아주 가는 사진도 최소 1px은 남긴다", () => {
    expect(fitWithin(10000, 5, RESIZE_LONG_SIDE)).toEqual({ width: 512, height: 1 });
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd Frontend && npm test`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 구현**

`Frontend/lib/themes.ts`:

```ts
export type ThemeId = "mono" | "vivid" | "golden";

export interface Theme {
  id: ThemeId;
  label: string;
  description: string;
  /** 서버에 보내는 영어 문장 — ScoringMLP 학습 테마(Ai/collect_unsplash_data.py의 THEMES)와 정확히 같아야 함 */
  prompt: string;
  /** 테마 카드에 보여줄 예시 색 3개 */
  swatch: readonly [string, string, string];
}

export const THEMES: readonly Theme[] = [
  {
    id: "mono",
    label: "흑백",
    description: "색을 덜어내고 빛과 그림자로",
    prompt: "black and white monochrome photography",
    swatch: ["#111111", "#7a7a7a", "#e6e6e6"],
  },
  {
    id: "vivid",
    label: "비비드",
    description: "선명하고 다채로운 색감",
    prompt: "vibrant colorful photography",
    swatch: ["#ff3b6b", "#ffc93c", "#2ec4b6"],
  },
  {
    id: "golden",
    label: "골든아워",
    description: "해 질 녘의 따뜻한 빛",
    prompt: "warm golden hour sunset photography",
    swatch: ["#ff8a3d", "#f6c26b", "#7a3e2b"],
  },
];

export function getTheme(id: ThemeId): Theme {
  const theme = THEMES.find((t) => t.id === id);
  if (!theme) throw new Error(`알 수 없는 테마: ${id}`);
  return theme;
}
```

`Frontend/lib/resize.ts`:

```ts
/** CLIP은 어차피 224px로 줄여서 보고, 512px에서도 점수·제거 판정이 원본과 같았다(이슈 #22 실측) */
export const RESIZE_LONG_SIDE = 512;
export const JPEG_QUALITY = 0.85;

export function fitWithin(width: number, height: number, maxSide: number): { width: number; height: number } {
  const longSide = Math.max(width, height);
  if (longSide <= maxSide) return { width, height };
  const scale = maxSide / longSide;
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
}

/** 휴대폰 사진을 긴 변 512px JPEG로 줄인다. EXIF 회전 정보를 반영해 세로 사진이 눕지 않게 한다 */
export async function resizeImage(file: Blob): Promise<Blob> {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  try {
    const { width, height } = fitWithin(bitmap.width, bitmap.height, RESIZE_LONG_SIDE);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("canvas 2d 컨텍스트를 만들 수 없음");
    context.drawImage(bitmap, 0, 0, width, height);
    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("JPEG 변환 실패"))), "image/jpeg", JPEG_QUALITY);
    });
  } finally {
    bitmap.close();
  }
}
```

`resizeImage`는 jsdom에 canvas·이미지 디코딩이 없어 단위 테스트하지 않고, Task 9 E2E(실제 Chromium)에서 "썸네일 긴 변 ≤ 512px"로 확인한다.

- [ ] **Step 4: 통과 확인**

Run: `npm test && npm run typecheck && npm run lint`
Expected: 전부 PASS

- [ ] **Step 5: 커밋 (승인 후)**

```bash
git add Frontend/lib/themes.ts Frontend/lib/themes.test.ts Frontend/lib/resize.ts Frontend/lib/resize.test.ts
git commit -m "feat(frontend): 테마 프리셋 3개 + 512px 리사이즈 로직 (#22)"
```

---

### Task 5: API 클라이언트 (`lib/api`)

**Files:**
- Create: `Frontend/lib/api.ts`, `Frontend/lib/api.test.ts`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `type ApiErrorKind = "network" | "timeout" | "bad_request" | "server"`
  - `class ArrangeError extends Error { readonly kind: ApiErrorKind }`
  - `interface UploadPhoto { id: string; blob: Blob }`
  - `interface ArrangeResult { order: string[]; removed: { id: string; score: number }[]; skipped: { id: string; reason: string }[] }`
  - `API_BASE_URL: string`, `REQUEST_TIMEOUT_MS = 65_000`
  - `arrange(themePrompt: string, photos: UploadPhoto[], options?: { signal?: AbortSignal; timeoutMs?: number; fetchImpl?: typeof fetch; baseUrl?: string }): Promise<ArrangeResult>` — 바깥 `signal`로 취소하면 `ArrangeError`가 아닌 원래 AbortError를 그대로 던진다

- [ ] **Step 1: 실패하는 테스트 작성**

`Frontend/lib/api.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { arrange, ArrangeError, type UploadPhoto } from "./api";

const photos: UploadPhoto[] = [
  { id: "0.jpg", blob: new Blob(["a"], { type: "image/jpeg" }) },
  { id: "1.jpg", blob: new Blob(["b"], { type: "image/jpeg" }) },
];

const okBody = {
  removed_candidates: [{ photo_id: "1.jpg", score: 0.21 }],
  skipped: [{ photo_id: "2.jpg", reason: "용량 초과(5MB 제한)" }],
  groups: [{ order: ["0.jpg"], adjacency_costs: [] }],
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("arrange", () => {
  it("테마·사진·group_ids(전부 0)를 멀티파트로 보낸다", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, okBody));

    await arrange("vibrant colorful photography", photos, { fetchImpl, baseUrl: "https://api.test" });

    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("https://api.test/arrange");
    expect(init.method).toBe("POST");
    const form = init.body as FormData;
    expect(form.get("theme")).toBe("vibrant colorful photography");
    expect(form.getAll("group_ids")).toEqual(["0", "0"]);
    expect(form.getAll("photos").map((file) => (file as File).name)).toEqual(["0.jpg", "1.jpg"]);
  });

  it("정상 응답을 순서·제거 후보·건너뛴 사진으로 바꾼다", async () => {
    const result = await arrange("t", photos, { fetchImpl: async () => jsonResponse(200, okBody) });

    expect(result).toEqual({
      order: ["0.jpg"],
      removed: [{ id: "1.jpg", score: 0.21 }],
      skipped: [{ id: "2.jpg", reason: "용량 초과(5MB 제한)" }],
    });
  });

  it("그룹이 비어 있으면(전부 제거 후보) 순서는 빈 배열", async () => {
    const body = { ...okBody, groups: [] };
    const result = await arrange("t", photos, { fetchImpl: async () => jsonResponse(200, body) });

    expect(result.order).toEqual([]);
  });

  it("연결 실패는 network", async () => {
    const fetchImpl = async () => {
      throw new TypeError("Failed to fetch");
    };

    await expect(arrange("t", photos, { fetchImpl })).rejects.toMatchObject({ kind: "network" });
  });

  it("제한 시간을 넘기면 timeout", async () => {
    const hang: typeof fetch = (_url, init) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      });

    await expect(arrange("t", photos, { fetchImpl: hang, timeoutMs: 10 })).rejects.toMatchObject({ kind: "timeout" });
  });

  it("504는 timeout", async () => {
    await expect(arrange("t", photos, { fetchImpl: async () => new Response("", { status: 504 }) })).rejects.toMatchObject({
      kind: "timeout",
    });
  });

  it("400은 bad_request이고 서버의 detail 문구를 메시지로 쓴다", async () => {
    const fetchImpl = async () => jsonResponse(400, { detail: "사진은 최대 20장까지 보낼 수 있음" });

    await expect(arrange("t", photos, { fetchImpl })).rejects.toMatchObject({
      kind: "bad_request",
      message: "사진은 최대 20장까지 보낼 수 있음",
    });
  });

  it("500은 server", async () => {
    await expect(arrange("t", photos, { fetchImpl: async () => new Response("", { status: 500 }) })).rejects.toBeInstanceOf(
      ArrangeError,
    );
    await expect(arrange("t", photos, { fetchImpl: async () => new Response("", { status: 500 }) })).rejects.toMatchObject({
      kind: "server",
    });
  });

  it("바깥에서 취소하면 ArrangeError가 아니라 AbortError를 그대로 던진다", async () => {
    const controller = new AbortController();
    const hang: typeof fetch = (_url, init) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      });

    const pending = arrange("t", photos, { fetchImpl: hang, signal: controller.signal });
    controller.abort();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd Frontend && npm test -- lib/api.test.ts`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 구현**

`Frontend/lib/api.ts`:

```ts
export type ApiErrorKind = "network" | "timeout" | "bad_request" | "server";

export class ArrangeError extends Error {
  readonly kind: ApiErrorKind;

  constructor(kind: ApiErrorKind, message: string) {
    super(message);
    this.name = "ArrangeError";
    this.kind = kind;
  }
}

export interface UploadPhoto {
  /** 서버가 사진을 구분하는 이름(0.jpg, 1.jpg, …) — 응답의 photo_id로 그대로 돌아온다 */
  id: string;
  blob: Blob;
}

export interface ArrangeResult {
  order: string[];
  removed: { id: string; score: number }[];
  skipped: { id: string; reason: string }[];
}

interface ArrangeResponseBody {
  removed_candidates: { photo_id: string; score: number }[];
  skipped: { photo_id: string; reason: string }[];
  groups: { order: string[]; adjacency_costs: [string, string, number][] }[];
}

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
/** CloudFront 오리진 대기(60초)보다 살짝 길게 — 서버 쪽 504를 먼저 받을 수 있게 */
export const REQUEST_TIMEOUT_MS = 65_000;

export interface ArrangeOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
  baseUrl?: string;
}

export async function arrange(themePrompt: string, photos: UploadPhoto[], options: ArrangeOptions = {}): Promise<ArrangeResult> {
  const { signal, timeoutMs = REQUEST_TIMEOUT_MS, fetchImpl = fetch, baseUrl = API_BASE_URL } = options;

  const form = new FormData();
  form.append("theme", themePrompt);
  for (const photo of photos) {
    form.append("photos", photo.blob, photo.id);
    form.append("group_ids", "0"); // 요청 1번 = 게시물 1개
  }

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const forwardAbort = () => controller.abort();
  signal?.addEventListener("abort", forwardAbort);

  let response: Response;
  try {
    response = await fetchImpl(`${baseUrl}/arrange`, { method: "POST", body: form, signal: controller.signal });
  } catch (error) {
    if (timedOut) throw new ArrangeError("timeout", "요청 시간이 초과됨");
    if (signal?.aborted) throw error;
    // 브라우저는 CORS 거절도 일반 연결 실패와 똑같이 알려줘서 둘을 구분할 수 없다
    throw new ArrangeError("network", "서버에 연결하지 못함");
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", forwardAbort);
  }

  if (response.ok) return toResult((await response.json()) as ArrangeResponseBody);
  if (response.status === 504) throw new ArrangeError("timeout", "게이트웨이 시간 초과");
  if (response.status >= 400 && response.status < 500) throw new ArrangeError("bad_request", await readDetail(response));
  throw new ArrangeError("server", `서버 오류 (${response.status})`);
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && typeof (body as { detail?: unknown }).detail === "string") {
      return (body as { detail: string }).detail;
    }
  } catch {
    // 본문이 JSON이 아니면 아래 기본 문구를 쓴다
  }
  return `요청이 거절됨 (${response.status})`;
}

function toResult(body: ArrangeResponseBody): ArrangeResult {
  return {
    order: body.groups[0]?.order ?? [],
    removed: body.removed_candidates.map((c) => ({ id: c.photo_id, score: c.score })),
    skipped: body.skipped.map((s) => ({ id: s.photo_id, reason: s.reason })),
  };
}
```

- [ ] **Step 4: 통과 확인**

Run: `npm test && npm run typecheck && npm run lint`
Expected: 전부 PASS

- [ ] **Step 5: 커밋 (승인 후)**

```bash
git add Frontend/lib/api.ts Frontend/lib/api.test.ts
git commit -m "feat(frontend): /arrange 요청 클라이언트 + 에러 4종 분류 (#22)"
```

---

### Task 6: 앱 상태 리듀서 (`lib/state`)

**Files:**
- Create: `Frontend/lib/state.ts`, `Frontend/lib/state.test.ts`

**Interfaces:**
- Consumes: `ArrangeError`, `ArrangeResult` (Task 5), `MAX_PHOTOS` (Task 3), `ThemeId` (Task 4)
- Produces:
  - `type Step = "home" | "theme" | "pick" | "analyzing" | "result"`
  - `interface DraftPhoto { id: string; blob: Blob; url: string }`
  - `interface Post { id: string; themeId: ThemeId; photos: DraftPhoto[] }` (`photos`는 추천 순서, 1장 이상)
  - `interface AppState { step; posts; themeId: ThemeId | null; draft: DraftPhoto[]; nextPhotoSeq: number; nextPostSeq: number; result: ArrangeResult | null; error: ArrangeError | null; openPostId: string | null }`
  - `type Action` (아래 코드), `initialState`, `reducer(state, action): AppState`
  - `PREVIOUS_STEP: Record<Step, Step>`
  - `interface ResultView { ordered: DraftPhoto[]; removed: { photo: DraftPhoto; score: number }[]; skipped: { id: string; reason: string; photo: DraftPhoto | null }[] }`, `selectResultView(state): ResultView`
  - `urlsReleasedByAddPost(state): string[]` — `ADD_POST` 뒤 그리드에 남지 않는 초안 사진의 objectURL

- [ ] **Step 1: 실패하는 테스트 작성**

`Frontend/lib/state.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { ArrangeError, type ArrangeResult } from "./api";
import { MAX_PHOTOS } from "./limits";
import { initialState, reducer, selectResultView, urlsReleasedByAddPost, type Action, type AppState } from "./state";

function photos(count: number) {
  return Array.from({ length: count }, (_, i) => ({ blob: new Blob([String(i)]), url: `blob:${i}` }));
}

function run(actions: Action[], from: AppState = initialState): AppState {
  return actions.reduce(reducer, from);
}

const result: ArrangeResult = {
  order: ["2.jpg", "0.jpg"],
  removed: [{ id: "1.jpg", score: 0.2 }],
  skipped: [],
};

function stateAtResult(): AppState {
  return run([
    { type: "START_NEW" },
    { type: "SELECT_THEME", themeId: "golden" },
    { type: "ADD_PHOTOS", photos: photos(3) },
    { type: "ANALYZE_START" },
    { type: "ANALYZE_SUCCESS", result },
  ]);
}

describe("reducer", () => {
  it("새 게시물 → 테마 → 사진 고르기 순서로 단계가 바뀐다", () => {
    const state = run([{ type: "START_NEW" }, { type: "SELECT_THEME", themeId: "mono" }]);

    expect(state.step).toBe("pick");
    expect(state.themeId).toBe("mono");
  });

  it("사진 id는 0.jpg부터 증가하고, 빼고 다시 넣어도 겹치지 않는다", () => {
    const state = run([
      { type: "ADD_PHOTOS", photos: photos(2) },
      { type: "REMOVE_PHOTO", id: "1.jpg" },
      { type: "ADD_PHOTOS", photos: photos(1) },
    ]);

    expect(state.draft.map((p) => p.id)).toEqual(["0.jpg", "2.jpg"]);
  });

  it("여러 번 나눠 골라도 최대 장수를 넘기지 않는다", () => {
    const state = run([
      { type: "ADD_PHOTOS", photos: photos(15) },
      { type: "ADD_PHOTOS", photos: photos(10) },
    ]);

    expect(state.draft).toHaveLength(MAX_PHOTOS);
  });

  it("사진이 없으면 분석을 시작하지 않는다", () => {
    const state = run([{ type: "START_NEW" }, { type: "SELECT_THEME", themeId: "mono" }, { type: "ANALYZE_START" }]);

    expect(state.step).toBe("pick");
  });

  it("분석 성공 시 결과 단계로 간다", () => {
    expect(stateAtResult().step).toBe("result");
  });

  it("분석 실패 시 analyzing에 머물며 에러를 담는다", () => {
    const state = run([
      { type: "ADD_PHOTOS", photos: photos(1) },
      { type: "ANALYZE_START" },
      { type: "ANALYZE_FAILURE", error: new ArrangeError("server", "x") },
    ]);

    expect(state.step).toBe("analyzing");
    expect(state.error?.kind).toBe("server");
  });

  it("뒤로가기로 analyzing을 떠난 뒤 늦게 온 응답은 무시한다", () => {
    const state = run([
      { type: "ADD_PHOTOS", photos: photos(1) },
      { type: "ANALYZE_START" },
      { type: "NAVIGATE", step: "pick" },
      { type: "ANALYZE_SUCCESS", result },
      { type: "ANALYZE_FAILURE", error: new ArrangeError("server", "x") },
    ]);

    expect(state.step).toBe("pick");
    expect(state.result).toBeNull();
    expect(state.error).toBeNull();
  });

  it("그리드에 추가하면 추천 순서대로 맨 앞에 쌓이고 홈으로 간다", () => {
    const first = run([{ type: "ADD_POST" }], stateAtResult());
    const second = run(
      [
        { type: "START_NEW" },
        { type: "SELECT_THEME", themeId: "vivid" },
        { type: "ADD_PHOTOS", photos: photos(1) },
        { type: "ANALYZE_START" },
        { type: "ANALYZE_SUCCESS", result: { order: ["3.jpg"], removed: [], skipped: [] } },
        { type: "ADD_POST" },
      ],
      first,
    );

    expect(first.step).toBe("home");
    expect(first.posts[0].photos.map((p) => p.id)).toEqual(["2.jpg", "0.jpg"]);
    expect(second.posts.map((p) => p.themeId)).toEqual(["vivid", "golden"]);
    expect(second.draft).toEqual([]);
  });

  it("추천 순서가 비어 있으면(전부 제거 후보) 그리드에 추가하지 않는다", () => {
    const empty = run([
      { type: "ADD_PHOTOS", photos: photos(1) },
      { type: "SELECT_THEME", themeId: "mono" },
      { type: "ANALYZE_START" },
      { type: "ANALYZE_SUCCESS", result: { order: [], removed: [{ id: "0.jpg", score: 0.1 }], skipped: [] } },
      { type: "ADD_POST" },
    ]);

    expect(empty.posts).toEqual([]);
    expect(empty.step).toBe("result");
  });

  it("게시물을 삭제하면 그리드에서 빠지고 시트가 닫힌다", () => {
    const added = run([{ type: "ADD_POST" }], stateAtResult());
    const postId = added.posts[0].id;
    const state = run([{ type: "OPEN_POST", postId }, { type: "DELETE_POST", postId }], added);

    expect(state.posts).toEqual([]);
    expect(state.openPostId).toBeNull();
  });
});

describe("selectResultView", () => {
  it("응답 id를 초안 사진으로 바꾸고, 모르는 id는 걸러낸다", () => {
    const state = run(
      [
        {
          type: "ANALYZE_SUCCESS",
          result: {
            order: ["2.jpg", "99.jpg", "0.jpg"],
            removed: [{ id: "1.jpg", score: 0.2 }, { id: "77.jpg", score: 0.1 }],
            skipped: [{ id: "88.jpg", reason: "용량 초과(5MB 제한)" }],
          },
        },
      ],
      { ...run([{ type: "ADD_PHOTOS", photos: photos(3) }]), step: "analyzing" },
    );

    const view = selectResultView(state);

    expect(view.ordered.map((p) => p.id)).toEqual(["2.jpg", "0.jpg"]);
    expect(view.removed.map((r) => r.photo.id)).toEqual(["1.jpg"]);
    expect(view.skipped).toEqual([{ id: "88.jpg", reason: "용량 초과(5MB 제한)", photo: null }]);
  });
});

describe("urlsReleasedByAddPost", () => {
  it("그리드에 남지 않는 사진(제거 후보)의 URL만 돌려준다", () => {
    expect(urlsReleasedByAddPost(stateAtResult())).toEqual(["blob:1"]);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd Frontend && npm test -- lib/state.test.ts`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 구현**

`Frontend/lib/state.ts`:

```ts
import type { ArrangeError, ArrangeResult } from "./api";
import { MAX_PHOTOS } from "./limits";
import type { ThemeId } from "./themes";

export type Step = "home" | "theme" | "pick" | "analyzing" | "result";

export interface DraftPhoto {
  /** 서버에 보내는 이름(0.jpg, 1.jpg, …) */
  id: string;
  /** 512px로 줄인 JPEG */
  blob: Blob;
  /** 썸네일용 objectURL — 쓰지 않게 되면 호출 측에서 URL.revokeObjectURL */
  url: string;
}

export interface Post {
  id: string;
  themeId: ThemeId;
  /** 추천 캐러셀 순서, 1장 이상 */
  photos: DraftPhoto[];
}

export interface AppState {
  step: Step;
  /** 최신이 앞 — 그대로 그리면 그리드 왼쪽 위가 최신 */
  posts: Post[];
  themeId: ThemeId | null;
  draft: DraftPhoto[];
  nextPhotoSeq: number;
  nextPostSeq: number;
  result: ArrangeResult | null;
  error: ArrangeError | null;
  openPostId: string | null;
}

export const initialState: AppState = {
  step: "home",
  posts: [],
  themeId: null,
  draft: [],
  nextPhotoSeq: 0,
  nextPostSeq: 0,
  result: null,
  error: null,
  openPostId: null,
};

export type Action =
  | { type: "START_NEW" }
  | { type: "SELECT_THEME"; themeId: ThemeId }
  | { type: "ADD_PHOTOS"; photos: { blob: Blob; url: string }[] }
  | { type: "REMOVE_PHOTO"; id: string }
  | { type: "ANALYZE_START" }
  | { type: "ANALYZE_SUCCESS"; result: ArrangeResult }
  | { type: "ANALYZE_FAILURE"; error: ArrangeError }
  | { type: "ADD_POST" }
  | { type: "DELETE_POST"; postId: string }
  | { type: "OPEN_POST"; postId: string }
  | { type: "CLOSE_POST" }
  | { type: "NAVIGATE"; step: Step };

/** 휴대폰 뒤로가기·화면의 ← 버튼이 가는 곳 */
export const PREVIOUS_STEP: Record<Step, Step> = {
  home: "home",
  theme: "home",
  pick: "theme",
  analyzing: "pick",
  result: "pick",
};

export function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "START_NEW":
      return { ...state, step: "theme", themeId: null, draft: [], result: null, error: null };
    case "SELECT_THEME":
      return { ...state, step: "pick", themeId: action.themeId };
    case "ADD_PHOTOS": {
      const room = Math.max(MAX_PHOTOS - state.draft.length, 0);
      const accepted = action.photos.slice(0, room).map((photo, i) => ({ ...photo, id: `${state.nextPhotoSeq + i}.jpg` }));
      return { ...state, draft: [...state.draft, ...accepted], nextPhotoSeq: state.nextPhotoSeq + accepted.length };
    }
    case "REMOVE_PHOTO":
      return { ...state, draft: state.draft.filter((p) => p.id !== action.id) };
    case "ANALYZE_START":
      if (state.draft.length === 0) return state;
      return { ...state, step: "analyzing", result: null, error: null };
    case "ANALYZE_SUCCESS":
      if (state.step !== "analyzing") return state; // 취소된 요청의 늦은 응답
      return { ...state, step: "result", result: action.result };
    case "ANALYZE_FAILURE":
      if (state.step !== "analyzing") return state;
      return { ...state, error: action.error };
    case "ADD_POST": {
      if (state.step !== "result" || !state.themeId) return state;
      const { ordered } = selectResultView(state);
      if (ordered.length === 0) return state;
      const post: Post = { id: `post-${state.nextPostSeq}`, themeId: state.themeId, photos: ordered };
      return {
        ...state,
        step: "home",
        posts: [post, ...state.posts],
        nextPostSeq: state.nextPostSeq + 1,
        themeId: null,
        draft: [],
        result: null,
      };
    }
    case "DELETE_POST":
      return { ...state, posts: state.posts.filter((p) => p.id !== action.postId), openPostId: null };
    case "OPEN_POST":
      return { ...state, openPostId: action.postId };
    case "CLOSE_POST":
      return { ...state, openPostId: null };
    case "NAVIGATE":
      return { ...state, step: action.step, error: null };
  }
}

export interface ResultView {
  ordered: DraftPhoto[];
  removed: { photo: DraftPhoto; score: number }[];
  skipped: { id: string; reason: string; photo: DraftPhoto | null }[];
}

/** 서버 응답의 id를 초안 사진으로 바꾼다. 서버가 모르는 id를 돌려줘도 화면이 깨지지 않게 걸러낸다 */
export function selectResultView(state: Pick<AppState, "draft" | "result">): ResultView {
  if (!state.result) return { ordered: [], removed: [], skipped: [] };
  const byId = new Map(state.draft.map((p) => [p.id, p]));
  return {
    ordered: state.result.order.flatMap((id) => {
      const photo = byId.get(id);
      return photo ? [photo] : [];
    }),
    removed: state.result.removed.flatMap(({ id, score }) => {
      const photo = byId.get(id);
      return photo ? [{ photo, score }] : [];
    }),
    skipped: state.result.skipped.map(({ id, reason }) => ({ id, reason, photo: byId.get(id) ?? null })),
  };
}

export function urlsReleasedByAddPost(state: AppState): string[] {
  const kept = new Set(selectResultView(state).ordered.map((p) => p.id));
  return state.draft.filter((p) => !kept.has(p.id)).map((p) => p.url);
}
```

- [ ] **Step 4: 통과 확인**

Run: `npm test && npm run typecheck && npm run lint`
Expected: 전부 PASS

- [ ] **Step 5: 커밋 (승인 후)**

```bash
git add Frontend/lib/state.ts Frontend/lib/state.test.ts
git commit -m "feat(frontend): 단계·초안·게시물 상태 리듀서 (#22)"
```

---

### Task 7: 홈 화면 조각 (`FeedGrid`, `PostSheet`, `IntroModal`, 공용 `CarouselStrip`)

**Files:**
- Create: `Frontend/lib/introSeen.ts`, `Frontend/lib/introSeen.test.ts`
- Create: `Frontend/components/CarouselStrip.tsx` + `.module.css`, `FeedGrid.tsx` + `.module.css`, `PostSheet.tsx` + `.module.css`, `IntroModal.tsx` + `.module.css`
- Test: `Frontend/components/home.test.tsx`

**Interfaces:**
- Consumes: `Post`, `DraftPhoto` (Task 6), `getTheme` (Task 4)
- Produces:
  - `hasSeenIntro(): boolean`, `markIntroSeen(): void`, `subscribeIntroSeen(listener: () => void): () => void`
  - `CarouselStrip({ photos: DraftPhoto[]; label: string })` — `<ol aria-label={label}>`, 각 `<img data-photo-id>`
  - `FeedGrid({ posts: Post[]; onOpenPost(postId: string): void; onNewPost(): void; onShowIntro(): void })`
  - `PostSheet({ post: Post; onClose(): void; onDelete(postId: string): void })`
  - `IntroModal({ onClose(): void })`

- [ ] **Step 1: 실패하는 테스트 작성**

`Frontend/lib/introSeen.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.restoreAllMocks();
  vi.resetModules();
  window.localStorage.clear();
});

describe("introSeen", () => {
  it("처음엔 안 본 상태이고, 표시하면 localStorage에 남는다", async () => {
    const { hasSeenIntro, markIntroSeen } = await import("./introSeen");

    expect(hasSeenIntro()).toBe(false);
    markIntroSeen();
    expect(hasSeenIntro()).toBe(true);
    expect(window.localStorage.getItem("gridflow:intro-seen")).toBe("1");
  });

  it("localStorage가 막혀 있어도 이번 방문 동안은 본 것으로 기억한다", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const { hasSeenIntro, markIntroSeen } = await import("./introSeen");

    expect(hasSeenIntro()).toBe(false);
    markIntroSeen();
    expect(hasSeenIntro()).toBe(true);
  });

  it("표시하면 구독자에게 알린다", async () => {
    const { markIntroSeen, subscribeIntroSeen } = await import("./introSeen");
    const listener = vi.fn();
    subscribeIntroSeen(listener);

    markIntroSeen();

    expect(listener).toHaveBeenCalledTimes(1);
  });
});
```

`Frontend/components/home.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Post } from "@/lib/state";
import { FeedGrid } from "./FeedGrid";
import { IntroModal } from "./IntroModal";
import { PostSheet } from "./PostSheet";

function post(id: string, count: number): Post {
  return {
    id,
    themeId: "golden",
    photos: Array.from({ length: count }, (_, i) => ({ id: `${i}.jpg`, blob: new Blob(), url: `blob:${id}-${i}` })),
  };
}

describe("FeedGrid", () => {
  it("게시물이 없으면 빈 상태 안내를 보여준다", () => {
    render(<FeedGrid posts={[]} onOpenPost={vi.fn()} onNewPost={vi.fn()} onShowIntro={vi.fn()} />);

    expect(screen.getByText("아직 게시물이 없어요")).toBeInTheDocument();
  });

  it("게시물마다 칸 하나, 대표 사진은 첫 번째 사진, 2장 이상이면 캐러셀 표시", async () => {
    const onOpenPost = vi.fn();
    const { container } = render(
      <FeedGrid posts={[post("post-1", 3), post("post-0", 1)]} onOpenPost={onOpenPost} onNewPost={vi.fn()} onShowIntro={vi.fn()} />,
    );

    const tiles = screen.getAllByRole("button", { name: /게시물 열기/ });
    expect(tiles).toHaveLength(2);
    expect(tiles[0].querySelector("img")).toHaveAttribute("src", "blob:post-1-0");
    expect(container.querySelectorAll("[data-carousel]")).toHaveLength(1);

    await userEvent.click(tiles[0]);
    expect(onOpenPost).toHaveBeenCalledWith("post-1");
  });
});

describe("PostSheet", () => {
  it("삭제는 한 번 더 확인한 뒤에만 실행한다", async () => {
    const onDelete = vi.fn();
    render(<PostSheet post={post("post-0", 2)} onClose={vi.fn()} onDelete={onDelete} />);

    await userEvent.click(screen.getByRole("button", { name: "삭제" }));
    expect(onDelete).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "삭제할게요" }));
    expect(onDelete).toHaveBeenCalledWith("post-0");
  });

  it("캐러셀 순서를 번호와 함께 보여준다", () => {
    render(<PostSheet post={post("post-0", 2)} onClose={vi.fn()} onDelete={vi.fn()} />);

    const order = screen.getByRole("list", { name: "캐러셀 순서" });
    expect([...order.querySelectorAll("img")].map((img) => img.getAttribute("data-photo-id"))).toEqual(["0.jpg", "1.jpg"]);
  });
});

describe("IntroModal", () => {
  it("슬라이드 3장을 넘긴 뒤 시작하기로 닫는다", async () => {
    const onClose = vi.fn();
    render(<IntroModal onClose={onClose} />);

    expect(screen.getByRole("heading", { name: "사진을 고르면" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "다음" }));
    await userEvent.click(screen.getByRole("button", { name: "다음" }));
    await userEvent.click(screen.getByRole("button", { name: "시작하기" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("건너뛰기로 바로 닫을 수 있다", async () => {
    const onClose = vi.fn();
    render(<IntroModal onClose={onClose} />);

    await userEvent.click(screen.getByRole("button", { name: "건너뛰기" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd Frontend && npm test`
Expected: 새 테스트 FAIL (모듈 없음)

- [ ] **Step 3: 구현 — `lib/introSeen.ts`**

```ts
const KEY = "gridflow:intro-seen";
const listeners = new Set<() => void>();
/** localStorage가 막힌 환경(사파리 시크릿 모드 등)에서도 이번 방문 동안은 다시 띄우지 않기 위한 메모리 기억 */
let seenThisVisit = false;

export function hasSeenIntro(): boolean {
  if (seenThisVisit) return true;
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function markIntroSeen(): void {
  seenThisVisit = true;
  try {
    window.localStorage.setItem(KEY, "1");
  } catch {
    // 저장이 막혀 있으면 다음 방문 때 한 번 더 보여주면 된다
  }
  listeners.forEach((listener) => listener());
}

export function subscribeIntroSeen(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
```

- [ ] **Step 4: 구현 — 컴포넌트**

`Frontend/components/CarouselStrip.tsx`:

```tsx
import type { DraftPhoto } from "@/lib/state";
import styles from "./CarouselStrip.module.css";

export function CarouselStrip({ photos, label }: { photos: DraftPhoto[]; label: string }) {
  return (
    <ol className={styles.strip} aria-label={label}>
      {photos.map((photo, i) => (
        <li key={photo.id} className={styles.item}>
          <span className={styles.index}>{i + 1}</span>
          <img src={photo.url} alt={`${i + 1}번째 사진`} data-photo-id={photo.id} />
        </li>
      ))}
    </ol>
  );
}
```

`Frontend/components/CarouselStrip.module.css`:

```css
.strip {
  list-style: none;
  padding: 0;
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  padding-bottom: var(--space-2);
}

.item {
  position: relative;
  flex: 0 0 62%;
  scroll-snap-align: start;
}

.item img {
  width: 100%;
  aspect-ratio: 4 / 5;
  object-fit: cover;
  border-radius: var(--radius);
}

.index {
  position: absolute;
  top: var(--space-2);
  left: var(--space-2);
  min-width: 26px;
  height: 26px;
  padding: 0 var(--space-2);
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.65);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}
```

`Frontend/components/FeedGrid.tsx`:

```tsx
import type { Post } from "@/lib/state";
import styles from "./FeedGrid.module.css";

interface Props {
  posts: Post[];
  onOpenPost: (postId: string) => void;
  onNewPost: () => void;
  onShowIntro: () => void;
}

export function FeedGrid({ posts, onOpenPost, onNewPost, onShowIntro }: Props) {
  return (
    <section className={styles.root}>
      <header className={styles.header}>
        <h1 className={styles.title}>GridFlow</h1>
        <button type="button" className={styles.help} onClick={onShowIntro} aria-label="사용법 보기">
          ?
        </button>
      </header>

      {posts.length === 0 ? (
        <div className={styles.empty}>
          <p>아직 게시물이 없어요</p>
          <p className={styles.emptyHint}>사진을 고르면 테마에 어울리는 순서를 추천해 드려요</p>
        </div>
      ) : (
        <ul className={styles.grid} aria-label="게시물 그리드">
          {posts.map((post) => (
            <li key={post.id}>
              <button
                type="button"
                className={styles.tile}
                onClick={() => onOpenPost(post.id)}
                aria-label={`게시물 열기 (사진 ${post.photos.length}장)`}
              >
                <img src={post.photos[0].url} alt="" />
                {post.photos.length > 1 && <span className={styles.carouselMark} data-carousel aria-hidden="true" />}
              </button>
            </li>
          ))}
        </ul>
      )}

      <button type="button" className={styles.fab} onClick={onNewPost}>
        + 새 게시물
      </button>
    </section>
  );
}
```

`Frontend/components/FeedGrid.module.css`:

```css
.root {
  padding-top: var(--space-4);
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) 0 var(--space-4);
}

.title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.help {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--surface);
}

.grid {
  list-style: none;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2px;
}

.tile {
  position: relative;
  display: block;
  width: 100%;
  aspect-ratio: 3 / 4;
  padding: 0;
  border: 0;
  background: var(--border);
  overflow: hidden;
}

.tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.carouselMark {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 14px;
  height: 14px;
  border: 2px solid #fff;
  border-radius: 3px;
  box-shadow: 3px -3px 0 -1px rgba(255, 255, 255, 0.9);
}

.empty {
  padding: 64px 0;
  text-align: center;
  color: var(--text-muted);
  display: grid;
  gap: var(--space-2);
}

.emptyHint {
  font-size: 14px;
}

.fab {
  position: fixed;
  left: 50%;
  bottom: calc(24px + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  padding: 14px 22px;
  border: 0;
  border-radius: 999px;
  background: var(--accent);
  color: var(--accent-text);
  font-weight: 600;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.18);
}
```

`Frontend/components/PostSheet.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { Post } from "@/lib/state";
import { getTheme } from "@/lib/themes";
import { CarouselStrip } from "./CarouselStrip";
import styles from "./PostSheet.module.css";

interface Props {
  post: Post;
  onClose: () => void;
  onDelete: (postId: string) => void;
}

export function PostSheet({ post, onClose, onDelete }: Props) {
  const [confirming, setConfirming] = useState(false);

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="게시물 상세"
        className={styles.sheet}
        onClick={(event) => event.stopPropagation()}
      >
        <div className={styles.handle} aria-hidden="true" />
        <p className={styles.meta}>
          {getTheme(post.themeId).label} 테마 · 사진 {post.photos.length}장
        </p>
        <CarouselStrip photos={post.photos} label="캐러셀 순서" />
        {confirming ? (
          <div className={styles.actions}>
            <p className={styles.confirmText}>이 게시물을 그리드에서 지울까요?</p>
            <button type="button" className={styles.danger} onClick={() => onDelete(post.id)}>
              삭제할게요
            </button>
            <button type="button" className={styles.secondary} onClick={() => setConfirming(false)}>
              취소
            </button>
          </div>
        ) : (
          <div className={styles.actions}>
            <button type="button" className={styles.secondary} onClick={() => setConfirming(true)}>
              삭제
            </button>
            <button type="button" className={styles.primary} onClick={onClose}>
              닫기
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
```

`Frontend/components/PostSheet.module.css`:

```css
.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 10;
}

.sheet {
  width: 100%;
  max-width: 480px;
  background: var(--surface);
  border-radius: 20px 20px 0 0;
  padding: var(--space-3) var(--space-4) calc(var(--space-6) + env(safe-area-inset-bottom));
  display: grid;
  gap: var(--space-4);
}

.handle {
  justify-self: center;
  width: 40px;
  height: 4px;
  border-radius: 2px;
  background: var(--border);
}

.meta {
  color: var(--text-muted);
  font-size: 14px;
}

.actions {
  display: grid;
  gap: var(--space-2);
}

.confirmText {
  text-align: center;
}

.primary,
.secondary,
.danger {
  padding: 14px;
  border-radius: var(--radius);
  font-weight: 600;
}

.primary {
  border: 0;
  background: var(--accent);
  color: var(--accent-text);
}

.secondary {
  border: 1px solid var(--border);
  background: transparent;
}

.danger {
  border: 0;
  background: var(--danger);
  color: #fff;
}
```

`Frontend/components/IntroModal.tsx`:

```tsx
"use client";

import { useState } from "react";
import styles from "./IntroModal.module.css";

const SLIDES = [
  { title: "사진을 고르면", body: "한 게시물에 넣을 사진을 최대 20장까지 골라 주세요." },
  { title: "테마에 안 맞는 사진을 골라내고", body: "흑백 · 비비드 · 골든아워 중 고른 테마와 어울리지 않는 사진을 알려 드려요." },
  { title: "넘겨 볼 순서를 추천해요", body: "색감이 자연스럽게 이어지도록 캐러셀 순서를 정해 드려요." },
] as const;

export function IntroModal({ onClose }: { onClose: () => void }) {
  const [index, setIndex] = useState(0);
  const isLast = index === SLIDES.length - 1;
  const slide = SLIDES[index];

  return (
    <div className={styles.backdrop}>
      <div role="dialog" aria-modal="true" aria-labelledby="intro-title" className={styles.modal}>
        <p className={styles.step}>
          {index + 1} / {SLIDES.length}
        </p>
        <h2 id="intro-title" className={styles.title}>
          {slide.title}
        </h2>
        <p className={styles.body}>{slide.body}</p>
        <div className={styles.dots} aria-hidden="true">
          {SLIDES.map((s, i) => (
            <span key={s.title} data-active={i === index} />
          ))}
        </div>
        <div className={styles.actions}>
          {!isLast && (
            <button type="button" className={styles.skip} onClick={onClose}>
              건너뛰기
            </button>
          )}
          <button type="button" className={styles.primary} onClick={() => (isLast ? onClose() : setIndex(index + 1))}>
            {isLast ? "시작하기" : "다음"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

`Frontend/components/IntroModal.module.css`:

```css
.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: grid;
  place-items: center;
  padding: var(--space-4);
  z-index: 20;
}

.modal {
  width: 100%;
  max-width: 400px;
  background: var(--surface);
  border-radius: 20px;
  padding: var(--space-6);
  display: grid;
  gap: var(--space-3);
}

.step {
  color: var(--text-muted);
  font-size: 13px;
}

.title {
  font-size: 22px;
  letter-spacing: -0.02em;
}

.body {
  color: var(--text-muted);
  line-height: 1.5;
}

.dots {
  display: flex;
  gap: 6px;
  padding: var(--space-2) 0;
}

.dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--border);
}

.dots span[data-active="true"] {
  width: 18px;
  border-radius: 3px;
  background: var(--text);
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

.skip {
  border: 0;
  background: transparent;
  color: var(--text-muted);
  padding: 12px;
}

.primary {
  border: 0;
  border-radius: var(--radius);
  background: var(--accent);
  color: var(--accent-text);
  padding: 12px 20px;
  font-weight: 600;
}
```

- [ ] **Step 5: 통과 확인**

Run: `npm test && npm run typecheck && npm run lint`
Expected: 전부 PASS

- [ ] **Step 6: 커밋 (승인 후)**

```bash
git add Frontend/lib/introSeen.ts Frontend/lib/introSeen.test.ts Frontend/components
git commit -m "feat(frontend): 그리드 홈·게시물 상세 시트·소개 모달 화면 (#22)"
```

---

### Task 8: 게시물 만들기 화면 조각 (`ThemePicker`, `PhotoPicker`, `AnalyzingView`, `ResultView`)

**Files:**
- Create: `Frontend/components/StepHeader.tsx` + `.module.css`, `ThemePicker.tsx` + `.module.css`, `PhotoPicker.tsx` + `.module.css`, `AnalyzingView.tsx` + `.module.css`, `ResultView.tsx` + `.module.css`, `Frontend/components/buttons.module.css`
- Test: `Frontend/components/flow.test.tsx`

**Interfaces:**
- Consumes: `THEMES`, `ThemeId` (Task 4), `ArrangeError` (Task 5), `DraftPhoto`, `ResultView` 타입 (Task 6), `MAX_PHOTOS` (Task 3), `CarouselStrip` (Task 7)
- Produces:
  - `StepHeader({ title: string; onBack(): void })`
  - `ThemePicker({ onSelect(themeId: ThemeId): void; onBack(): void })`
  - `PhotoPicker({ photos: DraftPhoto[]; notice: string | null; adding: boolean; onAdd(files: File[]): void; onRemove(id: string): void; onAnalyze(): void; onBack(): void })`
  - `AnalyzingView({ error: ArrangeError | null; onRetry(): void; onRepick(): void })` — 부모가 시도마다 `key`를 바꿔 10초 안내 타이머를 초기화
  - `ResultView({ themeLabel: string; view: ResultView; onAddToGrid(): void; onRepick(): void; onChangeTheme(): void })` (컴포넌트 이름과 타입 이름이 같으므로 타입은 `import type { ResultView as ResultViewData }`로 가져온다)

- [ ] **Step 1: 실패하는 테스트 작성**

`Frontend/components/flow.test.tsx`:

```tsx
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ArrangeError } from "@/lib/api";
import type { DraftPhoto } from "@/lib/state";
import { AnalyzingView } from "./AnalyzingView";
import { PhotoPicker } from "./PhotoPicker";
import { ResultView } from "./ResultView";
import { ThemePicker } from "./ThemePicker";

function photo(id: string): DraftPhoto {
  return { id, blob: new Blob(), url: `blob:${id}` };
}

describe("ThemePicker", () => {
  it("테마 카드를 누르면 그 테마 id로 알린다", async () => {
    const onSelect = vi.fn();
    render(<ThemePicker onSelect={onSelect} onBack={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /골든아워/ }));

    expect(onSelect).toHaveBeenCalledWith("golden");
  });
});

describe("PhotoPicker", () => {
  const base = { notice: null, adding: false, onAdd: vi.fn(), onRemove: vi.fn(), onAnalyze: vi.fn(), onBack: vi.fn() };

  it("사진이 없으면 분석하기를 누를 수 없다", () => {
    render(<PhotoPicker {...base} photos={[]} />);

    expect(screen.getByRole("button", { name: "분석하기" })).toBeDisabled();
    expect(screen.getByText("0 / 20")).toBeInTheDocument();
  });

  it("고른 장수와 안내 문구를 보여주고, 사진을 뺄 수 있다", async () => {
    const onRemove = vi.fn();
    render(<PhotoPicker {...base} onRemove={onRemove} notice="최대 20장까지 고를 수 있어요" photos={[photo("0.jpg"), photo("1.jpg")]} />);

    expect(screen.getByText("2 / 20")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("최대 20장까지 고를 수 있어요");
    await userEvent.click(screen.getAllByRole("button", { name: "이 사진 빼기" })[1]);
    expect(onRemove).toHaveBeenCalledWith("1.jpg");
  });

  it("20장이 차면 더 고를 수 없다", () => {
    const full = Array.from({ length: 20 }, (_, i) => photo(`${i}.jpg`));
    render(<PhotoPicker {...base} photos={full} />);

    expect(screen.getByRole("button", { name: "갤러리에서 선택" })).toBeDisabled();
  });
});

describe("AnalyzingView", () => {
  it("10초가 지나면 서버를 깨우는 중일 수 있다고 안내한다", () => {
    vi.useFakeTimers();
    render(<AnalyzingView error={null} onRetry={vi.fn()} onRepick={vi.fn()} />);

    expect(screen.getByText("사진을 분석하고 있어요")).toBeInTheDocument();
    expect(screen.queryByText(/서버를 깨우는 중/)).not.toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(screen.getByText(/서버를 깨우는 중/)).toBeInTheDocument();
    vi.useRealTimers();
  });

  it.each([
    ["network", "서버에 연결할 수 없어요"],
    ["timeout", "분석이 너무 오래 걸려요. 사진 수를 줄여 보세요"],
    ["server", "잠시 문제가 생겼어요"],
  ] as const)("%s 에러는 '%s'와 다시 시도 버튼", async (kind, message) => {
    const onRetry = vi.fn();
    render(<AnalyzingView error={new ArrangeError(kind, "x")} onRetry={onRetry} onRepick={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent(message);
    await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("bad_request는 서버 메시지를 보여주고 다시 시도 없이 사진 다시 고르기만", () => {
    render(<AnalyzingView error={new ArrangeError("bad_request", "사진은 최대 20장까지 보낼 수 있음")} onRetry={vi.fn()} onRepick={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent("사진은 최대 20장까지 보낼 수 있음");
    expect(screen.queryByRole("button", { name: "다시 시도" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "사진 다시 고르기" })).toBeInTheDocument();
  });
});

describe("ResultView", () => {
  const handlers = { onAddToGrid: vi.fn(), onRepick: vi.fn(), onChangeTheme: vi.fn() };

  it("추천 순서·빼는 걸 추천·분석 못 한 사진을 보여준다", () => {
    render(
      <ResultView
        themeLabel="골든아워"
        view={{
          ordered: [photo("2.jpg"), photo("0.jpg")],
          removed: [{ photo: photo("1.jpg"), score: 0.214 }],
          skipped: [{ id: "3.jpg", reason: "용량 초과(5MB 제한)", photo: photo("3.jpg") }],
        }}
        {...handlers}
      />,
    );

    const order = screen.getByRole("list", { name: "추천 캐러셀 순서" });
    expect([...order.querySelectorAll("img")].map((img) => img.getAttribute("data-photo-id"))).toEqual(["2.jpg", "0.jpg"]);
    expect(screen.getByRole("list", { name: "빼는 걸 추천하는 사진" })).toHaveTextContent("점수 0.21");
    expect(screen.getByText("분석하지 못한 사진 1장")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "그리드에 추가" })).toBeInTheDocument();
  });

  it("전부 제거 후보면 안내와 다른 테마 버튼을 보여주고 그리드 추가는 숨긴다", async () => {
    const onChangeTheme = vi.fn();
    render(
      <ResultView
        themeLabel="흑백"
        view={{ ordered: [], removed: [{ photo: photo("0.jpg"), score: 0.1 }], skipped: [] }}
        {...handlers}
        onChangeTheme={onChangeTheme}
      />,
    );

    expect(screen.getByText("이 테마와 어울리는 사진이 없어요")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "그리드에 추가" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "다른 테마로 해보기" }));
    expect(onChangeTheme).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd Frontend && npm test -- components/flow.test.tsx`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 구현 — 공용 버튼 스타일과 머리말**

`Frontend/components/buttons.module.css`:

```css
.primary,
.secondary {
  width: 100%;
  padding: 14px;
  border-radius: var(--radius);
  font-weight: 600;
}

.primary {
  border: 0;
  background: var(--accent);
  color: var(--accent-text);
}

.secondary {
  border: 1px solid var(--border);
  background: transparent;
}

.actions {
  display: grid;
  gap: var(--space-2);
  margin-top: var(--space-6);
}
```

`Frontend/components/StepHeader.tsx`:

```tsx
import styles from "./StepHeader.module.css";

export function StepHeader({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <header className={styles.header}>
      <button type="button" className={styles.back} onClick={onBack} aria-label="뒤로">
        ←
      </button>
      <h1 className={styles.title}>{title}</h1>
    </header>
  );
}
```

`Frontend/components/StepHeader.module.css`:

```css
.header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) 0;
}

.back {
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  font-size: 20px;
}

.title {
  font-size: 18px;
  font-weight: 700;
}
```

- [ ] **Step 4: 구현 — `ThemePicker`**

`Frontend/components/ThemePicker.tsx`:

```tsx
import { THEMES, type ThemeId } from "@/lib/themes";
import { StepHeader } from "./StepHeader";
import styles from "./ThemePicker.module.css";

export function ThemePicker({ onSelect, onBack }: { onSelect: (themeId: ThemeId) => void; onBack: () => void }) {
  return (
    <section>
      <StepHeader title="테마 고르기" onBack={onBack} />
      <p className={styles.lead}>어떤 분위기의 게시물인가요?</p>
      <ul className={styles.list}>
        {THEMES.map((theme) => (
          <li key={theme.id}>
            <button type="button" className={styles.card} onClick={() => onSelect(theme.id)}>
              <span className={styles.swatch} aria-hidden="true">
                {theme.swatch.map((color) => (
                  <span key={color} style={{ background: color }} />
                ))}
              </span>
              <span className={styles.text}>
                <span className={styles.label}>{theme.label}</span>
                <span className={styles.description}>{theme.description}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

`Frontend/components/ThemePicker.module.css`:

```css
.lead {
  color: var(--text-muted);
  margin-bottom: var(--space-4);
}

.list {
  list-style: none;
  padding: 0;
  display: grid;
  gap: var(--space-3);
}

.card {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  text-align: left;
}

.swatch {
  display: flex;
  flex-shrink: 0;
}

.swatch span {
  width: 22px;
  height: 44px;
}

.swatch span:first-child {
  border-radius: 8px 0 0 8px;
}

.swatch span:last-child {
  border-radius: 0 8px 8px 0;
}

.text {
  display: grid;
  gap: 2px;
}

.label {
  font-weight: 700;
}

.description {
  color: var(--text-muted);
  font-size: 14px;
}
```

- [ ] **Step 5: 구현 — `PhotoPicker`**

`Frontend/components/PhotoPicker.tsx`:

```tsx
"use client";

import { useRef } from "react";
import { MAX_PHOTOS } from "@/lib/limits";
import type { DraftPhoto } from "@/lib/state";
import buttons from "./buttons.module.css";
import styles from "./PhotoPicker.module.css";
import { StepHeader } from "./StepHeader";

interface Props {
  photos: DraftPhoto[];
  notice: string | null;
  adding: boolean;
  onAdd: (files: File[]) => void;
  onRemove: (id: string) => void;
  onAnalyze: () => void;
  onBack: () => void;
}

export function PhotoPicker({ photos, notice, adding, onAdd, onRemove, onAnalyze, onBack }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const full = photos.length >= MAX_PHOTOS;

  return (
    <section>
      <StepHeader title="사진 고르기" onBack={onBack} />
      <p className={styles.count} aria-live="polite">
        {photos.length} / {MAX_PHOTOS}
      </p>
      {notice && (
        <p role="status" className={styles.notice}>
          {notice}
        </p>
      )}

      <ul className={styles.grid} aria-label="고른 사진">
        {photos.map((photo) => (
          <li key={photo.id} className={styles.item}>
            <img src={photo.url} alt="고른 사진" data-photo-id={photo.id} />
            <button type="button" className={styles.remove} aria-label="이 사진 빼기" onClick={() => onRemove(photo.id)}>
              ×
            </button>
          </li>
        ))}
      </ul>

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = ""; // 같은 사진을 다시 골라도 change가 일어나게
          if (files.length > 0) onAdd(files);
        }}
      />

      <div className={buttons.actions}>
        <button type="button" className={buttons.secondary} disabled={full || adding} onClick={() => inputRef.current?.click()}>
          {adding ? "사진 준비 중…" : "갤러리에서 선택"}
        </button>
        <button type="button" className={buttons.primary} disabled={photos.length === 0 || adding} onClick={onAnalyze}>
          분석하기
        </button>
      </div>
    </section>
  );
}
```

`Frontend/components/PhotoPicker.module.css`:

```css
.count {
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  margin-bottom: var(--space-3);
}

.notice {
  margin-bottom: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius);
  background: var(--surface);
  border: 1px solid var(--border);
  font-size: 14px;
}

.grid {
  list-style: none;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-1);
}

.item {
  position: relative;
}

.item img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: 8px;
}

.remove {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  line-height: 1;
}
```

- [ ] **Step 6: 구현 — `AnalyzingView`**

`Frontend/components/AnalyzingView.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import type { ArrangeError } from "@/lib/api";
import styles from "./AnalyzingView.module.css";
import buttons from "./buttons.module.css";

const SLOW_HINT_MS = 10_000;

function errorMessage(error: ArrangeError): string {
  switch (error.kind) {
    case "network":
      return "서버에 연결할 수 없어요";
    case "timeout":
      return "분석이 너무 오래 걸려요. 사진 수를 줄여 보세요";
    case "server":
      return "잠시 문제가 생겼어요";
    case "bad_request":
      return error.message; // 정상 흐름에선 프론트가 미리 막으므로, 보인다면 버그 — 서버 문구 그대로
  }
}

export function AnalyzingView({ error, onRetry, onRepick }: { error: ArrangeError | null; onRetry: () => void; onRepick: () => void }) {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (error) return;
    const timer = setTimeout(() => setSlow(true), SLOW_HINT_MS);
    return () => clearTimeout(timer);
  }, [error]);

  if (error) {
    return (
      <section className={styles.card} role="alert">
        <h2 className={styles.message}>{errorMessage(error)}</h2>
        <div className={buttons.actions}>
          {error.kind !== "bad_request" && (
            <button type="button" className={buttons.primary} onClick={onRetry}>
              다시 시도
            </button>
          )}
          <button type="button" className={buttons.secondary} onClick={onRepick}>
            사진 다시 고르기
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className={styles.loading} aria-busy="true">
      <div className={styles.spinner} aria-hidden="true" />
      <p>사진을 분석하고 있어요</p>
      {slow && <p className={styles.hint}>서버를 깨우는 중일 수 있어요. 조금만 기다려 주세요</p>}
    </section>
  );
}
```

`Frontend/components/AnalyzingView.module.css`:

```css
.loading {
  min-height: 70dvh;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: var(--space-3);
  text-align: center;
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--border);
  border-top-color: var(--text);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
}

.hint {
  color: var(--text-muted);
  font-size: 14px;
}

.card {
  margin-top: 30dvh;
  padding: var(--space-6);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
}

.message {
  font-size: 18px;
  line-height: 1.4;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation-duration: 2.5s;
  }
}
```

- [ ] **Step 7: 구현 — `ResultView`**

`Frontend/components/ResultView.tsx`:

```tsx
import type { ResultView as ResultViewData } from "@/lib/state";
import buttons from "./buttons.module.css";
import { CarouselStrip } from "./CarouselStrip";
import styles from "./ResultView.module.css";
import { StepHeader } from "./StepHeader";

interface Props {
  themeLabel: string;
  view: ResultViewData;
  onAddToGrid: () => void;
  onRepick: () => void;
  onChangeTheme: () => void;
}

export function ResultView({ themeLabel, view, onAddToGrid, onRepick, onChangeTheme }: Props) {
  const { ordered, removed, skipped } = view;

  return (
    <section>
      <StepHeader title="추천 결과" onBack={onRepick} />

      {ordered.length === 0 ? (
        <div className={styles.empty} role="status">
          <p>이 테마와 어울리는 사진이 없어요</p>
          <button type="button" className={buttons.primary} onClick={onChangeTheme}>
            다른 테마로 해보기
          </button>
        </div>
      ) : (
        <>
          <h2 className={styles.heading}>이 순서로 올려 보세요</h2>
          <p className={styles.sub}>
            {themeLabel} · 사진 {ordered.length}장
          </p>
          <CarouselStrip photos={ordered} label="추천 캐러셀 순서" />
        </>
      )}

      {removed.length > 0 && (
        <div className={styles.block}>
          <h3 className={styles.blockTitle}>빼는 걸 추천해요</h3>
          <p className={styles.sub}>{themeLabel} 테마와 잘 어울리지 않아요</p>
          <ul className={styles.removed} aria-label="빼는 걸 추천하는 사진">
            {removed.map(({ photo, score }) => (
              <li key={photo.id}>
                <img src={photo.url} alt="빼는 걸 추천하는 사진" data-photo-id={photo.id} />
                <span>점수 {score.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {skipped.length > 0 && (
        <p className={styles.skipped} role="status">
          분석하지 못한 사진 {skipped.length}장
        </p>
      )}

      <div className={buttons.actions}>
        {ordered.length > 0 && (
          <button type="button" className={buttons.primary} onClick={onAddToGrid}>
            그리드에 추가
          </button>
        )}
        <button type="button" className={buttons.secondary} onClick={onRepick}>
          사진 다시 고르기
        </button>
      </div>
    </section>
  );
}
```

`Frontend/components/ResultView.module.css`:

```css
.heading {
  font-size: 22px;
  letter-spacing: -0.02em;
}

.sub {
  color: var(--text-muted);
  font-size: 14px;
  margin: var(--space-1) 0 var(--space-4);
}

.block {
  margin-top: var(--space-6);
}

.blockTitle {
  font-size: 16px;
}

.removed {
  list-style: none;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-2);
}

.removed li {
  display: grid;
  gap: var(--space-1);
  font-size: 12px;
  color: var(--text-muted);
}

.removed img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: 8px;
  opacity: 0.6;
}

.skipped {
  margin-top: var(--space-4);
  color: var(--text-muted);
  font-size: 14px;
}

.empty {
  padding: 48px 0 var(--space-4);
  display: grid;
  gap: var(--space-4);
  text-align: center;
}
```

- [ ] **Step 8: 통과 확인**

Run: `npm test && npm run typecheck && npm run lint`
Expected: 전부 PASS

- [ ] **Step 9: 커밋 (승인 후)**

```bash
git add Frontend/components
git commit -m "feat(frontend): 테마 선택·사진 고르기·분석 중·결과 화면 (#22)"
```

---

### Task 9: 화면 연결 (`GridFlowApp`) + 뒤로가기 + E2E

**Files:**
- Create: `Frontend/components/GridFlowApp.tsx`, `Frontend/e2e/flow.spec.ts`
- Modify: `Frontend/app/page.tsx`

**Interfaces:**
- Consumes: Task 4~8의 모든 export
- Produces: `GridFlowApp()` — `app/page.tsx`가 그대로 렌더

뒤로가기 동작 규칙: 홈에서 다른 단계로 들어갈 때 히스토리 항목을 하나 쌓고(`pushState({ gridflow: true })`), 이후 단계 이동은 항목을 늘리지 않는다. 휴대폰 뒤로가기(`popstate`)가 오면 `PREVIOUS_STEP`으로 이동하고, 아직 홈이 아니면 항목을 다시 하나 쌓아 다음 뒤로가기도 앱 안에서 처리한다. 화면의 ← 버튼은 `history.back()`을 불러 같은 경로를 탄다. `analyzing`에서 뒤로가면 요청을 취소한다. "그리드에 추가"로 홈에 갈 때는 `replaceState(null)`로 항목을 비운다.

- [ ] **Step 1: 실패하는 E2E 작성**

`Frontend/e2e/flow.spec.ts`:

```ts
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const SAMPLES = path.resolve(__dirname, "../../samples");
const sample = (name: string) => path.join(SAMPLES, name);

const okResponse = {
  removed_candidates: [{ photo_id: "2.jpg", score: 0.21 }],
  skipped: [],
  groups: [{ order: ["1.jpg", "0.jpg"], adjacency_costs: [["1.jpg", "0.jpg", 0.1]] }],
};

async function dismissIntro(page: Page) {
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByRole("button", { name: "다음" }).click();
  await page.getByRole("button", { name: "시작하기" }).click();
}

async function pickThreePhotos(page: Page) {
  await page.getByRole("button", { name: "+ 새 게시물" }).click();
  await page.getByRole("button", { name: /골든아워/ }).click();
  await page.locator('input[type="file"]').setInputFiles([sample("photo1.JPG"), sample("photo2.JPG"), sample("photo10.JPG")]);
  await expect(page.getByText("3 / 20")).toBeVisible();
}

test("게시물 하나를 만들어 그리드에 쌓고 지운다", async ({ page }) => {
  await page.route("**/arrange", (route) => route.fulfill({ json: okResponse }));
  await page.goto("/");
  await dismissIntro(page);

  await pickThreePhotos(page);

  // 4032x3024 원본이 512px 이하로 줄었는지 — 썸네일은 리사이즈한 Blob으로 그린다
  const sizes = await page
    .getByRole("list", { name: "고른 사진" })
    .locator("img")
    .evaluateAll((imgs) => imgs.map((img) => Math.max((img as HTMLImageElement).naturalWidth, (img as HTMLImageElement).naturalHeight)));
  expect(sizes).toHaveLength(3);
  for (const size of sizes) expect(size).toBeLessThanOrEqual(512);

  await page.getByRole("button", { name: "분석하기" }).click();

  const order = page.getByRole("list", { name: "추천 캐러셀 순서" }).locator("img");
  await expect(order).toHaveCount(2);
  expect(await order.evaluateAll((imgs) => imgs.map((img) => img.getAttribute("data-photo-id")))).toEqual(["1.jpg", "0.jpg"]);
  await expect(page.getByRole("list", { name: "빼는 걸 추천하는 사진" })).toContainText("점수 0.21");

  await page.getByRole("button", { name: "그리드에 추가" }).click();
  const tiles = page.getByRole("button", { name: /게시물 열기/ });
  await expect(tiles).toHaveCount(1);

  await tiles.first().click();
  await page.getByRole("button", { name: "삭제", exact: true }).click();
  await page.getByRole("button", { name: "삭제할게요" }).click();
  await expect(page.getByText("아직 게시물이 없어요")).toBeVisible();
});

test("소개 모달은 처음 방문 때만 뜨고 ?로 다시 볼 수 있다", async ({ page }) => {
  await page.goto("/");
  await dismissIntro(page);
  await page.reload();

  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "사용법 보기" }).click();
  await expect(page.getByRole("heading", { name: "사진을 고르면" })).toBeVisible();
});

test("휴대폰 뒤로가기는 앱 안에서 이전 단계로 간다", async ({ page }) => {
  await page.goto("/");
  await dismissIntro(page);
  await pickThreePhotos(page);

  await page.goBack();
  await expect(page.getByRole("heading", { name: "테마 고르기" })).toBeVisible();
  await page.goBack();
  await expect(page.getByText("아직 게시물이 없어요")).toBeVisible();
});

test("분석 중 뒤로가기는 요청을 취소하고 사진 고르기로 돌아간다", async ({ page }) => {
  await page.route("**/arrange", () => {
    // 응답하지 않아 분석 중 상태로 둔다
  });
  await page.goto("/");
  await dismissIntro(page);
  await pickThreePhotos(page);
  await page.getByRole("button", { name: "분석하기" }).click();
  await expect(page.getByText("사진을 분석하고 있어요")).toBeVisible();

  await page.goBack();

  await expect(page.getByText("3 / 20")).toBeVisible();
});

test("서버 오류 후 다시 시도하면 결과가 나온다", async ({ page }) => {
  let calls = 0;
  await page.route("**/arrange", (route) => {
    calls += 1;
    return calls === 1 ? route.fulfill({ status: 500, body: "" }) : route.fulfill({ json: okResponse });
  });
  await page.goto("/");
  await dismissIntro(page);
  await pickThreePhotos(page);
  await page.getByRole("button", { name: "분석하기" }).click();

  await expect(page.getByRole("alert")).toContainText("잠시 문제가 생겼어요");
  await page.getByRole("button", { name: "다시 시도" }).click();

  await expect(page.getByRole("list", { name: "추천 캐러셀 순서" })).toBeVisible();
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd Frontend && npm run e2e`
Expected: FAIL (홈에 "다음" 버튼 없음 — 아직 자리표시 페이지)

- [ ] **Step 3: 구현**

`Frontend/components/GridFlowApp.tsx`:

```tsx
"use client";

import { useEffect, useReducer, useRef, useState, useSyncExternalStore } from "react";
import { arrange, ArrangeError } from "@/lib/api";
import { hasSeenIntro, markIntroSeen, subscribeIntroSeen } from "@/lib/introSeen";
import { MAX_PHOTOS } from "@/lib/limits";
import { resizeImage } from "@/lib/resize";
import { initialState, PREVIOUS_STEP, reducer, selectResultView, urlsReleasedByAddPost, type Step } from "@/lib/state";
import { getTheme } from "@/lib/themes";
import { AnalyzingView } from "./AnalyzingView";
import { FeedGrid } from "./FeedGrid";
import { IntroModal } from "./IntroModal";
import { PhotoPicker } from "./PhotoPicker";
import { PostSheet } from "./PostSheet";
import { ResultView } from "./ResultView";
import { ThemePicker } from "./ThemePicker";

export function GridFlowApp() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [notice, setNotice] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [introForced, setIntroForced] = useState(false);
  // 정적 빌드(서버)에서는 모달을 그리지 않고, 브라우저에서 저장 여부를 읽은 뒤 띄운다
  const introSeen = useSyncExternalStore(subscribeIntroSeen, hasSeenIntro, () => true);

  const stepRef = useRef<Step>(state.step);
  const draftCountRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    stepRef.current = state.step;
    draftCountRef.current = state.draft.length;
  }, [state.step, state.draft.length]);

  useEffect(() => {
    const onPopState = () => {
      const current = stepRef.current;
      if (current === "home") return;
      if (current === "analyzing") abortRef.current?.abort();
      const previous = PREVIOUS_STEP[current];
      dispatch({ type: "NAVIGATE", step: previous });
      if (previous !== "home") window.history.pushState({ gridflow: true }, "");
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const goBack = () => window.history.back();

  const handleNewPost = () => {
    state.draft.forEach((photo) => URL.revokeObjectURL(photo.url)); // 지난번에 그만둔 초안
    setNotice(null);
    dispatch({ type: "START_NEW" });
    if (!window.history.state?.gridflow) window.history.pushState({ gridflow: true }, "");
  };

  const handleAddFiles = async (files: File[]) => {
    const room = Math.max(MAX_PHOTOS - draftCountRef.current, 0);
    const targets = files.slice(0, room);
    setAdding(true);
    const ready: { blob: Blob; url: string }[] = [];
    let failed = 0;
    for (const file of targets) {
      try {
        const blob = await resizeImage(file);
        ready.push({ blob, url: URL.createObjectURL(blob) });
      } catch {
        failed += 1; // 브라우저가 못 여는 형식(일부 안드로이드 HEIC 등)
      }
    }
    setAdding(false);
    dispatch({ type: "ADD_PHOTOS", photos: ready });
    const messages: string[] = [];
    if (files.length > targets.length) messages.push(`최대 ${MAX_PHOTOS}장까지 고를 수 있어요`);
    if (failed > 0) messages.push(`열 수 없는 사진 ${failed}장을 뺐어요`);
    setNotice(messages.length > 0 ? messages.join(" · ") : null);
  };

  const handleRemovePhoto = (id: string) => {
    const photo = state.draft.find((p) => p.id === id);
    if (photo) URL.revokeObjectURL(photo.url);
    dispatch({ type: "REMOVE_PHOTO", id });
  };

  const runAnalyze = async () => {
    if (!state.themeId || state.draft.length === 0) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    dispatch({ type: "ANALYZE_START" });
    setAttempt((n) => n + 1);
    try {
      const result = await arrange(
        getTheme(state.themeId).prompt,
        state.draft.map((p) => ({ id: p.id, blob: p.blob })),
        { signal: controller.signal },
      );
      dispatch({ type: "ANALYZE_SUCCESS", result });
    } catch (error) {
      if (controller.signal.aborted) return; // 뒤로가기로 취소한 요청
      dispatch({
        type: "ANALYZE_FAILURE",
        error: error instanceof ArrangeError ? error : new ArrangeError("server", String(error)),
      });
    }
  };

  const handleAddToGrid = () => {
    urlsReleasedByAddPost(state).forEach((url) => URL.revokeObjectURL(url));
    dispatch({ type: "ADD_POST" });
    window.history.replaceState(null, "");
  };

  const handleDeletePost = (postId: string) => {
    state.posts.find((p) => p.id === postId)?.photos.forEach((photo) => URL.revokeObjectURL(photo.url));
    dispatch({ type: "DELETE_POST", postId });
  };

  const closeIntro = () => {
    markIntroSeen();
    setIntroForced(false);
  };

  const openPost = state.posts.find((p) => p.id === state.openPostId) ?? null;

  return (
    <main className="app">
      {state.step === "home" && (
        <FeedGrid
          posts={state.posts}
          onOpenPost={(postId) => dispatch({ type: "OPEN_POST", postId })}
          onNewPost={handleNewPost}
          onShowIntro={() => setIntroForced(true)}
        />
      )}
      {state.step === "theme" && <ThemePicker onSelect={(themeId) => dispatch({ type: "SELECT_THEME", themeId })} onBack={goBack} />}
      {state.step === "pick" && (
        <PhotoPicker
          photos={state.draft}
          notice={notice}
          adding={adding}
          onAdd={handleAddFiles}
          onRemove={handleRemovePhoto}
          onAnalyze={runAnalyze}
          onBack={goBack}
        />
      )}
      {state.step === "analyzing" && (
        <AnalyzingView key={attempt} error={state.error} onRetry={runAnalyze} onRepick={() => dispatch({ type: "NAVIGATE", step: "pick" })} />
      )}
      {state.step === "result" && state.themeId && (
        <ResultView
          themeLabel={getTheme(state.themeId).label}
          view={selectResultView(state)}
          onAddToGrid={handleAddToGrid}
          onRepick={() => dispatch({ type: "NAVIGATE", step: "pick" })}
          onChangeTheme={() => dispatch({ type: "NAVIGATE", step: "theme" })}
        />
      )}
      {openPost && <PostSheet post={openPost} onClose={() => dispatch({ type: "CLOSE_POST" })} onDelete={handleDeletePost} />}
      {(!introSeen || introForced) && <IntroModal onClose={closeIntro} />}
    </main>
  );
}
```

`Frontend/app/page.tsx` 전체 교체:

```tsx
import { GridFlowApp } from "@/components/GridFlowApp";

export default function Page() {
  return <GridFlowApp />;
}
```

- [ ] **Step 4: 통과 확인**

Run: `npm test && npm run typecheck && npm run lint && npm run e2e`
Expected: 단위 테스트 전부 PASS, E2E 5개 PASS. `react-hooks` 린트 규칙(예: 렌더 중 ref 접근, effect 안 setState)이 걸리면 그 자리에서 멈추고 규칙 이름과 대안을 보고한다.

- [ ] **Step 5: 로컬 실제 연동 확인 (수동)**

터미널 1: `uvicorn main:app --app-dir Backend` (저장소 루트, `.venv` 활성화)
터미널 2: `cd Frontend && npm run dev`
브라우저 http://localhost:3000 → 골든아워 → `samples/` 사진 3장 → 분석하기 → 결과가 실제 서버 응답으로 나오는지 확인(첫 요청은 CLIP 로딩으로 수십 초). 걸린 시간을 보고에 적는다.

- [ ] **Step 6: 커밋 (승인 후)**

```bash
git add Frontend/components/GridFlowApp.tsx Frontend/app/page.tsx Frontend/e2e
git commit -m "feat(frontend): 화면 연결·뒤로가기·분석 요청 + Playwright E2E (#22)"
```

---

### Task 10: 디자인 다듬기

**Files:**
- Modify: `Frontend/app/globals.css`, `Frontend/components/*.module.css` (필요하면 `app/layout.tsx`의 글꼴)

**Interfaces:**
- Consumes: Task 7~9 화면
- Produces: 없음(시각 변경만, 마크업·aria 이름·`data-photo-id`는 유지 — 테스트가 이것들에 의존)

- [ ] **Step 1: 현재 화면 캡처**

`npm run build && npx serve out -l 3100`을 띄운 뒤 Playwright로 6개 화면(홈 빈 상태·홈 3칸·테마·사진 고르기·결과·상세 시트)을 Pixel 7 크기, 라이트/다크 각각 캡처해 스크래치 폴더에 저장하고 사용자에게 보여준다.

- [ ] **Step 2: `frontend-design` 스킬로 방향 제안**

`frontend-design` 스킬을 불러 spec의 방향(사진이 주인공, 무채색 바탕, 선 최소화, 강조색은 테마 카드·주요 버튼만, 라이트/다크)을 기준으로 글꼴·색 토큰·간격·모션 제안 2안을 캡처와 함께 제시하고, 사용자가 고르게 한다. **사용자가 고르기 전에는 CSS를 바꾸지 않는다.**

- [ ] **Step 3: 적용**

고른 안을 `globals.css` 변수와 각 `*.module.css`에 반영한다. 웹폰트를 쓰면 `next/font/google`로 `app/layout.tsx`에서 불러온다(정적 내보내기에서도 빌드 시 파일로 포함됨).

- [ ] **Step 4: 확인**

Run: `npm test && npm run lint && npm run e2e`
Expected: 전부 PASS. Step 1과 같은 방식으로 다시 캡처해 전후를 보여준다.

- [ ] **Step 5: 커밋 (승인 후)**

```bash
git add Frontend/app Frontend/components
git commit -m "style(frontend): 화면 디자인 다듬기 (#22)"
```

---

### Task 11: CI 워크플로

**Files:**
- Create: `.github/workflows/ci-backend.yml`, `.github/workflows/ci-frontend.yml`

**Interfaces:**
- Consumes: `python -m pytest`(Task 1·2), npm 스크립트 `typecheck`·`lint`·`test`·`build`(Task 3), Playwright 설정(Task 3)
- Produces: PR·push 검사 이름 `CI (backend) / test`, `CI (frontend) / test`

- [ ] **Step 1: 백엔드 CI 작성**

`.github/workflows/ci-backend.yml`:

```yaml
name: CI (backend)

on:
  pull_request:
    branches: [develop, main]
    paths:
      - "Ai/**"
      - "Backend/**"
      - "tests/**"
      - "requirements.txt"
      - "pytest.ini"
      - ".github/workflows/ci-backend.yml"
  push:
    branches: [develop, main, "feature/**"]
    paths:
      - "Ai/**"
      - "Backend/**"
      - "tests/**"
      - "requirements.txt"
      - "pytest.ini"
      - ".github/workflows/ci-backend.yml"

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - name: OpenCV 시스템 라이브러리
        run: sudo apt-get update && sudo apt-get install -y --no-install-recommends libgl1 libglib2.0-0
      - name: 의존성 설치 (torch +cpu는 PyTorch 인덱스에만 있음)
        run: pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
      - name: pytest (integration 제외 — pytest.ini addopts)
        run: python -m pytest -v
```

`push`에 `feature/**`를 넣은 이유: 기능 브랜치에 push할 때도 검사가 돌아 PR을 열기 전에 결과를 볼 수 있다(`workflow_dispatch`는 기본 브랜치에 파일이 있어야 해서 지금은 못 씀).

- [ ] **Step 2: 프론트 CI 작성**

`.github/workflows/ci-frontend.yml`:

```yaml
name: CI (frontend)

on:
  pull_request:
    branches: [develop, main]
    paths:
      - "Frontend/**"
      - "Ai/collect_unsplash_data.py"
      - "Backend/main.py"
      - ".github/workflows/ci-frontend.yml"
  push:
    branches: [develop, main, "feature/**"]
    paths:
      - "Frontend/**"
      - "Ai/collect_unsplash_data.py"
      - "Backend/main.py"
      - ".github/workflows/ci-frontend.yml"

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: Frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: Frontend/.nvmrc
          cache: npm
          cache-dependency-path: Frontend/package-lock.json
      - run: npm ci
      - run: npm run typecheck
      - run: npm run lint
      - run: npm test
      - run: npm run build
      - run: npx playwright install --with-deps chromium
      - run: npx playwright test
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: Frontend/playwright-report
          retention-days: 7
```

`Ai/collect_unsplash_data.py`와 `Backend/main.py`가 경로에 있는 이유: 프론트 테스트가 이 두 파일을 읽어 테마 문장·`MAX_PHOTOS`를 비교한다.

- [ ] **Step 3: 로컬 문법 확인**

Run: `python -c "import yaml,sys; [yaml.safe_load(open(f, encoding='utf-8')) for f in sys.argv[1:]]; print('ok')" .github/workflows/ci-backend.yml .github/workflows/ci-frontend.yml`
Expected: `ok`

- [ ] **Step 4: 커밋 + push 후 실제 실행 확인 (승인 후)**

```bash
git add .github/workflows/ci-backend.yml .github/workflows/ci-frontend.yml
git commit -m "ci: 백엔드 pytest + 프론트 타입·린트·테스트·빌드·E2E 워크플로 (#22)"
git push
```

Run: `gh run list --branch "feature/프론트엔드-배포/22" --limit 4` 후 `gh run watch <run-id>`
Expected: `CI (backend)`, `CI (frontend)` 둘 다 success. 실패하면 `gh run view <run-id> --log-failed`로 원인을 보고 고친다(예: 러너에서 빠진 시스템 라이브러리, 로컬과 다른 경로 대소문자).

---

### Task 12: AWS 인프라 구성 + 수동 첫 배포 + 실측

이 태스크는 대부분 사용자가 AWS·Netlify 콘솔에서 직접 하고, 에이전트는 단계별 안내·명령 준비·결과 확인·문서 작성을 맡는다. **콘솔 작업은 단계마다 사용자 확인을 받으며 진행한다.**

**Files:**
- Create: `docs/backend/Deploy.md`

**Interfaces:**
- Consumes: Task 2의 `ALLOWED_ORIGINS`, 기존 `Dockerfile`
- Produces (Task 13이 GitHub 저장소 변수로 사용): `AWS_ACCOUNT_ID`, `EC2_INSTANCE_ID`, CloudFront 주소(`https://<배포ID>.cloudfront.net`), Netlify 주소(`https://<사이트>.netlify.app`), 역할 `gridflow-ec2`

- [ ] **Step 1: 계정 준비 (사용자)**

AWS 가입(서울 리전) → 루트 MFA → 작업용 IAM 사용자(콘솔 접근, `AdministratorAccess`, MFA) → AWS Budgets 월 예산 $30, 알림 $5·$20·$30(실제 비용 기준, 이메일). 요금 계산기로 t3.small·gp3 30GB·공인 IPv4 월 비용을 확인해 보고에 적는다.

- [ ] **Step 2: EC2 역할 (사용자)**

IAM → 역할 생성 → 신뢰 대상 EC2 → 정책 `AmazonSSMManagedInstanceCore`, `AmazonEC2ContainerRegistryReadOnly` → 이름 `gridflow-ec2`.

- [ ] **Step 3: EC2 생성 (사용자)**

인스턴스 시작: 이름 `gridflow-backend`, Ubuntu Server 24.04 LTS(x86), t3.small, 키 페어 없음, 보안 그룹 새로 만들기(`gridflow-backend-sg`) — 인바운드 규칙은 Step 6에서 넣으므로 SSH 규칙은 지운다, 스토리지 gp3 30GB, 고급 세부 정보 → IAM 인스턴스 프로파일 `gridflow-ec2`. 생성 후 탄력적 IP 할당 → 이 인스턴스에 연결. 인스턴스 ID와 퍼블릭 IPv4 DNS를 기록.

- [ ] **Step 4: 서버 준비 (사용자, Session Manager)**

EC2 → 인스턴스 → 연결 → Session Manager로 접속(뜨지 않으면 몇 분 기다림 — SSM 에이전트가 역할을 인식하는 시간). 아래를 실행:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo apt-get update && sudo apt-get install -y docker.io git
sudo systemctl enable --now docker
sudo snap install aws-cli --classic
free -h && docker --version && aws --version
```

- [ ] **Step 5: 수동 첫 배포 — EC2 안에서 한 번 빌드 (사용자)**

CD(Task 13)는 `main`에 머지돼야 돌기 때문에, 인프라 확인용으로 한 번만 EC2에서 직접 빌드한다(10~20분):

```bash
git clone https://github.com/jinohpark371/GridFlow.git && cd GridFlow && git checkout "feature/프론트엔드-배포/22"
sudo docker build -t gridflow-backend:manual .
sudo docker run -d --name gridflow --restart unless-stopped -p 8000:8000 \
  -e ALLOWED_ORIGINS=http://localhost:3000 gridflow-backend:manual
sleep 90 && curl -s localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 6: 보안 그룹 (사용자)**

`gridflow-backend-sg` 인바운드: 유형 사용자 지정 TCP, 포트 8000, 소스 = 접두사 목록 `com.amazonaws.global.cloudfront.origin-facing`. 다른 인바운드 규칙 없음.

- [ ] **Step 7: CloudFront (사용자)**

배포 생성: 오리진 도메인 = EC2 퍼블릭 IPv4 DNS, 프로토콜 HTTP만, HTTP 포트 8000, 응답 제한 시간 60초 / 뷰어 프로토콜 Redirect HTTP to HTTPS / 허용 HTTP 방법 GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE / 캐시 정책 `CachingDisabled` / 오리진 요청 정책 `AllViewerExceptHostHeader` / WAF 사용 안 함. 배포 완료(수 분) 후:

```bash
curl -s https://<배포ID>.cloudfront.net/health
curl -s -m 5 http://<탄력적 IP>:8000/health; echo "exit=$?"
```

Expected: 첫 줄 `{"status":"ok"}`, 둘째 줄은 응답 없이 시간 초과(`exit=28`) — EC2 직접 접속이 막혔는지 확인

- [ ] **Step 8: Netlify 사이트 만들기 (사용자)**

Netlify → Add new site → GitHub `jinohpark371/GridFlow` 연결 → Base directory `Frontend`, Build command `npm run build`, Publish directory `Frontend/out`, Production branch `main`. 사이트 이름을 정해 주소(`https://<사이트>.netlify.app`)를 기록. (아직 `main`에 `Frontend/`가 없어 첫 빌드는 실패해도 된다)

- [ ] **Step 9: 운영 CORS로 재시작 + 실측 (사용자, Session Manager)**

```bash
sudo docker rm -f gridflow
sudo docker run -d --name gridflow --restart unless-stopped -p 8000:8000 \
  -e ALLOWED_ORIGINS=https://<사이트>.netlify.app,http://localhost:3000 gridflow-backend:manual
sleep 90
sudo docker stats --no-stream gridflow
```

에이전트가 로컬에서 CloudFront로 8장·20장 실측 요청을 보낸다(원본 대신 512px로 줄인 샘플 사용):

```bash
.venv/Scripts/python.exe -c "
import io, sys, time, httpx
from pathlib import Path
from PIL import Image
url = sys.argv[1] + '/arrange'
paths = sorted(Path('samples').glob('*.JPG'))
def small(p):
    img = Image.open(p).convert('RGB'); img.thumbnail((512, 512))
    buf = io.BytesIO(); img.save(buf, 'JPEG', quality=85); return buf.getvalue()
blobs = [small(p) for p in paths]
for n in [8, 20]:
    files = [('photos', (f'{i}.jpg', blobs[i % len(blobs)], 'image/jpeg')) for i in range(n)]
    t = time.perf_counter()
    r = httpx.post(url, data={'theme': 'warm golden hour sunset photography', 'group_ids': ['0'] * n}, files=files, timeout=120)
    print(n, '장:', r.status_code, f'{time.perf_counter() - t:.1f}s')
" https://<배포ID>.cloudfront.net
```

Expected: 둘 다 200, 20장이 60초 안. 60초를 넘거나 메모리가 2GB에 가까우면(스왑 사용 큼) 멈추고 `MAX_PHOTOS` 하향·인스턴스 변경 선택지를 보고한다.

- [ ] **Step 10: `docs/backend/Deploy.md` 작성**

아래 구성으로 쓴다(실제 ID·주소는 문서에 적지 않고 "GitHub 저장소 변수 참고"로 둔다):

```markdown
# 백엔드·프론트 배포 (`docs/backend/Deploy.md`)

> 작성일: <작성일> · 작성자: 진오 · 관련 이슈: #22

## 📌 목적
콘솔에서 클릭으로 만든 설정은 코드에 남지 않는다. 처음 한 번 하는 설정을 다시 할 수 있게, 문제가 생겼을 때 볼 곳을 바로 찾게 적어 둔다. 평소 배포는 `main` 머지 시 자동(CD)이다.

## 🧭 구성
(spec의 전체 구조 그림 + 리전 ap-northeast-2, 리소스 이름 표: EC2 `gridflow-backend`, 보안 그룹 `gridflow-backend-sg`, 역할 `gridflow-ec2`·`gridflow-github-deploy`, ECR `gridflow-backend`, 컨테이너 `gridflow`)

## 🔧 처음 한 번 하는 설정
### 1. 계정 (Step 1 내용)
### 2. EC2 역할 · 인스턴스 · 탄력적 IP (Step 2~3 내용, 왜 탄력적 IP인지 한 줄)
### 3. 서버 준비 (Step 4 명령)
### 4. 보안 그룹 (Step 6 — 8000은 CloudFront 관리형 접두사 목록만, 22번 없음)
### 5. CloudFront (Step 7 설정 표와 각 설정 이유)
### 6. Netlify (Step 8)
### 7. CD용 설정 — Task 13에서 추가

## ⚙️ 수동 배포·확인 명령
(Step 5·9 명령, 실측 스크립트)

## ⚠️ 문제 해결
- 브라우저 콘솔에 CORS 에러: ① `docker inspect gridflow`의 `ALLOWED_ORIGINS`에 Netlify 주소 정확히(끝 `/` 없이) ② CloudFront 오리진 요청 정책이 `AllViewerExceptHostHeader`인지(`Origin` 헤더 전달) ③ 허용 메서드에 OPTIONS 포함
- CloudFront 502/504: 컨테이너가 떠 있는지(`sudo docker ps`, `sudo docker logs --tail 100 gridflow`), 모델 로딩 중이면 1~2분 대기, 보안 그룹 8000 소스 확인
- Session Manager 접속이 안 됨: 인스턴스 역할에 `AmazonSSMManagedInstanceCore`가 붙었는지, 붙인 뒤 몇 분 대기
- 메모리 부족(컨테이너가 계속 재시작): `free -h`로 스왑 확인, `docker stats`

## 📊 실측 기록
(Step 9 결과: 메모리, 8장·20장 응답 시간, 측정일)
```

- [ ] **Step 11: 커밋 (승인 후)**

```bash
git add docs/backend/Deploy.md
git commit -m "docs(backend): EC2·CloudFront·Netlify 배포 절차와 실측 기록 (#22)"
```

---

### Task 13: CD 워크플로 + OIDC + Netlify 설정 파일

**Files:**
- Create: `.github/workflows/deploy-backend.yml`, `netlify.toml`
- Modify: `docs/backend/Deploy.md` (7절·되돌리기), `Backend/CLAUDE.md` (`## 범위`), `AGENTS.md` (Backend 요약)

**Interfaces:**
- Consumes: Task 12의 계정 ID·인스턴스 ID·CloudFront 주소·Netlify 주소
- Produces: GitHub 저장소 변수 `AWS_DEPLOY_ROLE_ARN`, `ECR_REPOSITORY`(= `gridflow-backend`), `EC2_INSTANCE_ID`, `ALLOWED_ORIGINS`, `BACKEND_HEALTH_URL`(= `https://<배포ID>.cloudfront.net/health`); 수동 실행 입력 `image_tag`

- [ ] **Step 1: ECR 저장소 (사용자)**

ECR → 프라이빗 저장소 생성 `gridflow-backend`(태그 변경 불가 끔) → 수명 주기 정책: 규칙 "이미지 개수 > 3이면 만료"(모든 태그).

- [ ] **Step 2: GitHub OIDC 공급자 + 배포 역할 (사용자)**

IAM → 자격 증명 공급자 → OpenID Connect, URL `https://token.actions.githubusercontent.com`, 대상 `sts.amazonaws.com`.
IAM → 역할 → 사용자 지정 신뢰 정책(`<ACCOUNT_ID>`는 실제 값):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com" },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:jinohpark371/GridFlow:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

인라인 권한 정책(`<INSTANCE_ID>`도 실제 값), 역할 이름 `gridflow-github-deploy`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": "ecr:GetAuthorizationToken", "Resource": "*" },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": "arn:aws:ecr:ap-northeast-2:<ACCOUNT_ID>:repository/gridflow-backend"
    },
    {
      "Effect": "Allow",
      "Action": "ssm:SendCommand",
      "Resource": [
        "arn:aws:ec2:ap-northeast-2:<ACCOUNT_ID>:instance/<INSTANCE_ID>",
        "arn:aws:ssm:ap-northeast-2::document/AWS-RunShellScript"
      ]
    },
    { "Effect": "Allow", "Action": ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations"], "Resource": "*" }
  ]
}
```

- [ ] **Step 3: GitHub 저장소 변수 (승인 후, 에이전트가 `gh`로)**

```bash
gh variable set AWS_DEPLOY_ROLE_ARN --body "arn:aws:iam::<ACCOUNT_ID>:role/gridflow-github-deploy"
gh variable set ECR_REPOSITORY --body "gridflow-backend"
gh variable set EC2_INSTANCE_ID --body "<INSTANCE_ID>"
gh variable set ALLOWED_ORIGINS --body "https://<사이트>.netlify.app"
gh variable set BACKEND_HEALTH_URL --body "https://<배포ID>.cloudfront.net/health"
gh variable list
```

비밀값이 아니라서(역할 ARN은 OIDC 신뢰 조건이 막아 줌) Secrets가 아닌 Variables를 쓴다.

- [ ] **Step 4: 배포 워크플로 작성**

`.github/workflows/deploy-backend.yml`:

```yaml
name: Deploy (backend)

on:
  push:
    branches: [main]
    paths:
      - "Ai/**"
      - "Backend/**"
      - "Dockerfile"
      - "requirements.txt"
      - ".github/workflows/deploy-backend.yml"
  workflow_dispatch:
    inputs:
      image_tag:
        description: "되돌릴 이미지 태그(커밋 해시). 비우면 현재 커밋으로 새로 빌드"
        required: false
        default: ""

permissions:
  id-token: write # OIDC 토큰 발급 요청
  contents: read

concurrency:
  group: deploy-backend
  cancel-in-progress: false

env:
  AWS_REGION: ap-northeast-2

jobs:
  test:
    if: inputs.image_tag == ''
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: sudo apt-get update && sudo apt-get install -y --no-install-recommends libgl1 libglib2.0-0
      - run: pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
      - run: python -m pytest -v

  deploy:
    needs: test
    if: always() && (needs.test.result == 'success' || needs.test.result == 'skipped')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}

      - id: ecr
        uses: aws-actions/amazon-ecr-login@v2

      - id: image
        run: |
          TAG="${{ inputs.image_tag }}"
          if [ -z "$TAG" ]; then TAG="${GITHUB_SHA::7}"; fi
          echo "tag=$TAG" >> "$GITHUB_OUTPUT"
          echo "uri=${{ steps.ecr.outputs.registry }}/${{ vars.ECR_REPOSITORY }}:$TAG" >> "$GITHUB_OUTPUT"

      - if: inputs.image_tag == ''
        uses: docker/setup-buildx-action@v3

      - if: inputs.image_tag == ''
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.image.outputs.uri }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: EC2 컨테이너 교체 (SSM Run Command)
        env:
          IMAGE: ${{ steps.image.outputs.uri }}
          REGISTRY: ${{ steps.ecr.outputs.registry }}
          ORIGINS: ${{ vars.ALLOWED_ORIGINS }}
          INSTANCE_ID: ${{ vars.EC2_INSTANCE_ID }}
        run: |
          COMMANDS=$(jq -n --arg image "$IMAGE" --arg registry "$REGISTRY" --arg origins "$ORIGINS" --arg region "$AWS_REGION" '{commands: [
            "set -e",
            "aws ecr get-login-password --region \($region) | docker login --username AWS --password-stdin \($registry)",
            "docker pull \($image)",
            "docker rm -f gridflow || true",
            "docker run -d --name gridflow --restart unless-stopped -p 8000:8000 -e ALLOWED_ORIGINS=\($origins) \($image)",
            "docker image prune -af"
          ]}')
          COMMAND_ID=$(aws ssm send-command --instance-ids "$INSTANCE_ID" --document-name AWS-RunShellScript \
            --comment "gridflow deploy ${GITHUB_SHA::7}" --parameters "$COMMANDS" --query Command.CommandId --output text)
          for i in $(seq 1 60); do
            STATUS=$(aws ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" --query Status --output text 2>/dev/null || echo Pending)
            echo "SSM 상태: $STATUS"
            case "$STATUS" in
              Success) exit 0 ;;
              Failed|Cancelled|TimedOut)
                aws ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" --query StandardErrorContent --output text
                exit 1 ;;
            esac
            sleep 10
          done
          echo "SSM 명령이 10분 안에 끝나지 않음"; exit 1

      - name: 헬스체크 (모델 로딩 약 1분, 최대 3분 대기)
        run: |
          for i in $(seq 1 18); do
            if curl -sf "${{ vars.BACKEND_HEALTH_URL }}"; then echo; echo "배포 완료: ${{ steps.image.outputs.tag }}"; exit 0; fi
            sleep 10
          done
          echo "헬스체크 실패"; exit 1
```

- [ ] **Step 5: Netlify 설정 파일**

저장소 루트 `netlify.toml`:

```toml
[build]
  base = "Frontend"
  command = "npm run build"
  publish = "out"
  # Frontend/ 밖만 바뀐 커밋이면 빌드를 건너뛴다(base 기준 경로)
  ignore = "git diff --quiet $CACHED_COMMIT_REF $COMMIT_REF -- . ../Ai/collect_unsplash_data.py ../Backend/main.py"

[build.environment]
  NODE_VERSION = "22"

[context.production.environment]
  NEXT_PUBLIC_API_BASE_URL = "https://<배포ID>.cloudfront.net"
```

`<배포ID>`는 Task 12에서 기록한 실제 값으로 넣는다(공개 주소라 커밋해도 됨). Netlify UI의 빌드 설정이 이 파일과 다르면 파일이 우선한다.

- [ ] **Step 6: 문법 확인**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-backend.yml', encoding='utf-8')); print('ok')"`
Expected: `ok`

- [ ] **Step 7: 문서 갱신**

`docs/backend/Deploy.md`의 `### 7. CD용 설정`을 Step 1~3 내용(ECR 수명 주기, OIDC 신뢰·권한 정책 JSON, 저장소 변수 표)으로 채우고, `## ⚙️` 절에 추가:

```markdown
### 자동 배포와 되돌리기
- `main`에 `Ai/`·`Backend/`·`Dockerfile`·`requirements.txt`가 바뀐 커밋이 들어오면 `Deploy (backend)`가 테스트 → 빌드 → ECR push(태그 = 커밋 해시 7자리) → SSM으로 컨테이너 교체 → 헬스체크
- 되돌리기: Actions → Deploy (backend) → Run workflow → `image_tag`에 이전 커밋 해시 7자리(ECR에 남아 있는 최근 3개 중) → 테스트·빌드 없이 그 이미지로 교체
- 교체 중 1~2분 끊김(모델 로딩)
- 프론트: Netlify가 `main`을 자동 배포. API 주소는 `netlify.toml`의 `NEXT_PUBLIC_API_BASE_URL`
```

`Backend/CLAUDE.md`의 `## 범위` 첫 항목을 다음으로 교체:

```markdown
- 배포: EC2(t3.small) + CloudFront, `main` 머지 시 GitHub Actions가 자동 배포 — 절차와 문제 해결은 [`docs/backend/Deploy.md`](../docs/backend/Deploy.md). IaC(Terraform)·커스텀 도메인·무중단 배포는 아직 범위 밖
```

`AGENTS.md` `## Backend 파트` 요약 줄의 `로컬 실행까지만(배포는 범위 밖)`을 `EC2 + CloudFront에 CD로 배포(docs/backend/Deploy.md)`로 교체. `## 프로젝트 구조`의 `docs/` 줄을 `` `docs/` — 파트별 설계 문서(`docs/ai/`, `docs/backend/`)와 설계·계획(`docs/superpowers/`)``로 교체.

- [ ] **Step 8: 커밋 (승인 후)**

```bash
git add .github/workflows/deploy-backend.yml netlify.toml docs/backend/Deploy.md Backend/CLAUDE.md AGENTS.md
git commit -m "ci: main 머지 시 ECR·SSM 백엔드 배포 워크플로 + Netlify 설정 (#22)"
```

---

### Task 14: 릴리스 + 운영 검증

**Files:**
- Modify: `docs/backend/Deploy.md` (`## 📊 실측 기록`)

**Interfaces:**
- Consumes: Task 1~13 전체

- [ ] **Step 1: PR → develop (승인 후)**

`/pr`로 `feature/프론트엔드-배포/22` → `develop` PR 생성. `gh pr checks`로 `CI (backend)`·`CI (frontend)`가 통과하는지 확인 후 사용자가 머지.

- [ ] **Step 2: 릴리스 PR → main (승인 후)**

`/pr`로 `develop` → `main` PR 생성, 사용자가 머지. 머지 직후 `gh run watch`로 `Deploy (backend)` 실행을 지켜보고, Netlify 배포 로그를 사용자에게 확인받는다.

- [ ] **Step 3: 수동 배포 흔적 정리 (사용자, Session Manager)**

```bash
sudo docker ps --format '{{.Image}}'   # ECR 이미지(…/gridflow-backend:<해시>)여야 함
sudo docker image rm gridflow-backend:manual || true
rm -rf ~/GridFlow
```

- [ ] **Step 4: 운영 확인**

- 휴대폰으로 `https://<사이트>.netlify.app` 접속 → 소개 모달 → 골든아워 → 사진 8장 → 결과 → 그리드 추가 → 상세 → 삭제
- 브라우저 개발자 도구(데스크톱)에서 `/arrange` 응답 헤더에 `access-control-allow-origin: https://<사이트>.netlify.app`
- `curl -s -m 5 http://<탄력적 IP>:8000/health` → 시간 초과(직접 접속 차단 유지)
- 되돌리기 연습: Actions → Deploy (backend) → Run workflow → 현재 태그 입력 → 성공

- [ ] **Step 5: 실기기 확인 (사용자)**

- 아이폰 사파리: HEIC 사진 선택이 되는지, 세로 사진이 눕지 않는지, 뒤로가기, 다크 모드, 시크릿 모드에서 소개 모달을 닫으면 다시 안 뜨는지
- 안드로이드 크롬: 갤러리 다중 선택, 뒤로가기

문제가 있으면 그 자리에서 멈추고 증상·원인 후보를 보고한다.

- [ ] **Step 6: 기록 + 이슈 정리 (승인 후)**

`docs/backend/Deploy.md` `## 📊 실측 기록`에 운영 응답 시간·메모리·실기기 결과를 추가하고 커밋(`docs(backend): 운영 배포 실측·실기기 확인 기록 (#22)`), `develop`으로 PR. #22 체크리스트를 갱신한다.
