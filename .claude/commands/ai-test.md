---
description: Ai/ 변경사항에 대한 pytest 테스트 코드를 작성한다
allowed-tools: Bash(git status), Bash(git diff *), Bash(git log *), Bash(python -m pytest *), Bash(pip install *), Read, Write, Edit, Glob, Grep
---

# Ai 테스트 코드 작성

`Ai/` 폴더의 변경사항을 확인하고, 대응하는 `tests/` 테스트 코드를 작성한다. 이 커맨드의 핵심은 **테스트 코드를 실제로 작성하는 것**이며, 아래 구조/템플릿을 그대로 따른다.

---

## Phase 1: 범위 파악

1. `git status` / `git diff HEAD -- Ai/`로 변경·추가된 `Ai/` 모듈 확인
2. `Ai/<module>.py`에 대응하는 `tests/ai/test_<module>.py`가 있는지 확인 — 없으면 새로 작성, 있으면 바뀐 함수 위주로 보강
3. `pytest`가 `requirements.txt`에 없으면 `pip install pytest` 후 실제 설치된 버전으로 추가
4. `Ai/` 밖의 변경이 섞여 있으면 이 커맨드 범위 밖이므로 사용자에게 분리 여부를 확인

---

## Phase 2: 테스트 코드 작성 (핵심)

### 1) 기반 파일 — 없으면 그대로 생성

**`pytest.ini`** (루트)

```ini
[pytest]
testpaths = tests
markers =
    integration: 실제 CLIP 모델 다운로드·네트워크가 필요한 느린 테스트. 기본 `pytest` 실행에서는 제외되며, `pytest -m integration`으로 명시 실행.
addopts = -m "not integration"
```

**`tests/conftest.py`**

```python
"""테스트에서 Ai/ 안의 스크립트 스타일 모듈을 python clip.py로 직접 실행할 때와
동일한 방식(import clip / import features / import mlp)으로 불러올 수 있게
Ai/ 디렉터리를 sys.path에 추가한다.

Ai/는 패키지(__init__.py)가 아니고, 모듈끼리도 `from clip import ...`처럼
같은 디렉터리 기준 bare import를 쓰고 있어(Ai/mlp.py 참고), 테스트도 동일한
임포트 방식을 유지해야 소스 코드를 건드리지 않고 그대로 재사용할 수 있다.
"""

import sys
from pathlib import Path

AI_DIR = Path(__file__).resolve().parent.parent / "Ai"
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))
```

### 2) 모듈별 테스트 파일 — `tests/ai/test_<module>.py`

- `Ai/<module>.py` 하나당 테스트 파일 하나
- 상단 docstring 한 줄로 무엇을 검증하는지, CLIP 모델 로딩이 필요한지 여부를 밝힌다
- 임포트는 conftest.py 덕분에 bare import로: `from features import ...`, `from mlp import ...`
- 로컬 샘플 이미지가 필요하면 `samples/`를 절대경로로 참조:

```python
from pathlib import Path

SAMPLE_PHOTO = Path(__file__).resolve().parents[2] / "samples" / "photo1.JPG"
```

**검증 우선순위** (전부 채우려 하지 말고 해당하는 것만):

1. **shape/타입** — 선언된 차원 상수와 실제 출력이 일치하는가
2. **값의 범위/정규화** — 0~1, -1~1처럼 스펙에 명시된 범위를 벗어나지 않는가
3. **결정성** — 같은 입력을 두 번 넣었을 때 같은 출력이 나오는가 (특히 `model.eval()` 누락 등으로 Dropout이 추론에 남는 버그는 이 항목으로 잡힌다)
4. **손실/수식 함수** — 알려진 입력에 대해 부호·대소 관계가 수식대로 나오는가 (예: margin 만족 시 loss=0, 순서 반대면 loss 증가)
5. **분기 로직** — threshold 등으로 나뉘는 두 그룹이 서로 겹치지 않고 전체를 덮는가

**버그를 고치는 김에 테스트를 쓰는 경우**: 어떤 조건에서 어떤 증상이 있었는지 docstring에 남기고, 그 조건을 그대로 재현하는 회귀 테스트를 추가한다.

### 3) 무거운 의존성(CLIP 모델 등) 분리

CLIP처럼 다운로드·네트워크가 필요한 모듈은 별도 파일로 분리하고 `pytest.mark.integration`을 붙인다:

```python
"""Ai/clip.py 통합 테스트. 실제 모델 다운로드·네트워크 필요, 느림.
기본 pytest 실행에서 제외됨 — 명시 실행: pytest -m integration
"""

import pytest

pytestmark = pytest.mark.integration
```

순수 로직(피처 추출, MLP forward/loss 등)은 랜덤 텐서나 로컬 샘플 이미지만으로 검증해 모델 로딩 없이 빠르게 돌아가야 한다 — 이런 테스트는 `integration` 마커를 붙이지 않는다.

### 4) 원칙

- 코드를 읽으면 자명한 내용까지 억지로 테스트하지 않는다. 실제로 깨질 수 있는 지점(위 "검증 우선순위")을 우선한다
- 테스트 하나는 한 가지만 검증한다 — 실패 시 원인이 바로 드러나야 함
- 함수명은 `test_<검증 대상>_<기대 결과>` 형태로, 실행 결과 목록만 봐도 무엇이 깨졌는지 알 수 있게 짓는다

---

## Phase 3: 실행 및 보고

1. `python -m pytest -v` (빠른 테스트만, integration 제외)
2. 필요 시 `python -m pytest -v -m integration` (느릴 수 있음을 미리 안내)
3. 실패하면 테스트 자체의 오류인지 `Ai/` 코드의 실제 버그인지 구분해서 보고 — 코드 버그면 임의로 고치지 않고 먼저 사용자에게 알린다
4. 통과/실패 요약과 새로 작성/수정한 테스트 파일 목록을 보고

---

## 주의사항

- 사용자가 명시적으로 요청하지 않는 한 커밋을 임의로 실행하지 않는다 — 필요하면 `/ai-commit`으로 별도 진행 (`type: test`)
- `Ai/` 코드 자체의 버그를 테스트 중 발견해도 수정은 이 커맨드 범위 밖 — 발견 사실만 보고. 수정까지 요청받았다면 그 수정에 대한 회귀 테스트를 함께 추가한다
