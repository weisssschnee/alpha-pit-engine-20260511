from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

import torch
from torch import nn


@dataclass(slots=True)
class LoRDStepReport:
    target_parameter_names: list[str]
    stable_rank_before: dict[str, float]
    stable_rank_after: dict[str, float]
    optimizer_step_completed_before_lord: bool
    finite_stable_rank: bool
    elapsed_ms: float


class TinyLoopedAttentionBlock(nn.Module):
    """Minimal q/k projection block so LoRD targets real attention matrices."""

    def __init__(self, d_model: int) -> None:
        super().__init__()
        self.q_proj = nn.Linear(d_model, d_model, bias=False)
        self.k_proj = nn.Linear(d_model, d_model, bias=False)
        self.v_proj = nn.Linear(d_model, d_model, bias=False)
        self.out_proj = nn.Linear(d_model, d_model, bias=False)
        self.norm = nn.LayerNorm(d_model)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        q = self.q_proj(inputs)
        k = self.k_proj(inputs)
        v = self.v_proj(inputs)
        attn = torch.softmax((q @ k.transpose(-2, -1)) / math.sqrt(q.shape[-1]), dim=-1)
        return self.norm(inputs + self.out_proj(attn @ v))


class Phase2PolicyNetwork(nn.Module):
    """Isolated Phase2 policy prototype; not connected to V1 final-ready runtime."""

    def __init__(self, d_model: int = 16, num_lanes: int = 4) -> None:
        super().__init__()
        self.block = TinyLoopedAttentionBlock(d_model)
        self.actor_head = nn.Linear(d_model, num_lanes)
        self.critic_head = nn.Linear(d_model, 1)

    def forward(self, inputs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        hidden = self.block(inputs).mean(dim=1)
        return self.actor_head(hidden), self.critic_head(hidden)


class StableRankMonitor:
    def __init__(self, model: nn.Module, target_keywords: tuple[str, ...] = ("q_proj", "k_proj")) -> None:
        self.model = model
        self.target_keywords = target_keywords

    def target_parameters(self) -> list[tuple[str, nn.Parameter]]:
        return [
            (name, param)
            for name, param in self.model.named_parameters()
            if param.requires_grad and param.ndim == 2 and any(keyword in name for keyword in self.target_keywords)
        ]

    @staticmethod
    def stable_rank(param: torch.Tensor) -> float:
        weight = param.detach().float()
        fro_sq = torch.linalg.matrix_norm(weight, ord="fro").pow(2)
        spectral_sq = torch.linalg.matrix_norm(weight, ord=2).pow(2)
        if not torch.isfinite(fro_sq) or not torch.isfinite(spectral_sq) or spectral_sq <= 0:
            return 0.0
        return round(float(fro_sq / spectral_sq), 6)

    def compute(self) -> dict[str, float]:
        return {name: self.stable_rank(param) for name, param in self.target_parameters()}


class NewtonSchulzLowRankDecay:
    """AlphaGPT-style LoRD: post-optimizer Newton-Schulz decay on q/k matrices."""

    def __init__(
        self,
        model: nn.Module,
        *,
        decay_rate: float = 1e-3,
        target_keywords: tuple[str, ...] = ("q_proj", "k_proj"),
        ns_steps: int = 5,
    ) -> None:
        self.model = model
        self.decay_rate = decay_rate
        self.target_keywords = target_keywords
        self.ns_steps = ns_steps

    def target_parameters(self) -> list[tuple[str, nn.Parameter]]:
        return [
            (name, param)
            for name, param in self.model.named_parameters()
            if param.requires_grad and param.ndim == 2 and any(keyword in name for keyword in self.target_keywords)
        ]

    def _newton_schulz_direction(self, param: torch.Tensor) -> torch.Tensor:
        weight = param.detach().float()
        norm = torch.linalg.matrix_norm(weight, ord="fro")
        if not torch.isfinite(norm) or norm <= 0:
            return torch.zeros_like(param)
        x = weight / norm
        transposed = x.shape[0] < x.shape[1]
        if transposed:
            x = x.T
        for _ in range(self.ns_steps):
            x = 1.5 * x - 0.5 * x @ (x.T @ x)
        if transposed:
            x = x.T
        return x.to(dtype=param.dtype, device=param.device)

    def step(self) -> list[str]:
        updated: list[str] = []
        with torch.no_grad():
            for name, param in self.target_parameters():
                direction = self._newton_schulz_direction(param)
                param.add_(direction, alpha=-self.decay_rate)
                updated.append(name)
        return updated


def run_lord_smoke_step(seed: int = 7) -> dict[str, Any]:
    start = time.perf_counter()
    torch.manual_seed(seed)
    model = Phase2PolicyNetwork(d_model=16, num_lanes=4)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    monitor = StableRankMonitor(model)
    lord = NewtonSchulzLowRankDecay(model, decay_rate=1e-3, target_keywords=("q_proj", "k_proj"))

    inputs = torch.randn(4, 3, 16)
    target_actions = torch.tensor([0, 1, 2, 3])
    target_values = torch.zeros(4, 1)

    stable_rank_before = monitor.compute()
    logits, values = model(inputs)
    loss = nn.CrossEntropyLoss()(logits, target_actions) + nn.MSELoss()(values, target_values)
    loss.backward()
    optimizer.step()
    optimizer_step_completed = True
    optimizer.zero_grad(set_to_none=True)
    target_parameter_names = lord.step()
    stable_rank_after = monitor.compute()

    finite = all(math.isfinite(value) and value > 0 for value in stable_rank_after.values())
    return {
        "source_reference": "AlphaGPT lord.NewtonSchulzLowRankDecay semantics: post-optimizer q_proj/k_proj decay",
        "prototype_scope": "isolated_phase2_policy_network_not_connected_to_v1_runtime",
        "target_keywords": ["q_proj", "k_proj"],
        "target_parameter_names": target_parameter_names,
        "stable_rank_before": stable_rank_before,
        "stable_rank_after": stable_rank_after,
        "optimizer_step_completed_before_lord": optimizer_step_completed,
        "finite_stable_rank": finite,
        "loss": round(float(loss.detach()), 6),
        "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 3),
        "performance_guard": "tiny_smoke_step_only_no_main_search_training",
    }


def run_lord_training_harness(seed: int = 11, steps: int = 6) -> dict[str, Any]:
    """Small isolated training loop; validates LoRD mechanics without steering search."""

    start = time.perf_counter()
    torch.manual_seed(seed)
    model = Phase2PolicyNetwork(d_model=16, num_lanes=4)
    optimizer = torch.optim.AdamW(model.parameters(), lr=8e-4)
    monitor = StableRankMonitor(model)
    lord = NewtonSchulzLowRankDecay(model, decay_rate=8e-4, target_keywords=("q_proj", "k_proj"), ns_steps=4)

    stable_rank_history: list[dict[str, float]] = []
    loss_history: list[float] = []
    lord_target_history: list[list[str]] = []
    for step in range(steps):
        # Deterministic synthetic policy batch: this is a harness, not market training.
        inputs = torch.randn(6, 4, 16) + (step * 0.02)
        target_actions = torch.tensor([(step + idx) % 4 for idx in range(6)])
        target_values = torch.linspace(-0.2, 0.2, steps=6).unsqueeze(-1)

        before = monitor.compute()
        logits, values = model(inputs)
        actor_loss = nn.CrossEntropyLoss()(logits, target_actions)
        critic_loss = nn.MSELoss()(values, target_values)
        loss = actor_loss + (0.25 * critic_loss)
        loss.backward()
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        lord_targets = lord.step()
        after = monitor.compute()

        stable_rank_history.append(
            {
                "step": step + 1,
                **{f"before::{name}": value for name, value in before.items()},
                **{f"after::{name}": value for name, value in after.items()},
            }
        )
        loss_history.append(round(float(loss.detach()), 6))
        lord_target_history.append(lord_targets)

    final_ranks = monitor.compute()
    finite_rank = all(math.isfinite(value) and value > 0 for value in final_ranks.values())
    rank_floor = min(final_ranks.values()) if final_ranks else 0.0
    elapsed_ms = round((time.perf_counter() - start) * 1000.0, 3)
    return {
        "harness_scope": "isolated_phase2_policy_training_reference",
        "connected_to_main_search_runtime": False,
        "training_data_source": "deterministic_synthetic_policy_batch",
        "steps": steps,
        "optimizer_step_before_lord_every_step": True,
        "lord_target_keywords": ["q_proj", "k_proj"],
        "lord_target_parameter_names": sorted(set(name for targets in lord_target_history for name in targets)),
        "lord_target_history": lord_target_history,
        "stable_rank_history": stable_rank_history,
        "stable_rank_final": final_ranks,
        "stable_rank_floor": round(rank_floor, 6),
        "finite_stable_rank": finite_rank,
        "loss_history": loss_history,
        "loss_is_finite": all(math.isfinite(value) for value in loss_history),
        "elapsed_ms": elapsed_ms,
        "performance_guard": {
            "max_steps": 6,
            "tiny_d_model": 16,
            "no_main_search_training": True,
            "elapsed_ms_budget": 8000.0,
            "elapsed_within_budget": elapsed_ms < 8000.0,
        },
    }
