from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold


REPLAY_RANKER_VERSION = "phase2-stock-pit-replay-ranker-v1-2026-05-11"

BASE_PRE_REPLAY_FEATURES = [
    "complexity_score",
    "cheap_backtest_sharpe",
    "cheap_backtest_fitness",
    "cheap_backtest_turnover",
    "cheap_backtest_returns",
    "cheap_backtest_drawdown",
    "cheap_backtest_ic",
    "cheap_backtest_rank_ic",
    "cheap_backtest_margin",
    "gap_score",
    "non_gap_score",
    "gap_minus_non_gap",
    "train_valid_decay",
    "subperiod_stability",
    "regime_stability",
    "sector_exposure",
    "style_exposure",
    "beta_exposure",
    "liquidity_exposure",
    "corr_to_existing_max",
]

POST_REPLAY_FORBIDDEN_FEATURES = {
    "strict_pass",
    "replay_attempted",
    "replay_pass",
    "non_gap_replay_pass",
    "replay_error_reason",
    "portfolio_replay_day_count",
    "portfolio_replay_cost_bps",
    "portfolio_replay_long_only_net_mean",
    "portfolio_replay_long_only_sortino",
    "portfolio_replay_long_short_net_mean",
    "portfolio_replay_long_short_sortino",
    "portfolio_replay_avg_one_way_turnover",
    "strict_mean_rank_ic",
    "strict_mean_cost_adjusted_window_spread",
    "strict_cost_adjusted_sortino",
    "strict_mean_one_way_turnover",
    "cost_survives",
    "fast_to_strict_ic_decay",
    "strict_gatekeeper_decision",
    "strict_blocker_flags",
    "shadow_rewards_selection_role",
    "shadow_replay_aware_reward",
    "shadow_cluster_contribution_reward",
    "shadow_cost_turnover_capacity_reward",
    "shadow_gap_residual_reward",
    "shadow_triple_barrier_auxiliary",
}

TOKEN_LIST_FEATURES = {
    "operator_list": "op",
    "field_family_list": "field_family",
    "field_list": "field",
    "window_list": "window",
}

CATEGORICAL_FEATURES = [
    "generator_name",
    "neutralization",
    "universe",
    "delay",
    "region",
]

DEFAULT_LANE_PRIORS = {
    "cem_adaptive_grammar": (4.0, 6.0),
    "ast_evolutionary_mutation": (3.0, 7.0),
    "simple_template": (1.5, 8.5),
    "non_gap_forced_sampler": (1.0, 9.0),
    "typed_random_dark": (1.0, 9.0),
    "unreached_space": (1.0, 9.0),
    "rx_no_policy_true_limit": (1.0, 9.0),
    "rx_diverse_beam": (1.0, 9.0),
}

PURE_RL_CONTROL_VERSION = "phase2-stock-pit-pure-rl-control-v1-2026-05-11"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        numeric = float(value)
        if not math.isfinite(numeric):
            return default
        return numeric
    except (TypeError, ValueError):
        return default


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if pd.isna(value):
        return []
    return [value]


def _safe_name(value: Any) -> str:
    text = str(value if value is not None else "missing").strip()
    return "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in text)[:80] or "missing"


