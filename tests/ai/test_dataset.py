"""Ai/dataset.py 라벨 데이터 로딩 단위 테스트.

load_label_pairs는 JSON 파싱만 하므로 CLIP 없이 빠르게 실행됨
(build_feature_vector까지 엮은 검증은 tests/ai/test_dataset_integration.py 참고).
"""

import json

from dataset import DEFAULT_LABEL_PATH, load_label_pairs


def test_load_label_pairs_returns_theme_pos_neg_dicts(tmp_path):
    label_path = tmp_path / "pairs.json"
    label_path.write_text(
        json.dumps([{"theme": "테마", "pos": "samples/a.JPG", "neg": "samples/b.JPG"}]),
        encoding="utf-8",
    )

    pairs = load_label_pairs(label_path)

    assert pairs == [{"theme": "테마", "pos": "samples/a.JPG", "neg": "samples/b.JPG"}]


def test_default_label_path_points_to_valid_schema():
    """저장소에 커밋된 실제 라벨 파일(Ai/data/label_pairs.json)이 스키마를 지키는지 확인."""
    pairs = load_label_pairs(DEFAULT_LABEL_PATH)

    assert len(pairs) > 0
    for pair in pairs:
        assert pair.keys() == {"theme", "pos", "neg"}
