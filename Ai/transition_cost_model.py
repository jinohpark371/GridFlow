"""사진 두 장의 피처 차이 -> 학습 가능한 전이 비용 (흐름도 > 전이 비용 배치 설계, 2단계).

흐름: 사진 A/B의 11차원 피처(build_feature_vector) -> |A - B| 차이 벡터 -> TransitionCostModel
      -> 비용 점수 하나 (낮을수록 나란히 놓기 자연스러움)

mlp.py의 ScoringMLP(사진 한 장 -> 테마 적합도 점수, 절대 점수형)와는 다른 문제라 재사용하지
않고 별도로 둔다 — 이건 사진 두 장을 동시에 보고 "이 둘이 어울리는가"를 직접 비교하는
페어와이즈 모델인 반면, ScoringMLP는 사진 하나를 고정된 테마 기준으로 독립 평가한다.
"""

from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn

from mlp import INPUT_DIM, margin_ranking_loss

DEFAULT_EPOCHS = 100
DEFAULT_LR = 1e-3
CHECKPOINT_PATH = Path(__file__).parent / "checkpoints" / "transition_cost_model.pt"


class TransitionCostModel(nn.Module):
    """피처 차이 벡터(11d) -> 전이 비용 점수 하나 (낮을수록 두 사진이 자연스럽게 어울림)."""

    def __init__(self, input_dim: int = INPUT_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )

    def forward(self, diff: torch.Tensor) -> torch.Tensor:
        return self.net(diff)  # (batch, 1)


def pair_cost(model: TransitionCostModel, feat_a: torch.Tensor, feat_b: torch.Tensor) -> torch.Tensor:
    """사진 두 장의 피처 -> |차이| -> 전이 비용. A/B 순서를 바꿔도 값이 같다(대칭)."""
    diff = torch.abs(feat_a - feat_b)
    return model(diff).squeeze(-1)


def train(
    feat_pos_a: torch.Tensor,
    feat_pos_b: torch.Tensor,
    feat_neg_a: torch.Tensor,
    feat_neg_b: torch.Tensor,
    epochs: int = DEFAULT_EPOCHS,
    lr: float = DEFAULT_LR,
) -> tuple[TransitionCostModel, list[float]]:
    """pos_pair(같은 테마, 비용 낮아야 함) vs neg_pair(다른 테마, 비용 높아야 함)로 풀배치 학습.

    비용이 낮을수록 좋으므로 -cost를 "점수"로 삼아 mlp.margin_ranking_loss를 그대로 재사용한다
    (score_pos > score_neg를 요구하는 기존 함수와 동일한 형태로 맞춤).
    """
    model = TransitionCostModel()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    loss_history = []
    for _ in range(epochs):
        optimizer.zero_grad()
        cost_pos = pair_cost(model, feat_pos_a, feat_pos_b)
        cost_neg = pair_cost(model, feat_neg_a, feat_neg_b)
        loss = margin_ranking_loss(-cost_pos, -cost_neg)
        loss.backward()
        optimizer.step()
        loss_history.append(loss.item())

    return model, loss_history


def save_checkpoint(model: TransitionCostModel, path: Path = CHECKPOINT_PATH) -> None:
    """학습된 모델 가중치를 저장 — 이후 세션/백엔드에서 재학습 없이 불러다 쓰기 위함."""
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), path)


def load_checkpoint(path: Path = CHECKPOINT_PATH) -> TransitionCostModel:
    """저장된 가중치를 불러와 eval 모드(Dropout 끔) TransitionCostModel로 복원."""
    model = TransitionCostModel()
    model.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
    model.eval()
    return model


if __name__ == "__main__":
    import random

    from dataset import load_photo_pool, sample_theme_pair_features

    features, by_theme = load_photo_pool()
    feat_pos_a, feat_pos_b, feat_neg_a, feat_neg_b = sample_theme_pair_features(
        features, by_theme, n_pairs=45, rng=random.Random(42)
    )

    model, loss_history = train(feat_pos_a, feat_pos_b, feat_neg_a, feat_neg_b)
    print(f"trained on {len(feat_pos_a)} pos/neg pairs for {DEFAULT_EPOCHS} epochs")
    print(f"loss: {loss_history[0]:.4f} -> {loss_history[-1]:.4f}")
