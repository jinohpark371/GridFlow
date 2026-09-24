"""Backend/main.py 헬스체크 + 앱 기동 테스트.

체크포인트가 실제로 로딩되는지 확인 — Ai/checkpoints/*.pt가 저장소에 커밋돼 있어
네트워크 없이 빠르게 실행됨. CLIP을 실제로 태우는 테스트(사진 업로드를 거치는
/arrange 관련)는 @pytest.mark.integration으로 분리한다(Ai/CLAUDE.md 컨벤션).
"""

from pathlib import Path

import pytest
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


@pytest.mark.integration
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


@pytest.mark.integration
def test_arrange_orders_photos_when_theme_matches(monkeypatch):
    """최종 리뷰에서 발견된 공백: 기존 happy-path 테스트는 threshold=0.35 때문에
    샘플 사진이 전부 걸러져서 groups가 항상 비었고, 실제 정렬 경로(arrange_photos,
    학습된 TransitionCostModel)가 한 번도 실행된 적이 없었다. THRESHOLD를 낮춰서
    사진이 남게 만들고, 실제로 정렬된 결과가 오는지 확인한다."""
    import main

    monkeypatch.setattr(main, "THRESHOLD", -1e9)

    with TestClient(main.app) as client:
        response = client.post(
            "/arrange",
            data={"theme": "black and white monochrome photography", "group_ids": [0, 0, 1]},
            files=[
                ("photos", _sample_file("photo1.JPG")),
                ("photos", _sample_file("photo2.JPG")),
                ("photos", _sample_file("photo10.JPG")),
            ],
        )

    assert response.status_code == 200
    body = response.json()
    assert body["removed_candidates"] == []
    assert len(body["groups"]) == 2
    all_ordered_ids = {pid for group in body["groups"] for pid in group["order"]}
    assert all_ordered_ids == {"photo1.JPG", "photo2.JPG", "photo10.JPG"}
    for group in body["groups"]:
        assert len(group["adjacency_costs"]) == len(group["order"]) - 1


@pytest.mark.integration
def test_arrange_excludes_groups_fully_filtered_out(monkeypatch):
    """Review Focus: 필터링으로 그룹이 통째로 비면 결과에서 조용히 빠지는 경로를
    (수동 curl 확인이 아니라) 테스트로 고정한다."""
    import main

    monkeypatch.setattr(main, "THRESHOLD", 1e9)

    with TestClient(main.app) as client:
        response = client.post(
            "/arrange",
            data={"theme": "black and white monochrome photography", "group_ids": [0, 0]},
            files=[
                ("photos", _sample_file("photo1.JPG")),
                ("photos", _sample_file("photo2.JPG")),
            ],
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["removed_candidates"]) == 2
    assert body["groups"] == []


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
