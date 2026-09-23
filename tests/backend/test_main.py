"""Backend/main.py 헬스체크 + 앱 기동 테스트.

체크포인트가 실제로 로딩되는지 확인 — Ai/checkpoints/*.pt가 저장소에 커밋돼 있어
네트워크 없이 빠르게 실행됨.
"""

from pathlib import Path

from fastapi.testclient import TestClient

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"


def test_health_check_returns_ok():
    from main import app

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _sample_file(name: str) -> tuple[str, bytes, str]:
    path = SAMPLES_DIR / name
    return (name, path.read_bytes(), "image/jpeg")


def test_arrange_returns_groups_and_removed_candidates():
    from main import app

    with TestClient(app) as client:
        response = client.post(
            "/arrange",
            data={"theme": "미니멀한 감성 사진", "group_ids": [0, 0, 1]},
            files=[
                ("photos", _sample_file("photo1.JPG")),
                ("photos", _sample_file("photo2.JPG")),
                ("photos", _sample_file("photo10.JPG")),
            ],
        )

    assert response.status_code == 200
    body = response.json()
    assert "removed_candidates" in body
    assert "skipped" in body
    assert len(body["groups"]) <= 2  # 필터링으로 그룹이 통째로 비면 결과에서 빠질 수 있음
    for group in body["groups"]:
        assert len(group["adjacency_costs"]) == len(group["order"]) - 1


def test_arrange_rejects_mismatched_lengths():
    from main import app

    with TestClient(app) as client:
        response = client.post(
            "/arrange",
            data={"theme": "테마", "group_ids": [0]},
            files=[
                ("photos", _sample_file("photo1.JPG")),
                ("photos", _sample_file("photo2.JPG")),
            ],
        )

    assert response.status_code == 400


def test_arrange_rejects_empty_photos():
    from main import app

    with TestClient(app) as client:
        response = client.post("/arrange", data={"theme": "테마", "group_ids": []}, files=[])

    assert response.status_code == 400


def test_arrange_rejects_duplicate_filenames():
    """Review Focus: 같은 파일명이 두 번 업로드되면 어느 사진인지 알 수 없어 거부해야 한다."""
    from main import app

    with TestClient(app) as client:
        response = client.post(
            "/arrange",
            data={"theme": "테마", "group_ids": [0, 0]},
            files=[
                ("photos", _sample_file("photo1.JPG")),
                ("photos", ("photo1.JPG", (SAMPLES_DIR / "photo2.JPG").read_bytes(), "image/jpeg")),
            ],
        )

    assert response.status_code == 400
