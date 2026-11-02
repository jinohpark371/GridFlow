"""테마별 ScoringMLP 학습 + 검증 + 기준값 결정 + 결과 시각화.

흐름: photos.csv(사진 90장, 색감 10d) + cross_clip_sim.csv(사진 x 테마 문장 clip_sim)
      -> dataset.split_photos로 테마별 학습 24장 / 검증 6장 고정 분할
      -> 테마마다: 이 테마 학습 사진 x 다른 테마 학습 사진 쌍으로 train_mlp.train
         -> 검증 사진 18장으로 ranking accuracy + 기준값(best_threshold) + 기준값 정확도
      -> Ai/checkpoints/scoring_mlp_<테마 키>.pt, scoring_thresholds.json 저장
      -> loss curve, 검증 점수 분포를 docs/ai/output/에 테마별 PNG로, 세 테마 요약을 theme_summary.png로 저장
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

from dataset import (
    build_theme_labeled,
    build_theme_pairs,
    load_cross_clip_sim,
    load_photo_pool,
    split_photos,
)
from mlp import CHECKPOINT_DIR, THEME_KEYS, ScoringMLP, inference_scores, save_checkpoint, save_thresholds, theme_checkpoint_path
from train_mlp import DEFAULT_EPOCHS, train

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "docs" / "ai" / "output"


def ranking_accuracy(model: ScoringMLP, feats_pos: torch.Tensor, feats_neg: torch.Tensor) -> float:
    """쌍마다 score_pos > score_neg인 비율 (eval 모드로 결정적으로 계산)."""
    scores_pos = inference_scores(model, feats_pos)
    scores_neg = inference_scores(model, feats_neg)
    return (scores_pos > scores_neg).float().mean().item()


def threshold_accuracy(scores: torch.Tensor, labels: torch.Tensor, threshold: float) -> float:
    """점수가 기준값 이상이면 '이 테마 사진'으로 판정했을 때 정답 비율."""
    predicted = (scores >= threshold).long()
    return (predicted == labels).float().mean().item()


def best_threshold(scores: torch.Tensor, labels: torch.Tensor) -> float:
    """검증 점수 -> 테마 사진과 나머지를 가장 많이 맞게 가르는 기준값.

    후보는 정렬된 점수 사이의 가운데 값들. 정확도가 같은 후보가 여럿이면 양옆 점수 간격이
    가장 넓은 곳을 고른다 — 새 사진의 점수가 조금 흔들려도 판정이 덜 뒤집히게.
    """
    sorted_scores = torch.sort(scores).values.tolist()
    best, best_key = sorted_scores[0], (-1.0, -1.0)
    for low, high in zip(sorted_scores, sorted_scores[1:]):
        candidate = (low + high) / 2
        key = (threshold_accuracy(scores, labels, candidate), high - low)
        if key > best_key:
            best, best_key = candidate, key
    return best


def evaluate_theme(
    theme_text: str,
    train_by_theme: dict[str, list[str]],
    val_by_theme: dict[str, list[str]],
    features: dict[str, np.ndarray],
    cross: dict[str, dict[str, float]],
    epochs: int = DEFAULT_EPOCHS,
) -> dict:
    """테마 하나: 학습 사진 쌍으로 학습 -> 검증 사진으로 순위 정확도·기준값·기준값 정확도."""
    feats_pos, feats_neg = build_theme_pairs(theme_text, train_by_theme, features, cross)
    model, loss_history = train(feats_pos, feats_neg, epochs=epochs)

    val_pos, val_neg = build_theme_pairs(theme_text, val_by_theme, features, cross)
    val_feats, val_labels = build_theme_labeled(theme_text, val_by_theme, features, cross)
    val_scores = inference_scores(model, val_feats)
    threshold = best_threshold(val_scores, val_labels)

    return {
        "model": model,
        "loss_history": loss_history,
        "n_train_pairs": len(feats_pos),
        "ranking_accuracy": ranking_accuracy(model, val_pos, val_neg),
        "val_scores": val_scores,
        "val_labels": val_labels,
        "threshold": threshold,
        "threshold_accuracy": threshold_accuracy(val_scores, val_labels, threshold),
    }


def val_pass_counts(
    model: ScoringMLP,
    theme_text: str,
    threshold: float,
    val_by_theme: dict[str, list[str]],
    features: dict[str, np.ndarray],
    cross: dict[str, dict[str, float]],
) -> dict[str, tuple[int, int]]:
    """이 테마 모델·기준값으로 검증 사진을 수집 테마별로 나눠 (통과 수, 전체 수) — 자기 테마만 통과해야 정상."""
    counts = {}
    for photo_theme, ids in val_by_theme.items():
        feats, _ = build_theme_labeled(theme_text, {photo_theme: ids}, features, cross)
        passed = int((inference_scores(model, feats) >= threshold).sum().item())
        counts[photo_theme] = (passed, len(ids))
    return counts


def plot_theme_summary(summaries: dict[str, dict], path: Path) -> None:
    """테마별 결과 한 장 요약: loss curve(겹쳐 그림) / 검증 정확도 막대 / 모델 x 사진 테마 통과율 표.

    재학습할 때마다 같은 형식으로 덮어써서, 이전 결과와 나란히 놓고 진행 상황을 비교하기 위함.
    """
    keys = list(summaries)
    fig, (ax_loss, ax_acc, ax_pass) = plt.subplots(1, 3, figsize=(16, 4.8))

    for key in keys:
        ax_loss.plot(summaries[key]["loss_history"], label=key)
    ax_loss.set_xlabel("epoch")
    ax_loss.set_ylabel("margin ranking loss")
    ax_loss.set_title("train loss")
    ax_loss.legend()

    x = np.arange(len(keys))
    for offset, metric, label in ((-0.2, "ranking_accuracy", "ranking"), (0.2, "threshold_accuracy", "threshold")):
        values = [summaries[key][metric] for key in keys]
        bars = ax_acc.bar(x + offset, values, width=0.4, label=label)
        ax_acc.bar_label(bars, labels=[f"{v:.0%}" for v in values], fontsize=8)
    ax_acc.set_xticks(x, keys)
    ax_acc.set_ylim(0, 1.1)
    ax_acc.set_ylabel("accuracy")
    ax_acc.set_title("val accuracy (unseen photos)")
    ax_acc.legend(loc="lower right")

    photo_themes = list(next(iter(summaries.values()))["pass_counts"])
    rates = np.array([[p / n for p, n in (summaries[k]["pass_counts"][t] for t in photo_themes)] for k in keys])
    ax_pass.imshow(rates, cmap="Greens", vmin=0, vmax=1)
    for i, key in enumerate(keys):
        for j, theme in enumerate(photo_themes):
            passed, total = summaries[key]["pass_counts"][theme]
            ax_pass.text(j, i, f"{passed}/{total}", ha="center", va="center", color="white" if rates[i, j] > 0.5 else "black")
    ax_pass.set_xticks(range(len(photo_themes)), [THEME_KEYS.get(t, t) for t in photo_themes])
    ax_pass.set_yticks(range(len(keys)), [f"{k} model" for k in keys])
    ax_pass.set_xlabel("val photos (collected theme)")
    ax_pass.set_title("passed threshold (diagonal = correct)")

    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def plot_loss_curve(loss_history: list[float], path: Path) -> None:
    """epoch별 loss를 선 그래프로 저장 — 학습이 실제로 수렴하는지 시각 확인."""
    plt.figure()
    plt.plot(loss_history)
    plt.xlabel("epoch")
    plt.ylabel("margin ranking loss")
    plt.title("train loss curve")
    plt.savefig(path)
    plt.close()


def plot_score_distribution(
    scores_theme: torch.Tensor, scores_other: torch.Tensor, path: Path, threshold: float
) -> None:
    """검증 사진의 점수를 테마 사진/나머지로 나눠 찍고 기준값 선을 그어 저장 — 얼마나 갈리는지 시각 확인."""
    plt.figure()
    plt.scatter(range(len(scores_theme)), scores_theme.tolist(), label="theme photos", marker="o")
    plt.scatter(range(len(scores_other)), scores_other.tolist(), label="other photos", marker="x")
    plt.axhline(threshold, color="gray", linestyle="--", label=f"threshold {threshold:.3f}")
    plt.xlabel("val photo index")
    plt.ylabel("score")
    plt.title("val score distribution")
    plt.legend()
    plt.savefig(path)
    plt.close()


TRAIN_SEED = 0


if __name__ == "__main__":
    torch.manual_seed(TRAIN_SEED)  # 재실행해도 같은 체크포인트·그래프가 나오게
    features, by_theme = load_photo_pool()
    cross = load_cross_clip_sim()
    train_by_theme, val_by_theme = split_photos(by_theme)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    thresholds, summaries = {}, {}
    for theme_text, key in THEME_KEYS.items():
        result = evaluate_theme(theme_text, train_by_theme, val_by_theme, features, cross)
        print(
            f"[{key}] 학습 {result['n_train_pairs']}쌍 / 검증 {len(result['val_labels'])}장 | "
            f"loss {result['loss_history'][0]:.4f} -> {result['loss_history'][-1]:.4f} | "
            f"순위 정확도 {result['ranking_accuracy']:.1%} | "
            f"기준값 {result['threshold']:.3f}, 정확도 {result['threshold_accuracy']:.1%}"
        )

        is_theme = result["val_labels"] == 1
        plot_loss_curve(result["loss_history"], OUTPUT_DIR / f"loss_curve_{key}.png")
        plot_score_distribution(
            result["val_scores"][is_theme],
            result["val_scores"][~is_theme],
            OUTPUT_DIR / f"score_distribution_{key}.png",
            result["threshold"],
        )
        save_checkpoint(result["model"], theme_checkpoint_path(theme_text))
        thresholds[key] = result["threshold"]
        result["pass_counts"] = val_pass_counts(
            result["model"], theme_text, result["threshold"], val_by_theme, features, cross
        )
        summaries[key] = result

    save_thresholds(thresholds)
    plot_theme_summary(summaries, OUTPUT_DIR / "theme_summary.png")
    print(f"체크포인트·기준값 저장: {CHECKPOINT_DIR}")
    print(f"그래프 저장: {OUTPUT_DIR}")
