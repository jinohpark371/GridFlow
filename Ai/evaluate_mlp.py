"""학습된 ScoringMLP의 validation ranking accuracy 확인 + loss curve/점수 분포 시각화.

흐름: Ai/data/unsplash/scoring_pairs.csv(테마 하나 고정) -> dataset.load_label_pairs
      -> split_pairs로 테마별 train/val 고정 분할 -> train_mlp.train(train)으로 학습
      -> val에 대해 ranking accuracy 측정
      -> loss curve, val 점수 분포를 docs/ai/output/에 PNG로 저장
      -> 학습된 가중치를 Ai/checkpoints/scoring_mlp.pt로 저장
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch

from dataset import build_pair_features, load_label_pairs
from mlp import CHECKPOINT_PATH, ScoringMLP, inference_scores, save_checkpoint
from train_mlp import train

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "docs" / "ai" / "output"
N_VAL_PER_THEME = 3


def split_pairs(pairs: list[dict], n_val_per_theme: int = N_VAL_PER_THEME) -> tuple[list[dict], list[dict]]:
    """테마별로 뒤쪽 n_val_per_theme개를 val, 나머지를 train으로 고정 분할.

    pairs.csv가 테마별로 연속해서 묶여 있어(테마당 15행), 앞/뒤 단순 분할을 하면
    val이 마지막 테마 하나에만 쏠린다 — 테마마다 나눠야 val이 모든 테마를 대표한다.
    """
    train_pairs, val_pairs = [], []
    by_theme: dict[str, list[dict]] = {}
    for pair in pairs:
        by_theme.setdefault(pair["theme"], []).append(pair)
    for theme_pairs in by_theme.values():
        train_pairs.extend(theme_pairs[:-n_val_per_theme])
        val_pairs.extend(theme_pairs[-n_val_per_theme:])
    return train_pairs, val_pairs


def ranking_accuracy(model: ScoringMLP, feats_pos: torch.Tensor, feats_neg: torch.Tensor) -> float:
    """val 쌍에서 score_pos > score_neg인 비율 (eval 모드로 결정적으로 계산)."""
    scores_pos = inference_scores(model, feats_pos)
    scores_neg = inference_scores(model, feats_neg)
    return (scores_pos > scores_neg).float().mean().item()


def plot_loss_curve(loss_history: list[float], path: Path) -> None:
    """epoch별 loss를 선 그래프로 저장 — 학습이 실제로 수렴하는지 시각 확인."""
    plt.figure()
    plt.plot(loss_history)
    plt.xlabel("epoch")
    plt.ylabel("margin ranking loss")
    plt.title("train loss curve")
    plt.savefig(path)
    plt.close()


def plot_score_distribution(scores_pos: torch.Tensor, scores_neg: torch.Tensor, path: Path) -> None:
    """val 쌍의 pos/neg 점수를 산점도로 저장 — 두 그룹이 얼마나 분리되는지 시각 확인."""
    plt.figure()
    plt.scatter(range(len(scores_pos)), scores_pos.tolist(), label="pos", marker="o")
    plt.scatter(range(len(scores_neg)), scores_neg.tolist(), label="neg", marker="x")
    plt.xlabel("val pair index")
    plt.ylabel("score")
    plt.title("val pos/neg score distribution")
    plt.legend()
    plt.savefig(path)
    plt.close()


if __name__ == "__main__":
    pairs = load_label_pairs()
    train_pairs, val_pairs = split_pairs(pairs)

    feats_pos_train, feats_neg_train = build_pair_features(train_pairs)
    feats_pos_val, feats_neg_val = build_pair_features(val_pairs)

    model, loss_history = train(feats_pos_train, feats_neg_train)

    acc = ranking_accuracy(model, feats_pos_val, feats_neg_val)
    print(f"train {len(train_pairs)}쌍 / val {len(val_pairs)}쌍")
    print(f"val ranking accuracy: {acc:.2%}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_loss_curve(loss_history, OUTPUT_DIR / "loss_curve.png")

    scores_pos_val = inference_scores(model, feats_pos_val)
    scores_neg_val = inference_scores(model, feats_neg_val)
    plot_score_distribution(scores_pos_val, scores_neg_val, OUTPUT_DIR / "score_distribution.png")

    print(f"저장: {OUTPUT_DIR / 'loss_curve.png'}")
    print(f"저장: {OUTPUT_DIR / 'score_distribution.png'}")

    save_checkpoint(model)
    print(f"체크포인트 저장: {CHECKPOINT_PATH}")
