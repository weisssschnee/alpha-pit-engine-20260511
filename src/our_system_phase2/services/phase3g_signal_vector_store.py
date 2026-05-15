from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH
from our_system_phase2.services.real_market_validation import (
    SIGNAL_CLOCK_AFTER_OPEN,
    _load_recent_quarter_market_panel,
    _signal_evaluation_frame,
    evaluate_panel_expression,
)
from our_system_phase2.services.variation import canonicalize_expression_light


PHASE3G_SIGNAL_VECTOR_VERSION = "phase3g-sampled-signal-vector-v1-2026-05-14"
DEFAULT_PHASE3G_VECTOR_NPZ = Path("runtime/phase3g_signal_vectors/phase3g_signal_vectors_20260514.npz")
DEFAULT_PHASE3G_VECTOR_METADATA = Path("runtime/phase3g_signal_vectors/vector_metadata.parquet")
DEFAULT_PHASE3G_SAMPLE_SIZE = 5000
DEFAULT_PHASE3G_RECENT_QUARTER_WINDOW_COUNT = 1
DEFAULT_PHASE3G_RECENT_WARMUP_DAYS = 90
DEFAULT_PHASE3G_SIGNAL_CORR_THRESHOLD = 0.80


def expression_vector_id(expression: str) -> str:
    canonical = canonicalize_expression_light(expression or "")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


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


def _corr(left: np.ndarray | None, right: np.ndarray | None) -> float:
    if left is None or right is None or left.size == 0 or right.size == 0:
        return 0.0
    if left.shape != right.shape:
        return 0.0
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if not math.isfinite(denom) or denom <= 1e-12:
        return 0.0
    value = float(np.dot(left, right) / denom)
    return value if math.isfinite(value) else 0.0


def _sample_signal_index(
    signal_frame: pd.DataFrame,
    evaluation_start: pd.Timestamp,
    evaluation_end: pd.Timestamp,
    *,
    sample_size: int,
) -> pd.MultiIndex:
    mask = (signal_frame["date"] >= evaluation_start) & (signal_frame["date"] <= evaluation_end)
    index_frame = signal_frame.loc[mask, ["date", "code"]].copy()
    index_frame["key"] = index_frame["date"].astype(str) + "::" + index_frame["code"].astype(str)
    index_frame["hash"] = index_frame["key"].map(lambda value: int(hashlib.sha1(value.encode("utf-8")).hexdigest()[:16], 16))
    index_frame = index_frame.sort_values(["hash", "date", "code"]).head(max(1, int(sample_size)))
    index_frame = index_frame.sort_values(["date", "code"])
    return pd.MultiIndex.from_frame(index_frame[["date", "code"]])


