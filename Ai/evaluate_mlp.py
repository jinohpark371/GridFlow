"""학습된 ScoringMLP의 validation ranking accuracy 확인 + loss curve/점수 분포 시각화.

흐름: Ai/data/label_pairs.json -> dataset.load_label_pairs -> split_pairs로 train(9)/val(3) 고정 분할
      -> train_mlp.train(train)으로 학습 -> val에 대해 ranking accuracy 측정
      -> loss curve, val 점수 분포를 docs/ai/output/에 PNG로 저장
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch

from dataset import build_pair_features, load_label_pairs
from mlp import ScoringMLP, inference_scores
from train_mlp import train

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "docs" / "ai" / "output"
N_VAL = 3


def split_pairs(pairs: list[dict], n_val: int = N_VAL) -> tuple[list[dict], list[dict]]:
    """라벨 쌍을 앞쪽 train / 뒤쪽 val로 고정 분할 (데이터가 12쌍뿐이라 랜덤 분할 대신 고정)."""
    return pairs[:-n_val], pairs[-n_val:]


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
