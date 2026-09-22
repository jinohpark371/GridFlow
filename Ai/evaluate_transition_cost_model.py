"""학습된 TransitionCostModel의 validation cost ranking accuracy 확인 + loss curve/비용 분포 시각화.

흐름: Ai/data/unsplash/photos.csv -> dataset.load_photo_pool -> sample_theme_pair_features로
      train/val 쌍 각각 샘플링 -> transition_cost_model.train(train)으로 학습
      -> val에 대해 "cost(pos_pair) < cost(neg_pair)" 비율 측정
      -> loss curve, val 비용 분포를 docs/ai/output/에 PNG로 저장
      -> 학습된 가중치를 Ai/checkpoints/transition_cost_model.pt로 저장
"""

from __future__ import annotations

import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch

from dataset import load_photo_pool, sample_theme_pair_features
from transition_cost_model import CHECKPOINT_PATH, TransitionCostModel, pair_cost, save_checkpoint, train

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "docs" / "ai" / "output"
N_TRAIN_PAIRS = 60
N_VAL_PAIRS = 15
SEED = 42


def cost_ranking_accuracy(
    model: TransitionCostModel,
    feat_pos_a: torch.Tensor,
    feat_pos_b: torch.Tensor,
    feat_neg_a: torch.Tensor,
    feat_neg_b: torch.Tensor,
) -> float:
    """val 쌍에서 cost(pos_pair) < cost(neg_pair)인 비율 (eval 모드로 결정적으로 계산)."""
    was_training = model.training
    model.eval()
    with torch.no_grad():
        cost_pos = pair_cost(model, feat_pos_a, feat_pos_b)
        cost_neg = pair_cost(model, feat_neg_a, feat_neg_b)
    model.train(was_training)
    return (cost_pos < cost_neg).float().mean().item()


def plot_loss_curve(loss_history: list[float], path: Path) -> None:
    """epoch별 loss를 선 그래프로 저장 — 학습이 실제로 수렴하는지 시각 확인."""
    plt.figure()
    plt.plot(loss_history)
    plt.xlabel("epoch")
    plt.ylabel("margin ranking loss")
    plt.title("transition cost model train loss curve")
    plt.savefig(path)
    plt.close()


def plot_cost_distribution(cost_pos: torch.Tensor, cost_neg: torch.Tensor, path: Path) -> None:
    """val pos_pair/neg_pair 비용을 산점도로 저장 — 두 그룹이 얼마나 분리되는지 시각 확인."""
    plt.figure()
    plt.scatter(range(len(cost_pos)), cost_pos.tolist(), label="pos_pair (same theme)", marker="o")
    plt.scatter(range(len(cost_neg)), cost_neg.tolist(), label="neg_pair (diff theme)", marker="x")
    plt.xlabel("val pair index")
    plt.ylabel("cost")
    plt.title("val pos/neg pair cost distribution")
    plt.legend()
    plt.savefig(path)
    plt.close()


if __name__ == "__main__":
    features, by_theme = load_photo_pool()
    rng = random.Random(SEED)

    train_pos_a, train_pos_b, train_neg_a, train_neg_b = sample_theme_pair_features(
        features, by_theme, N_TRAIN_PAIRS, rng
    )
    val_pos_a, val_pos_b, val_neg_a, val_neg_b = sample_theme_pair_features(features, by_theme, N_VAL_PAIRS, rng)

    model, loss_history = train(train_pos_a, train_pos_b, train_neg_a, train_neg_b)

    acc = cost_ranking_accuracy(model, val_pos_a, val_pos_b, val_neg_a, val_neg_b)
    print(f"train {N_TRAIN_PAIRS}쌍 / val {N_VAL_PAIRS}쌍")
    print(f"val cost ranking accuracy: {acc:.2%}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_loss_curve(loss_history, OUTPUT_DIR / "transition_loss_curve.png")

    was_training = model.training
    model.eval()
    with torch.no_grad():
        cost_pos_val = pair_cost(model, val_pos_a, val_pos_b)
        cost_neg_val = pair_cost(model, val_neg_a, val_neg_b)
    model.train(was_training)
    plot_cost_distribution(cost_pos_val, cost_neg_val, OUTPUT_DIR / "transition_cost_distribution.png")

    print(f"저장: {OUTPUT_DIR / 'transition_loss_curve.png'}")
    print(f"저장: {OUTPUT_DIR / 'transition_cost_distribution.png'}")

    save_checkpoint(model)
    print(f"체크포인트 저장: {CHECKPOINT_PATH}")
