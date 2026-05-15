from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _load_recent_quarter_market_panel,
    _signal_evaluation_frame,
    _tradable_daily_ic_spread_turnover_frame,
    _tradable_signal_work_frame,
    evaluate_panel_expression,
)
from our_system_phase2.services.variation import (
    canonicalize_expression_light,
    extract_structural_skeleton,
)


DEFAULT_PHASE3E_CLUSTERED_ROWS = Path(
    "reports/phase3e_official_s21_s24_company_20260514/phase3E_official_s21_s24_global_clustered_rows.json"
)
DEFAULT_PHASE3F_CLUSTERED_ROWS = Path(
    "reports/phase3f_smoke_aggregate_company_20260514/phase3F_smoke_global_clustered_rows.json"
)
DEFAULT_PHASE3E_BASELINE = Path(
    "src/our_system_phase2/runtime/baselines/phase3E_cumulative_deployable_clusters_20260514.json"
)
DEFAULT_OUTPUT_ROOT = Path("reports/phase3g_signal_vector_audit_20260514")
DEFAULT_VECTOR_ROOT = Path("runtime/phase3g_signal_vectors")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _stable_hash(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _expr_hash(expression: str) -> str:
    return _stable_hash(canonicalize_expression_light(expression), 20)


def _cluster_id(row: dict[str, Any]) -> str:
    return str(row.get("global_signal_cluster_id") or row.get("signal_cluster_id") or "cluster_missing")


def _scope(row: dict[str, Any]) -> str:
    return str(row.get("phase3g_source_scope") or row.get("source_scope") or "unknown")


def _row_id(row: dict[str, Any], fallback: int) -> str:
    candidate = str(row.get("candidate_id") or "")
    expression = str(row.get("expression") or row.get("representative_expression") or "")
    return candidate or f"row_{fallback}_{_expr_hash(expression)}"


def _fields(expression: str) -> list[str]:
    return re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression or "")


