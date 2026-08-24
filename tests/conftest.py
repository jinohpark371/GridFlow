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