def _numeric_frame(df: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(index=df.index)
    for column in BASE_PRE_REPLAY_FEATURES:
        if column not in df.columns:
            values = pd.Series(np.nan, index=df.index)
        else:
            values = pd.to_numeric(df[column], errors="coerce")
        output[column] = values
        output[f"{column}__isna"] = values.isna().astype(float)
        median = values.median(skipna=True)
        fill_value = float(median) if pd.notna(median) and math.isfinite(float(median)) else 0.0
        output[column] = values.fillna(fill_value).astype(float)
    return output


def _categorical_frame(df: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for column in CATEGORICAL_FEATURES:
        if column not in df.columns:
            series = pd.Series("missing", index=df.index)
        else:
            series = df[column].fillna("missing").astype(str)
        dummies = pd.get_dummies(series, prefix=f"cat_{column}", dtype=float)
        parts.append(dummies)
    return pd.concat(parts, axis=1) if parts else pd.DataFrame(index=df.index)


def _token_frame(df: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(index=df.index)
    for column, prefix in TOKEN_LIST_FEATURES.items():
        token_counts: dict[str, int] = {}
        values_by_index: dict[Any, set[str]] = {}
        if column not in df.columns:
            continue
        for index, value in df[column].items():
            tokens = {_safe_name(token) for token in _as_list(value)}
            values_by_index[index] = tokens
            for token in tokens:
                token_counts[token] = token_counts.get(token, 0) + 1
        for token in sorted(token_counts):
            output[f"{prefix}__{token}"] = [1.0 if token in values_by_index.get(index, set()) else 0.0 for index in df.index]
    return output


def build_pre_replay_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    leaked = sorted(set(BASE_PRE_REPLAY_FEATURES + CATEGORICAL_FEATURES + list(TOKEN_LIST_FEATURES)) & POST_REPLAY_FORBIDDEN_FEATURES)
    if leaked:
        raise ValueError(f"forbidden ranker feature columns requested: {leaked}")
    matrix = pd.concat([_numeric_frame(df), _categorical_frame(df), _token_frame(df)], axis=1)
    matrix = matrix.loc[:, ~matrix.columns.duplicated()].copy()
    feature_columns = sorted(matrix.columns)
    return matrix[feature_columns], feature_columns


def _make_model(random_state: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.04,
        max_leaf_nodes=31,
        l2_regularization=0.1,
        random_state=random_state,
    )


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(values, -35.0, 35.0)))


def _standardize(train: pd.DataFrame, all_rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    mean = train.mean(axis=0).to_numpy(dtype=float)
    std = train.std(axis=0, ddof=0).replace(0.0, 1.0).fillna(1.0).to_numpy(dtype=float)
    train_x = (train.to_numpy(dtype=float) - mean) / std
    all_x = (all_rows.to_numpy(dtype=float) - mean) / std
    return train_x, all_x, {"mean": mean.tolist(), "std": std.tolist()}


def _fit_logged_policy_gradient(
    X: np.ndarray,
    reward: np.ndarray,
    *,
    random_state: int,
    epochs: int = 500,
    learning_rate: float = 0.03,
    entropy_coeff: float = 0.002,
    l2: float = 0.001,
) -> dict[str, Any]:
    rng = np.random.default_rng(random_state)
    n_rows, n_features = X.shape
    weights = rng.normal(loc=0.0, scale=0.01, size=n_features)
    bias = 0.0
    baseline = float(np.mean(reward)) if n_rows else 0.0
    for _ in range(max(1, int(epochs))):
        logits = X @ weights + bias
        p = _sigmoid(logits)
        advantage = reward - baseline
        entropy_grad = np.log(np.clip(1.0 - p, 1e-9, 1.0) / np.clip(p, 1e-9, 1.0)) * p * (1.0 - p)
        grad_logits = advantage * (1.0 - p) + entropy_coeff * entropy_grad
        grad_w = (X.T @ grad_logits) / max(1, n_rows) - l2 * weights
        grad_b = float(np.mean(grad_logits))
        weights += learning_rate * grad_w
        bias += learning_rate * grad_b
    return {
        "weights": weights,
        "bias": bias,
        "baseline": baseline,
        "epochs": int(epochs),
        "learning_rate": float(learning_rate),
        "entropy_coeff": float(entropy_coeff),
        "l2": float(l2),
    }


def _policy_predict(policy: dict[str, Any], X: np.ndarray) -> np.ndarray:
    return _sigmoid(X @ np.asarray(policy["weights"], dtype=float) + float(policy["bias"]))


def _sample_weight(y: pd.Series) -> np.ndarray:
    y_values = y.astype(int).to_numpy()
    positives = max(1, int(y_values.sum()))
    negatives = max(1, int(len(y_values) - y_values.sum()))
    pos_weight = len(y_values) / (2.0 * positives)
    neg_weight = len(y_values) / (2.0 * negatives)
    return np.where(y_values == 1, pos_weight, neg_weight)


def _splitter(y: pd.Series, groups: pd.Series, max_splits: int) -> Any:
    unique_groups = int(groups.nunique())
    positives = int(y.astype(int).sum())
    negatives = int(len(y) - positives)
    n_splits = min(max_splits, unique_groups, positives, negatives)
    if n_splits < 2:
        return None
    try:
        return StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=42)
    except TypeError:
        return GroupKFold(n_splits=n_splits)


def _score_predictions(y: pd.Series, p: np.ndarray) -> dict[str, Any]:
    y_values = y.astype(int).to_numpy()
    baseline = float(y_values.mean()) if len(y_values) else 0.0
    metrics: dict[str, Any] = {
        "baseline_pass_rate": round(baseline, 6),
        "sample_count": int(len(y_values)),
        "positive_count": int(y_values.sum()),
    }
    if len(set(y_values.tolist())) > 1:
        metrics["roc_auc"] = round(float(roc_auc_score(y_values, p)), 6)
    else:
        metrics["roc_auc"] = None
    metrics["average_precision"] = round(float(average_precision_score(y_values, p)), 6) if int(y_values.sum()) > 0 else None
    order = np.argsort(-p)
    for share in (0.05, 0.10, 0.20):
        n = max(1, int(math.ceil(len(order) * share)))
        top_rate = float(y_values[order[:n]].mean()) if n else 0.0
        metrics[f"top_{int(share * 100)}pct_pass_rate"] = round(top_rate, 6)
        metrics[f"top_{int(share * 100)}pct_lift"] = round(top_rate / baseline, 6) if baseline > 0 else None
    return metrics


def _holdout_metrics_by_column(
    candidates: pd.DataFrame,
    *,
    target: str,
    holdout_column: str,
    feature_columns: list[str],
    random_state: int,
) -> dict[str, Any]:
    if holdout_column not in candidates.columns:
        return {"status": "missing_holdout_column", "holdout_column": holdout_column}
    train_mask = candidates["replay_attempted"].astype(bool) & candidates[target].notna()
    frame = candidates.loc[train_mask].copy()
    if frame.empty:
        return {"status": "no_training_rows", "holdout_column": holdout_column}
    X_all, all_columns = build_pre_replay_matrix(candidates)
    # Keep a stable feature contract even if a future builder adds columns.
    columns = [column for column in feature_columns if column in all_columns]
    X = X_all.loc[frame.index, columns]
    y = frame[target].astype(int)
    predictions = pd.Series(np.nan, index=frame.index, dtype=float)
    details: list[dict[str, Any]] = []
    groups = frame[holdout_column].fillna("missing").astype(str)
    for offset, group_value in enumerate(sorted(groups.unique())):
        valid_idx = groups[groups == group_value].index
        train_idx = groups[groups != group_value].index
        y_train = y.loc[train_idx]
        y_valid = y.loc[valid_idx]
        if len(train_idx) < 20 or int(y_train.sum()) < 2 or int(len(y_train) - y_train.sum()) < 2:
            details.append(
                {
                    "group": group_value,
                    "status": "skipped_insufficient_train_class_balance",
                    "valid_rows": int(len(valid_idx)),
                    "valid_positive_count": int(y_valid.sum()),
                }
            )
            continue
        model = _make_model(random_state + 100 + offset)
        model.fit(X.loc[train_idx], y_train, sample_weight=_sample_weight(y_train))
        p = model.predict_proba(X.loc[valid_idx])[:, 1]
        predictions.loc[valid_idx] = p
        detail = {
            "group": group_value,
            "status": "scored",
            "train_rows": int(len(train_idx)),
            "valid_rows": int(len(valid_idx)),
            "valid_positive_count": int(y_valid.sum()),
        }
        if len(set(y_valid.astype(int).tolist())) > 1:
            detail["roc_auc"] = round(float(roc_auc_score(y_valid.astype(int), p)), 6)
        details.append(detail)
    valid = predictions.notna()
    metrics = _score_predictions(y.loc[valid], predictions.loc[valid].to_numpy()) if valid.any() else {}
    return {
        "status": "completed" if valid.any() else "no_scored_groups",
        "holdout_column": holdout_column,
        "scored_rows": int(valid.sum()),
        "group_details": details,
        "metrics": metrics,
    }


@dataclass(slots=True)
class TrainedReplayRanker:
    target: str
    model: HistGradientBoostingClassifier
    feature_columns: list[str]
    metrics: dict[str, Any]


def train_one_ranker(
    candidates: pd.DataFrame,
    *,
    target: str,
    random_state: int = 42,
    max_splits: int = 5,
) -> tuple[TrainedReplayRanker | None, pd.Series, dict[str, Any]]:
    if target not in candidates.columns:
        return None, pd.Series(np.nan, index=candidates.index), {"status": "missing_target", "target": target}
    train_mask = candidates["replay_attempted"].astype(bool) & candidates[target].notna()
    train = candidates.loc[train_mask].copy()
    if train.empty:
        return None, pd.Series(np.nan, index=candidates.index), {"status": "no_training_rows", "target": target}

    X_all, feature_columns = build_pre_replay_matrix(candidates)
    X = X_all.loc[train.index]
    y = train[target].astype(int)
    positives = int(y.sum())
    negatives = int(len(y) - positives)
    if positives < 2 or negatives < 2:
        return None, pd.Series(np.nan, index=candidates.index), {
            "status": "insufficient_class_balance",
            "target": target,
            "training_rows": int(len(y)),
            "positive_count": positives,
            "negative_count": negatives,
        }

    groups = train["ast_hash"].fillna(train["candidate_id"]).astype(str).str[:12]
    splitter = _splitter(y, groups, max_splits=max_splits)
    oof = pd.Series(np.nan, index=train.index, dtype=float)
    fold_metrics: list[dict[str, Any]] = []
    if splitter is not None:
        split_iter = splitter.split(X, y, groups)
        for fold_index, (tr_idx, va_idx) in enumerate(split_iter):
            model = _make_model(random_state + fold_index)
            model.fit(X.iloc[tr_idx], y.iloc[tr_idx], sample_weight=_sample_weight(y.iloc[tr_idx]))
            p = model.predict_proba(X.iloc[va_idx])[:, 1]
            oof.iloc[va_idx] = p
            fold_metrics.append(
                {
                    "fold_index": fold_index,
                    "train_rows": int(len(tr_idx)),
                    "valid_rows": int(len(va_idx)),
                    "valid_positive_count": int(y.iloc[va_idx].sum()),
                }
            )
    else:
        oof.loc[:] = float(y.mean())

    valid_oof = oof.notna()
    cv_metrics = _score_predictions(y.loc[valid_oof], oof.loc[valid_oof].to_numpy()) if valid_oof.any() else {}
    final_model = _make_model(random_state)
    final_model.fit(X, y, sample_weight=_sample_weight(y))
    all_predictions = pd.Series(final_model.predict_proba(X_all)[:, 1], index=candidates.index, dtype=float)
    metrics = {
        "status": "trained",
        "target": target,
        "training_rows": int(len(y)),
        "positive_count": positives,
        "negative_count": negatives,
        "group_count": int(groups.nunique()),
        "feature_count": int(len(feature_columns)),
        "feature_columns": feature_columns,
        "folds": fold_metrics,
        "oof": cv_metrics,
        "seed_holdout": _holdout_metrics_by_column(
            candidates,
            target=target,
            holdout_column="generator_seed",
            feature_columns=feature_columns,
            random_state=random_state,
        ),
        "lane_holdout": _holdout_metrics_by_column(
            candidates,
            target=target,
            holdout_column="generator_name",
            feature_columns=feature_columns,
            random_state=random_state,
        ),
        "leakage_guard": {
            "post_replay_forbidden_features": sorted(POST_REPLAY_FORBIDDEN_FEATURES),
            "feature_overlap_with_forbidden": sorted(set(feature_columns) & POST_REPLAY_FORBIDDEN_FEATURES),
        },
    }
    return TrainedReplayRanker(target=target, model=final_model, feature_columns=feature_columns, metrics=metrics), all_predictions, metrics


def _minmax(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if values.notna().sum() == 0:
        return pd.Series(0.0, index=series.index)
    low = values.min(skipna=True)
    high = values.max(skipna=True)
    if not math.isfinite(float(low)) or not math.isfinite(float(high)) or abs(float(high) - float(low)) < 1e-12:
        return pd.Series(0.0, index=series.index)
    return ((values - low) / (high - low)).fillna(0.0).clip(0.0, 1.0)


def _behavioral_plausibility(row: pd.Series) -> float:
    families = set(_as_list(row.get("field_family_list")))
    operators = set(_as_list(row.get("operator_list")))
    score = 0.0
    if "liquidity" in families and ("CSRank" in operators or "ZScore" in operators):
        score += 0.35
    if "price_shape" in families and ("Mean" in operators or "Std" in operators or "Mom" in operators):
        score += 0.25
    if "return_vol" in families and ("Mean" in operators or "Std" in operators):
        score += 0.20
    if "trend_state" in families:
        score += 0.15
    if len(families) >= 2:
        score += 0.10
    return round(min(1.0, score), 6)


def score_shadow_selector(candidates: pd.DataFrame, *, selection_budget: int = 96) -> pd.DataFrame:
    scored = candidates.copy()
    if "p_non_gap_replay" not in scored.columns:
        scored["p_non_gap_replay"] = 0.0
    if "p_replay" not in scored.columns:
        scored["p_replay"] = scored["p_non_gap_replay"]
    corr = pd.to_numeric(scored.get("corr_to_existing_max", pd.Series(0.0, index=scored.index)), errors="coerce").fillna(0.0)
    scored["novelty_score"] = (1.0 - corr.clip(0.0, 1.0)).clip(0.0, 1.0)
    scored["behavioral_plausibility"] = scored.apply(_behavioral_plausibility, axis=1)
    scored["complexity_penalty"] = _minmax(scored["complexity_score"])
    scored["turnover_penalty"] = _minmax(scored["cheap_backtest_turnover"])
    scored["gap_dependency_penalty"] = pd.to_numeric(scored["gap_minus_non_gap"], errors="coerce").fillna(0.0).clip(lower=0.0)
    scored["selection_score"] = (
        1.00 * pd.to_numeric(scored["p_non_gap_replay"], errors="coerce").fillna(0.0)
        + 0.25 * pd.to_numeric(scored["p_replay"], errors="coerce").fillna(0.0)
        + 0.15 * scored["novelty_score"]
        + 0.10 * scored["behavioral_plausibility"]
        - 0.30 * corr.clip(0.0, 1.0)
        - 0.20 * scored["turnover_penalty"]
        - 0.15 * scored["complexity_penalty"]
        - 0.25 * scored["gap_dependency_penalty"]
    )
    scored["selector_bucket"] = ""

    budget = max(1, int(selection_budget))
    if budget == 1:
        exploit_n, explore_n, diversity_n = 1, 0, 0
    elif budget == 2:
        exploit_n, explore_n, diversity_n = 1, 1, 0
    else:
        exploit_n = max(1, int(round(budget * 0.60)))
        explore_n = max(1, int(round(budget * 0.25)))
        diversity_n = max(0, budget - exploit_n - explore_n)
        overflow = exploit_n + explore_n + diversity_n - budget
        if overflow > 0:
            diversity_reduction = min(diversity_n, overflow)
            diversity_n -= diversity_reduction
            overflow -= diversity_reduction
        if overflow > 0:
            explore_reduction = min(max(0, explore_n - 1), overflow)
            explore_n -= explore_reduction
            overflow -= explore_reduction
        if overflow > 0:
            exploit_n = max(1, exploit_n - overflow)
    selected: list[int] = []
    seen: set[int] = set()

    def add(indices: list[int], role: str, limit: int) -> None:
        if limit <= 0:
            return
        count = 0
        for idx in indices:
            if idx in seen:
                continue
            seen.add(idx)
            selected.append(idx)
            scored.loc[idx, "selector_bucket"] = role
            count += 1
            if count >= limit:
                break

    add(scored.sort_values("selection_score", ascending=False).index.tolist(), "exploit_ranker_top", exploit_n)
    per_lane = max(1, math.ceil(explore_n / max(1, scored["generator_name"].nunique())))
    explore_indices: list[int] = []
    for _, group in scored.sort_values("selection_score", ascending=False).groupby("generator_name", sort=False):
        explore_indices.extend(group.head(per_lane).index.tolist())
    add(explore_indices, "explore_lane_floor", explore_n)
    diversity_order = scored.sort_values(["novelty_score", "selection_score"], ascending=[False, False]).index.tolist()
    add(diversity_order, "diversity_low_corr", diversity_n)
    if len(selected) < budget:
        add(scored.sort_values("selection_score", ascending=False).index.tolist(), "overflow_ranker_top", budget - len(selected))
    scored["selector_selected"] = scored.index.isin(selected)
    return scored


class LaneBandit:
    def __init__(
        self,
        lanes: list[str],
        *,
        priors: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        self.lanes = list(dict.fromkeys(lanes))
        priors = priors or {}
        self.alpha = {lane: float(priors.get(lane, (1.0, 1.0))[0]) for lane in self.lanes}
        self.beta = {lane: float(priors.get(lane, (1.0, 1.0))[1]) for lane in self.lanes}

    def update(self, lane: str, success_count: int, failure_count: int) -> None:
        if lane not in self.alpha:
            self.lanes.append(lane)
            self.alpha[lane] = 1.0
            self.beta[lane] = 1.0
        self.alpha[lane] += max(0, int(success_count))
        self.beta[lane] += max(0, int(failure_count))

    def allocate(self, total_budget: int, *, min_share: float = 0.05, seed: int = 42) -> dict[str, int]:
        total_budget = max(0, int(total_budget))
        if not self.lanes or total_budget == 0:
            return {}
        rng = np.random.default_rng(seed)
        samples = {lane: float(rng.beta(self.alpha[lane], self.beta[lane])) for lane in self.lanes}
        floor = int(total_budget * min_share)
        if floor * len(self.lanes) > total_budget:
            floor = total_budget // len(self.lanes)
        remaining = total_budget - floor * len(self.lanes)
        raw = np.array([samples[lane] for lane in self.lanes], dtype=float)
        raw = raw / raw.sum() if raw.sum() > 0 else np.ones(len(self.lanes)) / len(self.lanes)
        allocation = {lane: floor + int(remaining * raw[index]) for index, lane in enumerate(self.lanes)}
        diff = total_budget - sum(allocation.values())
        if diff:
            best_lane = max(samples, key=samples.get)
            allocation[best_lane] += diff
        return allocation

    def state(self) -> dict[str, Any]:
        return {
            "version": REPLAY_RANKER_VERSION,
            "lanes": self.lanes,
            "alpha": self.alpha,
            "beta": self.beta,
            "posterior_mean": {
                lane: round(self.alpha[lane] / max(1e-12, self.alpha[lane] + self.beta[lane]), 6)
                for lane in self.lanes
            },
        }


def build_lane_bandit_from_replay(replay: pd.DataFrame, *, lanes: list[str] | None = None) -> LaneBandit:
    lane_names = lanes or sorted(str(value) for value in replay.get("generator_name", pd.Series(dtype=str)).dropna().unique())
    bandit = LaneBandit(lane_names, priors=DEFAULT_LANE_PRIORS)
    if replay.empty:
        return bandit
    for lane, group in replay.groupby("generator_name"):
        attempted = int(len(group))
        success = int(group["non_gap_replay_pass"].astype(bool).sum()) if "non_gap_replay_pass" in group else 0
        bandit.update(str(lane), success, attempted - success)
    return bandit


def score_with_trained_replay_rankers(
    candidates: pd.DataFrame,
    *,
    model_dir: Path | str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply persisted replay-aware rankers to pre-replay candidate rows.

    The scorer is selector-only: it consumes the same pre-replay feature matrix
    used during training, aligns missing feature columns to zero, and never
    requires strict/replay labels.
    """
    scored = candidates.copy()
    model_root = Path(model_dir)
    X_all, available_columns = build_pre_replay_matrix(scored)
    available = set(available_columns)
    report: dict[str, Any] = {
        "version": REPLAY_RANKER_VERSION,
        "model_dir": str(model_root),
        "candidate_rows": int(len(scored)),
        "models": {},
    }
    for target, output_column in (("non_gap_replay_pass", "p_non_gap_replay"), ("replay_pass", "p_replay")):
        model_path = model_root / f"{target}_ranker.joblib"
        if not model_path.exists():
            scored[output_column] = 0.0
            report["models"][target] = {"status": "missing_model", "path": str(model_path)}
            continue
        payload = joblib.load(model_path)
        feature_columns = list(payload.get("feature_columns") or [])
        missing = [column for column in feature_columns if column not in available]
        X = X_all.reindex(columns=feature_columns, fill_value=0.0)
        model = payload.get("model")
        if model is None or not hasattr(model, "predict_proba"):
            scored[output_column] = 0.0
            report["models"][target] = {"status": "invalid_model_payload", "path": str(model_path)}
            continue
        scored[output_column] = model.predict_proba(X)[:, 1]
        report["models"][target] = {
            "status": "scored",
            "path": str(model_path),
            "feature_count": int(len(feature_columns)),
            "missing_feature_count": int(len(missing)),
            "missing_features": missing[:30],
        }
    report["leakage_guard"] = {
        "feature_overlap_with_forbidden": sorted(set(available_columns) & POST_REPLAY_FORBIDDEN_FEATURES),
        "post_replay_forbidden_features": sorted(POST_REPLAY_FORBIDDEN_FEATURES),
    }
    return scored, report


def train_pure_rl_control(
    candidates: pd.DataFrame,
    *,
    target: str = "non_gap_replay_pass",
    random_state: int = 42,
    epochs: int = 500,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Logged policy-gradient control, used only as a shadow baseline.

    This is intentionally not a supervised classifier. It treats replayed
    candidates as logged actions and optimizes a stochastic select probability
    against replay reward. Because unplayed actions have no counterfactual
    reward, the output is a control group for selector research, not a claim of
    online RL optimality.
    """

    if target not in candidates.columns:
        scored = candidates.copy()
        scored["pure_rl_score"] = 0.0
        scored["pure_rl_selected"] = False
        return scored, {"status": "missing_target", "target": target}
    train_mask = candidates["replay_attempted"].astype(bool) & candidates[target].notna()
    train = candidates.loc[train_mask].copy()
    scored = candidates.copy()
    if train.empty:
        scored["pure_rl_score"] = 0.0
        scored["pure_rl_selected"] = False
        return scored, {"status": "no_training_rows", "target": target}

    X_all, feature_columns = build_pre_replay_matrix(candidates)
    X_train_df = X_all.loc[train.index]
    reward = train[target].astype(float).to_numpy()
    positives = int(np.sum(reward > 0))
    negatives = int(len(reward) - positives)
    if positives < 2 or negatives < 2:
        scored["pure_rl_score"] = float(np.mean(reward)) if len(reward) else 0.0
        scored["pure_rl_selected"] = False
        return scored, {
            "status": "insufficient_reward_balance",
            "target": target,
            "training_rows": int(len(reward)),
            "positive_count": positives,
            "negative_count": negatives,
        }

    groups = train["ast_hash"].fillna(train["candidate_id"]).astype(str).str[:12]
    splitter = _splitter(train[target].astype(int), groups, max_splits=5)
    oof = pd.Series(np.nan, index=train.index, dtype=float)
    folds: list[dict[str, Any]] = []
    if splitter is not None:
        for fold_index, (tr_idx, va_idx) in enumerate(splitter.split(X_train_df, train[target].astype(int), groups)):
            fold_train = X_train_df.iloc[tr_idx]
            fold_valid = X_train_df.iloc[va_idx]
            fold_reward = train[target].astype(float).iloc[tr_idx].to_numpy()
            fold_train_x, fold_valid_x, _ = _standardize(fold_train, fold_valid)
            policy = _fit_logged_policy_gradient(
                fold_train_x,
                fold_reward,
                random_state=random_state + fold_index,
                epochs=epochs,
            )
            p = _policy_predict(policy, fold_valid_x)
            oof.iloc[va_idx] = p
            folds.append(
                {
                    "fold_index": int(fold_index),
                    "train_rows": int(len(tr_idx)),
                    "valid_rows": int(len(va_idx)),
                    "valid_positive_count": int(train[target].astype(int).iloc[va_idx].sum()),
                }
            )
    valid_oof = oof.notna()
    oof_metrics = (
        _score_predictions(train[target].astype(int).loc[valid_oof], oof.loc[valid_oof].to_numpy())
        if valid_oof.any()
        else {}
    )

    train_x, all_x, scaler = _standardize(X_train_df, X_all)
    policy = _fit_logged_policy_gradient(
        train_x,
        reward,
        random_state=random_state,
        epochs=epochs,
    )
    scored["pure_rl_score"] = _policy_predict(policy, all_x)
    scored["pure_rl_selected"] = False
    selected_indices = scored.sort_values("pure_rl_score", ascending=False).head(96).index
    scored.loc[selected_indices, "pure_rl_selected"] = True

    selected = scored.loc[selected_indices]
    report = {
        "version": PURE_RL_CONTROL_VERSION,
        "status": "trained_logged_policy_gradient_control",
        "target": target,
        "training_rows": int(len(train)),
        "positive_count": positives,
        "negative_count": negatives,
        "feature_count": int(len(feature_columns)),
        "feature_columns": feature_columns,
        "folds": folds,
        "oof": oof_metrics,
        "selected_count": int(len(selected)),
        "selected_generator_counts": selected["generator_name"].value_counts().to_dict(),
        "known_replay_attempted_count": int(selected["replay_attempted"].astype(bool).sum()),
        "known_non_gap_replay_pass_count": int(selected["non_gap_replay_pass"].astype(bool).sum()),
        "leakage_guard": {
            "post_replay_forbidden_features": sorted(POST_REPLAY_FORBIDDEN_FEATURES),
            "feature_overlap_with_forbidden": sorted(set(feature_columns) & POST_REPLAY_FORBIDDEN_FEATURES),
        },
        "control_limitations": [
            "offline_logged_actions_only_no_counterfactual_rewards_for_unreplayed_candidates",
            "shadow_baseline_not_live_rl_generator",
            "not_a_commercial_alpha_claim",
        ],
        "policy": {
            "baseline": policy["baseline"],
            "epochs": policy["epochs"],
            "learning_rate": policy["learning_rate"],
            "entropy_coeff": policy["entropy_coeff"],
            "l2": policy["l2"],
            "scaler": scaler,
        },
    }
    # The weight vector can be large; keep it in a separate model artifact.
    report["_policy_weights"] = policy["weights"].tolist()
    report["_policy_bias"] = float(policy["bias"])
    return scored, report


def train_rankers_and_score(
    candidates: pd.DataFrame,
    *,
    random_state: int = 42,
) -> tuple[pd.DataFrame, dict[str, Any], dict[str, TrainedReplayRanker]]:
    scored = candidates.copy()
    trained: dict[str, TrainedReplayRanker] = {}
    report: dict[str, Any] = {"version": REPLAY_RANKER_VERSION, "models": {}}
    for target, output_column in (("non_gap_replay_pass", "p_non_gap_replay"), ("replay_pass", "p_replay")):
        model, predictions, metrics = train_one_ranker(scored, target=target, random_state=random_state)
        scored[output_column] = predictions.fillna(0.0)
        report["models"][target] = metrics
        if model is not None:
            trained[target] = model
    pure_rl_scored, pure_rl_report = train_pure_rl_control(scored, target="non_gap_replay_pass", random_state=random_state)
    scored["pure_rl_score"] = pure_rl_scored["pure_rl_score"]
    scored["pure_rl_selected"] = pure_rl_scored["pure_rl_selected"]
    report["pure_rl_control"] = {key: value for key, value in pure_rl_report.items() if key not in {"_policy_weights", "_policy_bias"}}
    report["_pure_rl_policy"] = {
        "weights": pure_rl_report.get("_policy_weights"),
        "bias": pure_rl_report.get("_policy_bias"),
        "feature_columns": pure_rl_report.get("feature_columns"),
        "version": PURE_RL_CONTROL_VERSION,
    }
    return scored, report, trained


def write_ranker_outputs(
    *,
    scored_candidates: pd.DataFrame,
    replay: pd.DataFrame,
    report: dict[str, Any],
    trained: dict[str, TrainedReplayRanker],
    output_dir: Path,
    selection_budget: int,
    bandit_budget: int,
    seed: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir = output_dir / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_manifest: dict[str, str] = {}
    for target, trained_model in trained.items():
        path = model_dir / f"{target}_ranker.joblib"
        joblib.dump(
            {
                "version": REPLAY_RANKER_VERSION,
                "target": target,
                "model": trained_model.model,
                "feature_columns": trained_model.feature_columns,
                "metrics": trained_model.metrics,
            },
            path,
        )
        model_manifest[target] = str(path)
    pure_rl_policy = report.pop("_pure_rl_policy", None)
    if pure_rl_policy and pure_rl_policy.get("weights") is not None:
        pure_rl_path = model_dir / "pure_rl_control_policy.joblib"
        joblib.dump(pure_rl_policy, pure_rl_path)
        model_manifest["pure_rl_control"] = str(pure_rl_path)

    shadow = score_shadow_selector(scored_candidates, selection_budget=selection_budget)
    shadow_path = output_dir / "replay_selector_shadow.parquet"
    shadow.to_parquet(shadow_path, index=False)
    calibration_table, calibration_report = build_replay_ranker_calibration(shadow)
    calibration_table_path = output_dir / "replay_ranker_calibration_deciles.parquet"
    calibration_report_path = output_dir / "replay_ranker_calibration_report.json"
    calibration_table.to_parquet(calibration_table_path, index=False)
    calibration_report_path.write_text(json.dumps(calibration_report, ensure_ascii=False, indent=2), encoding="utf-8")
    pure_rl_shadow_path = output_dir / "pure_rl_selector_shadow.parquet"
    pure_rl_columns = [
        column
        for column in (
            "candidate_event_id",
            "candidate_id",
            "generator_name",
            "generator_seed",
            "expression",
            "normalized_expression",
            "ast_hash",
            "pure_rl_score",
            "pure_rl_selected",
            "replay_attempted",
            "replay_pass",
            "non_gap_replay_pass",
            "strict_pass",
        )
        if column in scored_candidates.columns
    ]
    scored_candidates[pure_rl_columns].to_parquet(pure_rl_shadow_path, index=False)

    bandit = build_lane_bandit_from_replay(replay, lanes=sorted(scored_candidates["generator_name"].dropna().astype(str).unique()))
    allocation = bandit.allocate(bandit_budget, min_share=0.05, seed=seed)
    bandit_state_path = output_dir / "lane_bandit_state.json"
    bandit_allocation_path = output_dir / "lane_bandit_allocation.json"
    bandit_state_path.write_text(json.dumps(bandit.state(), ensure_ascii=False, indent=2), encoding="utf-8")
    bandit_allocation_path.write_text(json.dumps(allocation, ensure_ascii=False, indent=2), encoding="utf-8")

    selected = shadow[shadow["selector_selected"]].copy()
    selection_summary = {
        "selection_budget": int(selection_budget),
        "selected_count": int(len(selected)),
        "bucket_counts": selected["selector_bucket"].value_counts().to_dict(),
        "generator_counts": selected["generator_name"].value_counts().to_dict(),
        "mean_selection_score": round(float(selected["selection_score"].mean()), 6) if len(selected) else None,
        "known_replay_attempted_count": int(selected["replay_attempted"].astype(bool).sum()) if len(selected) else 0,
        "known_non_gap_replay_pass_count": int(selected["non_gap_replay_pass"].astype(bool).sum()) if len(selected) else 0,
    }
    report = {
        **report,
        "model_manifest": model_manifest,
        "shadow_selector": selection_summary,
        "pure_rl_control": report.get("pure_rl_control", {}),
        "calibration": {
            "status": calibration_report.get("status"),
            "sample": calibration_report.get("sample", {}),
            "score_lifts": calibration_report.get("score_lifts", {}),
            "decile_trends": calibration_report.get("decile_trends", {}),
            "pure_rl_control_status": calibration_report.get("pure_rl_control_status"),
            "table_path": str(calibration_table_path),
            "report_path": str(calibration_report_path),
        },
        "bandit": {
            "budget": int(bandit_budget),
            "allocation": allocation,
            "state_path": str(bandit_state_path),
            "allocation_path": str(bandit_allocation_path),
        },
        "outputs": {
            "scored_candidates": str(output_dir / "candidates_scored.parquet"),
            "shadow_selector": str(shadow_path),
            "pure_rl_selector": str(pure_rl_shadow_path),
            "calibration_deciles": str(calibration_table_path),
            "calibration_report": str(calibration_report_path),
            "bandit_state": str(bandit_state_path),
            "bandit_allocation": str(bandit_allocation_path),
        },
    }
    scored_candidates.to_parquet(output_dir / "candidates_scored.parquet", index=False)
    (output_dir / "replay_ranker_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _bucket_edges(count: int, bucket_count: int) -> list[int]:
    bucket_count = max(1, int(bucket_count))
    return [int(round(index * count / bucket_count)) for index in range(bucket_count + 1)]


def _score_bucket_table(
    frame: pd.DataFrame,
    *,
    score_column: str,
    bucket_count: int = 10,
    descending: bool = True,
) -> pd.DataFrame:
    if score_column not in frame.columns:
        return pd.DataFrame()
    replay = frame[frame["replay_attempted"].astype(bool)].copy()
    if replay.empty:
        return pd.DataFrame()
    replay = replay[pd.to_numeric(replay[score_column], errors="coerce").notna()].copy()
    if replay.empty:
        return pd.DataFrame()
    replay[score_column] = pd.to_numeric(replay[score_column], errors="coerce")
    replay = replay.sort_values(score_column, ascending=not descending).reset_index(drop=True)
    edges = _bucket_edges(len(replay), bucket_count)
    rows: list[dict[str, Any]] = []
    for bucket_index in range(bucket_count):
        start, end = edges[bucket_index], edges[bucket_index + 1]
        if end <= start:
            continue
        bucket = replay.iloc[start:end]
        if bucket.empty:
            continue
        turnover = _numeric_column(bucket, "strict_mean_one_way_turnover")
        corr = _numeric_column(bucket, "corr_to_existing_max")
        gap = _numeric_column(bucket, "gap_score")
        rows.append(
            {
                "score_column": score_column,
                "bucket_rank": bucket_index + 1,
                "bucket_order": "descending_top_first" if descending else "ascending_top_first",
                "row_count": int(len(bucket)),
                "score_min": round(float(bucket[score_column].min()), 6),
                "score_max": round(float(bucket[score_column].max()), 6),
                "score_mean": round(float(bucket[score_column].mean()), 6),
                "strict_pass_rate": round(float(bucket["strict_pass"].astype(bool).mean()), 6),
                "replay_pass_rate": round(float(bucket["replay_pass"].astype(bool).mean()), 6),
                "non_gap_replay_pass_rate": round(float(bucket["non_gap_replay_pass"].astype(bool).mean()), 6),
                "cost_survival_rate": round(float(bucket.get("cost_survives", pd.Series(False, index=bucket.index)).astype(bool).mean()), 6),
                "turnover_survival_rate": round(float((turnover <= 0.75).fillna(False).mean()), 6),
                "gap_share": round(float(gap.fillna(0.0).clip(0.0, 1.0).mean()), 6),
                "low_corr_share": round(float((corr <= 0.80).fillna(False).mean()), 6),
                "generator_counts_json": json.dumps(bucket["generator_name"].value_counts().to_dict(), ensure_ascii=False, sort_keys=True),
            }
        )
    return pd.DataFrame(rows)


def _numeric_column(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _score_lift(frame: pd.DataFrame, *, score_column: str, target: str = "non_gap_replay_pass") -> dict[str, Any]:
    if score_column not in frame.columns or target not in frame.columns:
        return {"status": "missing_column", "score_column": score_column, "target": target}
    replay = frame[frame["replay_attempted"].astype(bool)].copy()
    replay = replay[pd.to_numeric(replay[score_column], errors="coerce").notna()].copy()
    if replay.empty:
        return {"status": "no_replay_rows", "score_column": score_column, "target": target}
    replay[score_column] = pd.to_numeric(replay[score_column], errors="coerce")
    replay = replay.sort_values(score_column, ascending=False)
    y = replay[target].astype(bool).to_numpy()
    baseline = float(y.mean()) if len(y) else 0.0
    out: dict[str, Any] = {
        "status": "ok",
        "score_column": score_column,
        "target": target,
        "replay_rows": int(len(y)),
        "baseline_pass_rate": round(baseline, 6),
    }
    for share in (0.05, 0.10, 0.20):
        n = max(1, int(math.ceil(len(replay) * share)))
        rate = float(y[:n].mean()) if n else 0.0
        out[f"top_{int(share * 100)}pct_pass_rate"] = round(rate, 6)
        out[f"top_{int(share * 100)}pct_lift"] = round(rate / baseline, 6) if baseline > 0 else None
    return out


def _decile_trend(table: pd.DataFrame, *, metric: str = "non_gap_replay_pass_rate") -> dict[str, Any]:
    if table.empty or metric not in table.columns:
        return {"status": "no_table", "metric": metric}
    x = pd.to_numeric(table["bucket_rank"], errors="coerce")
    y = pd.to_numeric(table[metric], errors="coerce")
    valid = x.notna() & y.notna()
    if valid.sum() < 3:
        return {"status": "insufficient_buckets", "metric": metric}
    corr = x[valid].corr(y[valid], method="spearman")
    # Buckets are descending top-first, so a useful score should have negative
    # correlation between bucket rank and pass rate.
    return {
        "status": "ok",
        "metric": metric,
        "spearman_bucket_rank_to_metric": round(float(corr), 6) if pd.notna(corr) else None,
        "top_bucket_metric": round(float(y[valid].iloc[0]), 6),
        "bottom_bucket_metric": round(float(y[valid].iloc[-1]), 6),
        "top_minus_bottom": round(float(y[valid].iloc[0] - y[valid].iloc[-1]), 6),
    }


def build_replay_ranker_calibration(
    scored_candidates: pd.DataFrame,
    *,
    score_columns: list[str] | None = None,
    bucket_count: int = 10,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    score_columns = score_columns or [
        "p_non_gap_replay",
        "p_replay",
        "selection_score",
        "cheap_backtest_fitness",
        "cheap_backtest_rank_ic",
        "cheap_backtest_sharpe",
        "pure_rl_score",
    ]
    tables: list[pd.DataFrame] = []
    lifts: dict[str, Any] = {}
    trends: dict[str, Any] = {}
    for score_column in score_columns:
        if score_column not in scored_candidates.columns:
            continue
        table = _score_bucket_table(scored_candidates, score_column=score_column, bucket_count=bucket_count)
        if not table.empty:
            tables.append(table)
            trends[score_column] = _decile_trend(table)
        lifts[score_column] = _score_lift(scored_candidates, score_column=score_column)
    calibration_table = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
    replay = scored_candidates[scored_candidates["replay_attempted"].astype(bool)]
    strict_pass = replay[replay["strict_pass"].astype(bool)] if not replay.empty else replay
    strict_non_gap = strict_pass[~strict_pass.get("gap_score", pd.Series(0.0, index=strict_pass.index)).astype(float).astype(bool)]
    report = {
        "version": REPLAY_RANKER_VERSION,
        "status": "completed",
        "sample": {
            "candidate_rows": int(len(scored_candidates)),
            "replay_attempted_rows": int(len(replay)),
            "replay_pass_rows": int(replay["replay_pass"].astype(bool).sum()) if not replay.empty else 0,
            "non_gap_replay_pass_rows": int(replay["non_gap_replay_pass"].astype(bool).sum()) if not replay.empty else 0,
            "strict_pass_rows": int(replay["strict_pass"].astype(bool).sum()) if not replay.empty else 0,
            "non_gap_strict_pass_rows": int(len(strict_non_gap)),
        },
        "score_lifts": lifts,
        "decile_trends": trends,
        "pure_rl_control_status": "premature_shadow_diagnostic_not_formal_ablation",
        "calibration_warning": (
            "Final-model score columns are trained on this replay sample; decision-grade calibration still requires fresh replay. "
            "Use grouped OOF/seed/lane holdout metrics from replay_ranker_report.json as the less-biased internal check."
        ),
    }
    return calibration_table, report