def _operators(expression: str) -> list[str]:
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*(?=\()", expression or "")


def _field_group(field: str) -> str:
    name = field.lower().lstrip("$")
    if name in {"close", "open", "high", "low", "vwap", "price_pos"}:
        return "price"
    if name in {"amount", "volume", "turnover", "turnover_rate", "amtm", "vrat"}:
        return "flow_liquidity"
    if "vol" in name or name in {"ret", "returns", "daily_ret"}:
        return "volatility_return"
    if name in {"mbrd", "pldn", "arat", "crowding", "rps_score", "money_flow"}:
        return "state_style"
    return name


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


def _symbolic_similarity(left_expression: str, right_expression: str) -> float:
    left = canonicalize_expression_light(left_expression)
    right = canonicalize_expression_light(right_expression)
    exact = 1.0 if left == right else 0.0
    ast = 1.0 if extract_structural_skeleton(left) == extract_structural_skeleton(right) else 0.0
    field_overlap = _jaccard({_field_group(field) for field in _fields(left)}, {_field_group(field) for field in _fields(right)})
    operator_overlap = _jaccard(set(_operators(left)), set(_operators(right)))
    return max(exact, 0.55 * ast + 0.20 * field_overlap + 0.25 * operator_overlap)


def _load_candidate_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        payload = _read_json(path)
        source_scope = "phase3f" if "phase3f" in path.name.lower() else "phase3e"
        for row in payload.get("rows", []):
            expression = str(row.get("expression") or "")
            if not expression:
                continue
            item = dict(row)
            item["phase3g_source_scope"] = source_scope
            item["phase3g_final_cluster_id"] = _cluster_id(row)
            item["phase3g_row_kind"] = "audited_candidate"
            rows.append(item)
    return rows


def _load_registry_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    raw_rows = payload.get("deployable_representatives") or payload.get("cluster_registry") or []
    rows = []
    for row in raw_rows:
        expression = str(row.get("representative_expression") or row.get("expression") or "")
        if not expression:
            continue
        item = dict(row)
        item["expression"] = expression
        item["phase3g_source_scope"] = "registry_134"
        item["phase3g_final_cluster_id"] = str(row.get("cluster_id") or "registry_cluster_missing")
        item["phase3g_row_kind"] = "registry_representative"
        rows.append(item)
    return rows


def _dedupe_by_expression(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out = []
    for row in rows:
        key = _expr_hash(str(row.get("expression") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _sample_signal_index(signal_frame: pd.DataFrame, evaluation_start: pd.Timestamp, evaluation_end: pd.Timestamp, *, sample_size: int) -> pd.MultiIndex:
    mask = (signal_frame["date"] >= evaluation_start) & (signal_frame["date"] <= evaluation_end)
    index_frame = signal_frame.loc[mask, ["date", "code"]].copy()
    index_frame["key"] = index_frame["date"].astype(str) + "::" + index_frame["code"].astype(str)
    index_frame["hash"] = index_frame["key"].map(lambda value: int(hashlib.sha1(value.encode("utf-8")).hexdigest()[:16], 16))
    index_frame = index_frame.sort_values(["hash", "date", "code"]).head(max(1, int(sample_size)))
    index_frame = index_frame.sort_values(["date", "code"])
    return pd.MultiIndex.from_frame(index_frame[["date", "code"]])


def _normalize_vector(values: np.ndarray) -> np.ndarray:
    array = values.astype(np.float32, copy=False)
    finite = np.isfinite(array)
    if not finite.any():
        return np.zeros_like(array, dtype=np.float32)
    mean = float(array[finite].mean())
    std = float(array[finite].std())
    if not math.isfinite(std) or std <= 1e-12:
        out = np.zeros_like(array, dtype=np.float32)
        out[finite] = array[finite] - mean
        return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    out = (array - mean) / std
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


@dataclass
class VectorBuildResult:
    metadata: list[dict[str, Any]]
    signal_vectors: np.ndarray
    daily_ic_vectors: np.ndarray
    daily_return_vectors: np.ndarray
    vector_errors: list[dict[str, Any]]
    evaluation_start: str
    evaluation_end: str
    sample_size: int


def _build_vectors(
    rows: list[dict[str, Any]],
    *,
    dataset_path: Path,
    recent_quarter_window_count: int,
    recent_warmup_days: int,
    signal_sample_size: int,
    top_bottom_quantile: float,
) -> VectorBuildResult:
    frame, evaluation_start, evaluation_end = _load_recent_quarter_market_panel(
        dataset_path,
        quarter_window_count=recent_quarter_window_count,
        warmup_days=recent_warmup_days,
    )
    signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
    sample_index = _sample_signal_index(
        signal_frame,
        evaluation_start,
        evaluation_end,
        sample_size=signal_sample_size,
    )
    dates = sorted(pd.to_datetime(frame.loc[(frame["date"] >= evaluation_start) & (frame["date"] <= evaluation_end), "date"]).dropna().unique())
    date_index = pd.Index(dates, name="date")

    expression_cache: dict[str, pd.Series] = {}
    metadata: list[dict[str, Any]] = []
    signal_vectors: list[np.ndarray] = []
    daily_ic_vectors: list[np.ndarray] = []
    daily_return_vectors: list[np.ndarray] = []
    errors: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        expression = str(row.get("expression") or "")
        vector_id = _expr_hash(expression)
        try:
            signal = evaluate_panel_expression(
                signal_frame,
                expression,
                cache=expression_cache,
                field_lags=signal_clock_report["field_lags"],
            )
            ranked = signal.groupby(signal_frame["date"]).rank(pct=True)
            mask = (signal_frame["date"] >= evaluation_start) & (signal_frame["date"] <= evaluation_end)
            index_frame = signal_frame.loc[mask, ["date", "code"]]
            ranked_recent = pd.to_numeric(ranked.loc[mask], errors="coerce")
            ranked_recent.index = pd.MultiIndex.from_frame(index_frame)
            sampled = ranked_recent.reindex(sample_index)
            signal_vector = _normalize_vector(sampled.to_numpy(dtype=np.float32))

            work, _tradability_masks = _tradable_signal_work_frame(
                frame,
                signal,
                horizon_days=1,
                feature_lag_days=0,
                evaluation_start_date=evaluation_start,
                evaluation_end_date=evaluation_end,
                field_lags=signal_clock_report["field_lags"],
            )
            daily = _tradable_daily_ic_spread_turnover_frame(work, top_bottom_quantile=top_bottom_quantile)
            if daily.empty:
                daily_ic = np.zeros(len(date_index), dtype=np.float32)
                daily_return = np.zeros(len(date_index), dtype=np.float32)
            else:
                daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
                daily = daily.set_index("date").sort_index()
                daily_ic = _normalize_vector(pd.to_numeric(daily["rank_ic"], errors="coerce").reindex(date_index).to_numpy(dtype=np.float32))
                daily_return = _normalize_vector(
                    pd.to_numeric(daily["long_short_return"], errors="coerce").reindex(date_index).to_numpy(dtype=np.float32)
                )

            metadata.append(
                {
                    "vector_id": vector_id,
                    "row_id": _row_id(row, index),
                    "row_kind": row.get("phase3g_row_kind"),
                    "source_scope": row.get("phase3g_source_scope"),
                    "final_cluster_id": row.get("phase3g_final_cluster_id"),
                    "candidate_id": row.get("candidate_id"),
                    "ablation_arm": row.get("ablation_arm"),
                    "source_lane": row.get("phase3_budget_bucket") or row.get("proof_variant") or row.get("source_lane"),
                    "expression": expression,
                    "expression_hash": vector_id,
                    "signal_nonzero_count": int(np.count_nonzero(signal_vector)),
                    "daily_ic_nonzero_count": int(np.count_nonzero(daily_ic)),
                    "daily_return_nonzero_count": int(np.count_nonzero(daily_return)),
                }
            )
            signal_vectors.append(signal_vector)
            daily_ic_vectors.append(daily_ic)
            daily_return_vectors.append(daily_return)
        except Exception as exc:
            errors.append(
                {
                    "row_id": _row_id(row, index),
                    "expression": expression,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:500],
                }
            )

    return VectorBuildResult(
        metadata=metadata,
        signal_vectors=np.vstack(signal_vectors).astype(np.float32) if signal_vectors else np.zeros((0, len(sample_index)), dtype=np.float32),
        daily_ic_vectors=np.vstack(daily_ic_vectors).astype(np.float32) if daily_ic_vectors else np.zeros((0, len(date_index)), dtype=np.float32),
        daily_return_vectors=np.vstack(daily_return_vectors).astype(np.float32) if daily_return_vectors else np.zeros((0, len(date_index)), dtype=np.float32),
        vector_errors=errors,
        evaluation_start=evaluation_start.date().isoformat(),
        evaluation_end=evaluation_end.date().isoformat(),
        sample_size=int(len(sample_index)),
    )


def _corr_matrix(vectors: np.ndarray) -> np.ndarray:
    if vectors.size == 0:
        return np.zeros((0, 0), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1)
    safe = np.where(norms > 1e-12, norms, 1.0).astype(np.float32)
    normalized = vectors / safe[:, None]
    return np.clip(normalized @ normalized.T, -1.0, 1.0).astype(np.float32)


def _auc(labels: list[int], scores: list[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    order = np.argsort(np.asarray(scores, dtype=float))
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1, dtype=float)
    rank_sum_pos = float(ranks[np.asarray(labels, dtype=bool)].sum())
    auc = (rank_sum_pos - positives * (positives + 1) / 2.0) / (positives * negatives)
    return round(float(auc), 6)


def _pair_metrics(
    metadata: list[dict[str, Any]],
    score_matrix: np.ndarray,
    *,
    threshold: float,
    score_name: str,
) -> dict[str, Any]:
    labels: list[int] = []
    scores: list[float] = []
    scopes = [str(row.get("source_scope") or "") for row in metadata]
    clusters = [str(row.get("final_cluster_id") or "") for row in metadata]
    for i in range(len(metadata)):
        for j in range(i + 1, len(metadata)):
            if scopes[i] != scopes[j] or scopes[i] == "registry_134":
                continue
            if clusters[i].startswith("cluster_missing") or clusters[j].startswith("cluster_missing"):
                continue
            labels.append(1 if clusters[i] == clusters[j] else 0)
            scores.append(abs(float(score_matrix[i, j])))
    positives = sum(labels)
    above = [index for index, score in enumerate(scores) if score >= threshold]
    true_above = sum(labels[index] for index in above)
    false_above = len(above) - true_above
    negatives = len(labels) - positives
    return {
        "score_name": score_name,
        "pair_count": len(labels),
        "positive_same_cluster_pairs": positives,
        "auc": _auc(labels, scores),
        "threshold": float(threshold),
        "precision_at_threshold": round(true_above / len(above), 6) if above else None,
        "recall_at_threshold": round(true_above / positives, 6) if positives else None,
        "false_positive_rate_at_threshold": round(false_above / negatives, 6) if negatives else None,
        "above_threshold_pair_count": len(above),
    }


def _symbolic_pair_metrics(metadata: list[dict[str, Any]], *, threshold: float) -> dict[str, Any]:
    labels: list[int] = []
    scores: list[float] = []
    scopes = [str(row.get("source_scope") or "") for row in metadata]
    clusters = [str(row.get("final_cluster_id") or "") for row in metadata]
    expressions = [str(row.get("expression") or "") for row in metadata]
    for i in range(len(metadata)):
        for j in range(i + 1, len(metadata)):
            if scopes[i] != scopes[j] or scopes[i] == "registry_134":
                continue
            labels.append(1 if clusters[i] == clusters[j] else 0)
            scores.append(_symbolic_similarity(expressions[i], expressions[j]))
    positives = sum(labels)
    above = [index for index, score in enumerate(scores) if score >= threshold]
    true_above = sum(labels[index] for index in above)
    false_above = len(above) - true_above
    negatives = len(labels) - positives
    return {
        "score_name": "symbolic_ast_field_operator_proxy",
        "pair_count": len(labels),
        "positive_same_cluster_pairs": positives,
        "auc": _auc(labels, scores),
        "threshold": float(threshold),
        "precision_at_threshold": round(true_above / len(above), 6) if above else None,
        "recall_at_threshold": round(true_above / positives, 6) if positives else None,
        "false_positive_rate_at_threshold": round(false_above / negatives, 6) if negatives else None,
        "above_threshold_pair_count": len(above),
    }


def _cluster_detection(
    metadata: list[dict[str, Any]],
    score_matrix: np.ndarray,
    *,
    cluster_id: str,
    threshold: float,
    scope_filter: str | None = None,
) -> dict[str, Any]:
    indices = [
        index
        for index, row in enumerate(metadata)
        if str(row.get("final_cluster_id")) == cluster_id and (scope_filter is None or str(row.get("source_scope")) == scope_filter)
    ]
    same_pairs = 0
    same_hits = 0
    cross_pairs = 0
    cross_false = 0
    for pos, i in enumerate(indices):
        for j in indices[pos + 1 :]:
            same_pairs += 1
            if abs(float(score_matrix[i, j])) >= threshold:
                same_hits += 1
        for j, row in enumerate(metadata):
            if j == i:
                continue
            if scope_filter is not None and str(row.get("source_scope")) != scope_filter:
                continue
            if str(row.get("final_cluster_id")) == cluster_id:
                continue
            cross_pairs += 1
            if abs(float(score_matrix[i, j])) >= threshold:
                cross_false += 1
    return {
        "cluster_id": cluster_id,
        "scope_filter": scope_filter,
        "member_count": len(indices),
        "threshold": float(threshold),
        "same_cluster_pair_recall": round(same_hits / same_pairs, 6) if same_pairs else None,
        "cross_cluster_false_positive_rate": round(cross_false / cross_pairs, 6) if cross_pairs else None,
        "same_pairs": same_pairs,
        "cross_pairs": cross_pairs,
    }


def _greedy_vector_clusters(metadata: list[dict[str, Any]], score_matrix: np.ndarray, *, threshold: float, scope: str) -> tuple[list[str], dict[str, Any]]:
    indices = [index for index, row in enumerate(metadata) if str(row.get("source_scope")) == scope]
    assigned: dict[int, str] = {}
    representatives: list[int] = []
    for index in indices:
        best = None
        best_corr = 0.0
        for rep in representatives:
            corr = abs(float(score_matrix[index, rep]))
            if corr > best_corr:
                best_corr = corr
                best = rep
        if best is not None and best_corr >= threshold:
            assigned[index] = assigned[best]
        else:
            cluster_id = f"vec_{len(representatives) + 1:03d}"
            representatives.append(index)
            assigned[index] = cluster_id
    out = [""] * len(metadata)
    for index, cluster_id in assigned.items():
        out[index] = cluster_id
    cluster_to_replay: dict[str, Counter[str]] = defaultdict(Counter)
    for index in indices:
        cluster_to_replay[out[index]][str(metadata[index].get("final_cluster_id"))] += 1
    purities = []
    rows = []
    for vector_cluster, counter in sorted(cluster_to_replay.items()):
        total = sum(counter.values())
        top_cluster, top_count = counter.most_common(1)[0]
        purity = top_count / max(1, total)
        purities.append(purity)
        rows.append(
            {
                "scope": scope,
                "vector_cluster_id": vector_cluster,
                "member_count": total,
                "top_replay_cluster": top_cluster,
                "top_replay_cluster_count": top_count,
                "purity": round(purity, 6),
            }
        )
    report = {
        "scope": scope,
        "threshold": float(threshold),
        "vector_cluster_count": len(cluster_to_replay),
        "mean_cluster_purity": round(float(np.mean(purities)), 6) if purities else None,
        "weighted_cluster_purity": round(
            float(sum(row["purity"] * row["member_count"] for row in rows) / max(1, sum(row["member_count"] for row in rows))),
            6,
        )
        if rows
        else None,
    }
    return out, {"summary": report, "rows": rows}


def _queue_corr_report(metadata: list[dict[str, Any]], score_matrix: np.ndarray) -> list[dict[str, Any]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(metadata):
        if str(row.get("row_kind")) != "audited_candidate":
            continue
        arm = str(row.get("ablation_arm") or "unknown_arm")
        scope = str(row.get("source_scope") or "unknown_scope")
        groups[f"{scope}::{arm}"].append(index)
    out = []
    for group_id, indices in sorted(groups.items()):
        values = []
        for pos, i in enumerate(indices):
            for j in indices[pos + 1 :]:
                values.append(abs(float(score_matrix[i, j])))
        out.append(
            {
                "scope_arm": group_id,
                "candidate_count": len(indices),
                "pair_count": len(values),
                "mean_abs_corr": round(float(np.mean(values)), 6) if values else None,
                "median_abs_corr": round(float(np.median(values)), 6) if values else None,
                "max_abs_corr": round(float(np.max(values)), 6) if values else None,
            }
        )
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8")


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Phase3G Signal Vector Audit",
        "",
        "## Decision",
        "",
        f"- decision: `{report['decision']}`",
        f"- experiment_id: `{report['experiment_id']}`",
        f"- candidate_rows: `{report['candidate_row_count']}`",
        f"- registry_rows: `{report['registry_row_count']}`",
        f"- vector_errors: `{report['vector_error_count']}`",
        "",
        "## Calibration",
        "",
        "| score | AUC | precision@threshold | recall@threshold | FPR@threshold | pairs |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in report["pair_metrics"]:
        lines.append(
            f"| {item['score_name']} | {item.get('auc')} | {item.get('precision_at_threshold')} | "
            f"{item.get('recall_at_threshold')} | {item.get('false_positive_rate_at_threshold')} | {item.get('pair_count')} |"
        )
    lines.extend(
        [
            "",
            "## Cluster Focus",
            "",
            "| score | cluster | scope | members | recall | false positive rate |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    for score_name, rows in report["cluster_detection"].items():
        for item in rows:
            lines.append(
                f"| {score_name} | {item['cluster_id']} | {item.get('scope_filter')} | {item['member_count']} | "
                f"{item.get('same_cluster_pair_recall')} | {item.get('cross_cluster_false_positive_rate')} |"
            )
    lines.extend(
        [
            "",
            "## Findings",
            "",
        ]
    )
    for finding in report["findings"]:
        lines.append(f"- {finding}")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
        ]
    )
    for key, value in report["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Phase3G pre-replay signal/return vector cluster observability.")
    parser.add_argument("--phase3e-clustered-rows", type=Path, default=DEFAULT_PHASE3E_CLUSTERED_ROWS)
    parser.add_argument("--phase3f-clustered-rows", type=Path, default=DEFAULT_PHASE3F_CLUSTERED_ROWS)
    parser.add_argument("--baseline-json", type=Path, default=DEFAULT_PHASE3E_BASELINE)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_REAL_MARKET_DATASET_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--vector-root", type=Path, default=DEFAULT_VECTOR_ROOT)
    parser.add_argument("--recent-quarter-window-count", type=int, default=1)
    parser.add_argument("--recent-warmup-days", type=int, default=90)
    parser.add_argument("--signal-sample-size", type=int, default=5000)
    parser.add_argument("--top-bottom-quantile", type=float, default=0.02)
    parser.add_argument("--corr-threshold", type=float, default=0.80)
    parser.add_argument("--candidate-limit", type=int, default=0)
    args = parser.parse_args()

    candidate_rows = _load_candidate_rows([args.phase3e_clustered_rows, args.phase3f_clustered_rows])
    if args.candidate_limit > 0:
        candidate_rows = candidate_rows[: int(args.candidate_limit)]
    registry_rows = _load_registry_rows(args.baseline_json)
    analysis_rows = [*registry_rows, *candidate_rows]
    build_rows = _dedupe_by_expression(analysis_rows)

    result = _build_vectors(
        build_rows,
        dataset_path=args.dataset_path,
        recent_quarter_window_count=args.recent_quarter_window_count,
        recent_warmup_days=args.recent_warmup_days,
        signal_sample_size=args.signal_sample_size,
        top_bottom_quantile=args.top_bottom_quantile,
    )
    unique_metadata = result.metadata
    vector_index = {str(row["vector_id"]): index for index, row in enumerate(unique_metadata)}
    expanded_metadata: list[dict[str, Any]] = []
    expanded_signal_vectors: list[np.ndarray] = []
    expanded_daily_ic_vectors: list[np.ndarray] = []
    expanded_daily_return_vectors: list[np.ndarray] = []
    missing_vector_rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(analysis_rows):
        expression = str(row.get("expression") or row.get("representative_expression") or "")
        vector_id = _expr_hash(expression)
        index = vector_index.get(vector_id)
        if index is None:
            missing_vector_rows.append(
                {
                    "row_id": _row_id(row, row_index),
                    "vector_id": vector_id,
                    "expression": expression,
                    "reason": "vector_build_missing",
                }
            )
            continue
        expanded_metadata.append(
            {
                "vector_id": vector_id,
                "row_id": _row_id(row, row_index),
                "row_kind": row.get("phase3g_row_kind"),
                "source_scope": row.get("phase3g_source_scope"),
                "final_cluster_id": row.get("phase3g_final_cluster_id"),
                "candidate_id": row.get("candidate_id"),
                "ablation_arm": row.get("ablation_arm"),
                "source_lane": row.get("phase3_budget_bucket") or row.get("proof_variant") or row.get("source_lane"),
                "expression": expression,
                "expression_hash": vector_id,
                "dedup_vector_source_index": index,
                "signal_nonzero_count": unique_metadata[index].get("signal_nonzero_count"),
                "daily_ic_nonzero_count": unique_metadata[index].get("daily_ic_nonzero_count"),
                "daily_return_nonzero_count": unique_metadata[index].get("daily_return_nonzero_count"),
            }
        )
        expanded_signal_vectors.append(result.signal_vectors[index])
        expanded_daily_ic_vectors.append(result.daily_ic_vectors[index])
        expanded_daily_return_vectors.append(result.daily_return_vectors[index])

    metadata = expanded_metadata
    signal_vectors = np.vstack(expanded_signal_vectors).astype(np.float32) if expanded_signal_vectors else np.zeros((0, result.signal_vectors.shape[1]), dtype=np.float32)
    daily_ic_vectors = np.vstack(expanded_daily_ic_vectors).astype(np.float32) if expanded_daily_ic_vectors else np.zeros((0, result.daily_ic_vectors.shape[1]), dtype=np.float32)
    daily_return_vectors = (
        np.vstack(expanded_daily_return_vectors).astype(np.float32)
        if expanded_daily_return_vectors
        else np.zeros((0, result.daily_return_vectors.shape[1]), dtype=np.float32)
    )
    args.vector_root.mkdir(parents=True, exist_ok=True)
    args.output_root.mkdir(parents=True, exist_ok=True)

    signal_corr = _corr_matrix(signal_vectors)
    ic_corr = _corr_matrix(daily_ic_vectors)
    return_corr = _corr_matrix(daily_return_vectors)

    pair_metrics = [
        _pair_metrics(metadata, signal_corr, threshold=args.corr_threshold, score_name="sampled_signal_vector_corr"),
        _pair_metrics(metadata, ic_corr, threshold=args.corr_threshold, score_name="daily_rank_ic_vector_corr"),
        _pair_metrics(metadata, return_corr, threshold=args.corr_threshold, score_name="daily_long_short_return_vector_corr"),
        _symbolic_pair_metrics(metadata, threshold=args.corr_threshold),
    ]

    vector_cluster_assignments = {}
    vector_cluster_reports = {}
    vector_cluster_rows = []
    for scope in sorted({str(row.get("source_scope")) for row in metadata if str(row.get("source_scope")) != "registry_134"}):
        assignments, report = _greedy_vector_clusters(metadata, signal_corr, threshold=args.corr_threshold, scope=scope)
        vector_cluster_assignments[scope] = assignments
        vector_cluster_reports[scope] = report["summary"]
        vector_cluster_rows.extend(report["rows"])

    cluster_detection = {
        "sampled_signal_vector_corr": [
            _cluster_detection(metadata, signal_corr, cluster_id="cluster_001", threshold=args.corr_threshold, scope_filter="phase3f"),
            _cluster_detection(metadata, signal_corr, cluster_id="cluster_003", threshold=args.corr_threshold, scope_filter="phase3f"),
        ],
        "daily_long_short_return_vector_corr": [
            _cluster_detection(metadata, return_corr, cluster_id="cluster_001", threshold=args.corr_threshold, scope_filter="phase3f"),
            _cluster_detection(metadata, return_corr, cluster_id="cluster_003", threshold=args.corr_threshold, scope_filter="phase3f"),
        ],
    }
    queue_corr = _queue_corr_report(metadata, signal_corr)

    vector_npz = args.vector_root / "phase3g_signal_vectors_20260514.npz"
    np.savez_compressed(
        vector_npz,
        signal_vectors=signal_vectors,
        daily_ic_vectors=daily_ic_vectors,
        daily_return_vectors=daily_return_vectors,
    )
    metadata_path = args.vector_root / "vector_metadata.parquet"
    pd.DataFrame(metadata).to_parquet(metadata_path, index=False)
    unique_metadata_path = args.vector_root / "unique_vector_metadata.parquet"
    pd.DataFrame(unique_metadata).to_parquet(unique_metadata_path, index=False)
    errors_path = args.output_root / "phase3g_vector_errors.csv"
    _write_csv(errors_path, [*result.vector_errors, *missing_vector_rows])
    pair_metrics_path = args.output_root / "phase3g_pair_metrics.csv"
    _write_csv(pair_metrics_path, pair_metrics)
    vector_clusters_path = args.output_root / "phase3g_vector_cluster_purity.csv"
    _write_csv(vector_clusters_path, vector_cluster_rows)
    queue_corr_path = args.output_root / "phase3g_queue_vector_corr.csv"
    _write_csv(queue_corr_path, queue_corr)

    best_vector_auc = max(
        [item.get("auc") or 0.0 for item in pair_metrics if item["score_name"] != "symbolic_ast_field_operator_proxy"],
        default=0.0,
    )
    best_precision = max(
        [item.get("precision_at_threshold") or 0.0 for item in pair_metrics if item["score_name"] != "symbolic_ast_field_operator_proxy"],
        default=0.0,
    )
    symbolic_auc = next((item.get("auc") for item in pair_metrics if item["score_name"] == "symbolic_ast_field_operator_proxy"), None)
    decision = "PASS_VECTOR_PROXY_GATE" if best_vector_auc >= 0.75 or best_precision >= 0.70 else "HOLD_RESEARCH"
    findings = [
        "Phase3G is a no-run audit: it does not generate new formulas or run replay.",
        f"Best vector AUC={best_vector_auc}; best precision@{args.corr_threshold}={best_precision}.",
        f"Symbolic proxy AUC={symbolic_auc}; vector proxy should replace symbolic proxy only if materially stronger.",
        "Current post-replay cluster labels are signal-correlation clusters, so pre-replay sampled signal vectors are the closest available observable proxy.",
    ]
    if decision != "PASS_VECTOR_PROXY_GATE":
        findings.append("Do not implement E3V2 official selection until vector proxy calibration improves or a better cheap-return vector is added.")
    else:
        findings.append("E3V2 vector-diversified selector is eligible for selector-only dry run.")

    report = {
        "experiment_id": "20260514_phase3g_signal_vector_audit",
        "objective": "Test whether pre-replay signal/return vectors predict final replay signal clusters better than symbolic proxy.",
        "decision": decision,
        "dataset_path": str(args.dataset_path),
        "phase3e_clustered_rows": str(args.phase3e_clustered_rows),
        "phase3f_clustered_rows": str(args.phase3f_clustered_rows),
        "baseline_json": str(args.baseline_json),
        "candidate_row_count": len(candidate_rows),
        "registry_row_count": len(registry_rows),
        "deduped_vector_row_count": len(unique_metadata),
        "expanded_vector_row_count": len(metadata),
        "vector_error_count": len(result.vector_errors) + len(missing_vector_rows),
        "evaluation_start": result.evaluation_start,
        "evaluation_end": result.evaluation_end,
        "signal_sample_size": result.sample_size,
        "corr_threshold": float(args.corr_threshold),
        "pair_metrics": pair_metrics,
        "cluster_detection": cluster_detection,
        "vector_cluster_reports": vector_cluster_reports,
        "findings": findings,
        "outputs": {
            "summary_json": str(args.output_root / "phase3g_signal_vector_audit_summary.json"),
            "summary_md": str(args.output_root / "PHASE3G_SIGNAL_VECTOR_AUDIT_2026-05-14.md"),
            "vectors_npz": str(vector_npz),
            "metadata_parquet": str(metadata_path),
            "unique_metadata_parquet": str(unique_metadata_path),
            "pair_metrics_csv": str(pair_metrics_path),
            "vector_cluster_purity_csv": str(vector_clusters_path),
            "queue_vector_corr_csv": str(queue_corr_path),
            "errors_csv": str(errors_path),
        },
        "reproducibility": {
            "mode": "no_run_historical_audit",
            "new_search_started": False,
            "sample_index_policy": "deterministic_sha1_date_code_lowest_hashes",
        },
    }
    _write_json(args.output_root / "phase3g_signal_vector_audit_summary.json", report)
    (args.output_root / "PHASE3G_SIGNAL_VECTOR_AUDIT_2026-05-14.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"decision": decision, "outputs": report["outputs"], "pair_metrics": pair_metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