class Phase3GSignalVectorStore:
    """Pre-replay sampled signal vector store.

    This is a selector-side representation. It deliberately does not read
    candidate replay labels or deployable labels. Frozen registry cluster labels
    are allowed because they are the historical baseline being avoided.
    """

    def __init__(
        self,
        *,
        vector_npz: Path | str = DEFAULT_PHASE3G_VECTOR_NPZ,
        metadata_path: Path | str = DEFAULT_PHASE3G_VECTOR_METADATA,
        dataset_path: Path | str = DEFAULT_REAL_MARKET_DATASET_PATH,
        sample_size: int = DEFAULT_PHASE3G_SAMPLE_SIZE,
        recent_quarter_window_count: int = DEFAULT_PHASE3G_RECENT_QUARTER_WINDOW_COUNT,
        recent_warmup_days: int = DEFAULT_PHASE3G_RECENT_WARMUP_DAYS,
        corr_threshold: float = DEFAULT_PHASE3G_SIGNAL_CORR_THRESHOLD,
    ) -> None:
        self.vector_npz = Path(vector_npz)
        self.metadata_path = Path(metadata_path)
        self.dataset_path = Path(dataset_path)
        self.sample_size = int(sample_size)
        self.recent_quarter_window_count = int(recent_quarter_window_count)
        self.recent_warmup_days = int(recent_warmup_days)
        self.corr_threshold = float(corr_threshold)
        self.version = PHASE3G_SIGNAL_VECTOR_VERSION
        self._vectors_by_id: dict[str, np.ndarray] = {}
        self._metadata_by_id: dict[str, dict[str, Any]] = {}
        self._registry_ids: list[str] = []
        self._registry_vectors: list[np.ndarray] = []
        self._registry_cluster_ids: list[str] = []
        self._runtime_cache: dict[str, np.ndarray] = {}
        self._panel_context: tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], pd.MultiIndex] | None = None
        self._expression_cache: dict[str, pd.Series] = {}
        self._load_artifacts()

    @classmethod
    def default(cls) -> "Phase3GSignalVectorStore":
        return cls()

    def _load_artifacts(self) -> None:
        if not self.vector_npz.exists() or not self.metadata_path.exists():
            return
        payload = np.load(self.vector_npz)
        signal_vectors = payload["signal_vectors"]
        metadata = pd.read_parquet(self.metadata_path).to_dict("records")
        for index, row in enumerate(metadata):
            vector_id = str(row.get("vector_id") or "")
            if not vector_id or index >= len(signal_vectors):
                continue
            vector = signal_vectors[index].astype(np.float32, copy=False)
            self._vectors_by_id.setdefault(vector_id, vector)
            self._metadata_by_id.setdefault(vector_id, row)
            if str(row.get("row_kind")) == "registry_representative" and str(row.get("source_scope")) == "registry_134":
                self._registry_ids.append(vector_id)
                self._registry_vectors.append(vector)
                self._registry_cluster_ids.append(str(row.get("final_cluster_id") or "registry_cluster_missing"))

    def coverage_ready(self) -> bool:
        return bool(self._registry_vectors)

    def vector_for_expression(self, expression: str) -> tuple[np.ndarray | None, dict[str, Any]]:
        vector_id = expression_vector_id(expression)
        if vector_id in self._vectors_by_id:
            return self._vectors_by_id[vector_id], {
                "signal_vector_id": vector_id,
                "signal_vector_source": "phase3g_artifact",
                "signal_vector_error": "",
            }
        if vector_id in self._runtime_cache:
            return self._runtime_cache[vector_id], {
                "signal_vector_id": vector_id,
                "signal_vector_source": "runtime_evaluated",
                "signal_vector_error": "",
            }
        try:
            vector = self._evaluate_expression_vector(expression)
        except Exception as exc:
            return None, {
                "signal_vector_id": vector_id,
                "signal_vector_source": "missing",
                "signal_vector_error": f"{type(exc).__name__}:{str(exc)[:200]}",
            }
        self._runtime_cache[vector_id] = vector
        return vector, {
            "signal_vector_id": vector_id,
            "signal_vector_source": "runtime_evaluated",
            "signal_vector_error": "",
        }

    def _context(self) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], pd.MultiIndex]:
        if self._panel_context is not None:
            return self._panel_context
        frame, evaluation_start, evaluation_end = _load_recent_quarter_market_panel(
            self.dataset_path,
            quarter_window_count=self.recent_quarter_window_count,
            warmup_days=self.recent_warmup_days,
        )
        signal_frame, signal_clock_report = _signal_evaluation_frame(frame, signal_clock=SIGNAL_CLOCK_AFTER_OPEN)
        sample_index = _sample_signal_index(
            signal_frame,
            evaluation_start,
            evaluation_end,
            sample_size=self.sample_size,
        )
        self._panel_context = (frame, signal_frame, signal_clock_report, sample_index)
        return self._panel_context

    def _evaluate_expression_vector(self, expression: str) -> np.ndarray:
        _frame, signal_frame, signal_clock_report, sample_index = self._context()
        signal = evaluate_panel_expression(
            signal_frame,
            expression,
            cache=self._expression_cache,
            field_lags=signal_clock_report["field_lags"],
        )
        ranked = signal.groupby(signal_frame["date"]).rank(pct=True)
        index_frame = signal_frame[["date", "code"]]
        ranked = pd.to_numeric(ranked, errors="coerce")
        ranked.index = pd.MultiIndex.from_frame(index_frame)
        sampled = ranked.reindex(sample_index)
        return _normalize_vector(sampled.to_numpy(dtype=np.float32))

    def registry_similarity(self, expression: str) -> dict[str, Any]:
        vector, meta = self.vector_for_expression(expression)
        if vector is None or not self._registry_vectors:
            return {
                **meta,
                "nearest_134_signal_cluster_id": "",
                "max_corr_to_134_signal_vector": 0.0,
                "mean_topk_corr_to_134_signal_vector": 0.0,
                "known_signal_cluster_id": "",
                "signal_vector_ready": False,
            }
        scores = [abs(_corr(vector, registry_vector)) for registry_vector in self._registry_vectors]
        best_index = int(np.argmax(scores)) if scores else -1
        best = float(scores[best_index]) if best_index >= 0 else 0.0
        top = sorted(scores, reverse=True)[: min(5, len(scores))]
        nearest = self._registry_cluster_ids[best_index] if best_index >= 0 else ""
        return {
            **meta,
            "nearest_134_signal_cluster_id": nearest,
            "max_corr_to_134_signal_vector": round(best, 6),
            "mean_topk_corr_to_134_signal_vector": round(float(sum(top) / len(top)), 6) if top else 0.0,
            "known_signal_cluster_id": nearest if best >= self.corr_threshold else "",
            "signal_vector_ready": True,
        }

    def selected_similarity(self, expression: str, selected_rows: list[dict[str, Any]]) -> dict[str, Any]:
        vector, meta = self.vector_for_expression(expression)
        if vector is None or not selected_rows:
            return {
                **meta,
                "max_corr_to_selected_queue_signal": 0.0,
                "mean_corr_to_selected_queue_signal": 0.0,
                "nearest_selected_signal_cluster_id": "",
                "nearest_selected_signal_vector_id": "",
            }
        scores: list[tuple[float, dict[str, Any]]] = []
        for selected in selected_rows:
            selected_expression = str(selected.get("expression") or "")
            selected_vector, selected_meta = self.vector_for_expression(selected_expression)
            if selected_vector is None:
                continue
            scores.append((abs(_corr(vector, selected_vector)), {**selected, **selected_meta}))
        if not scores:
            return {
                **meta,
                "max_corr_to_selected_queue_signal": 0.0,
                "mean_corr_to_selected_queue_signal": 0.0,
                "nearest_selected_signal_cluster_id": "",
                "nearest_selected_signal_vector_id": "",
            }
        scores.sort(key=lambda item: item[0], reverse=True)
        top_values = [item[0] for item in scores[: min(5, len(scores))]]
        nearest_row = scores[0][1]
        nearest_cluster = str(
            nearest_row.get("known_signal_cluster_id")
            or nearest_row.get("provisional_signal_cluster_id")
            or nearest_row.get("signal_vector_id")
            or ""
        )
        return {
            **meta,
            "max_corr_to_selected_queue_signal": round(float(scores[0][0]), 6),
            "mean_corr_to_selected_queue_signal": round(float(sum(top_values) / len(top_values)), 6),
            "nearest_selected_signal_cluster_id": nearest_cluster if float(scores[0][0]) >= self.corr_threshold else "",
            "nearest_selected_signal_vector_id": str(nearest_row.get("signal_vector_id") or ""),
        }

    def feature_bundle(self, expression: str, selected_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        selected_rows = selected_rows or []
        registry = self.registry_similarity(expression)
        selected = self.selected_similarity(expression, selected_rows)
        known = str(registry.get("known_signal_cluster_id") or "")
        selected_cluster = str(selected.get("nearest_selected_signal_cluster_id") or "")
        vector_id = str(registry.get("signal_vector_id") or selected.get("signal_vector_id") or expression_vector_id(expression))
        provisional = known or selected_cluster or f"sigprov_{vector_id[:12]}"
        return {
            **registry,
            **selected,
            "known_signal_cluster_id": known,
            "provisional_signal_cluster_id": provisional,
            "signal_vector_cluster_basis": "known_134" if known else ("selected_queue" if selected_cluster else "self_vector"),
        }
