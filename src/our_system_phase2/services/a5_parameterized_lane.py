from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from our_system_phase2.services.real_market_data import DEFAULT_REAL_MARKET_DATASET_PATH


DEFAULT_A5_ARCHIVE_ROOT = Path(
    r"G:\Project_V7_Archive_20260412\alpha_factory_backup_20260412\reports\alphagpt_a5"
)


def _walk_json(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)
    else:
        yield value


def extract_a5_observed_windows(archive_root: Path | str = DEFAULT_A5_ARCHIVE_ROOT) -> list[int]:
    root = Path(archive_root)
    windows: set[int] = set()
    if not root.exists():
        return []
    patterns = (
        r"lag\s*=\s*(\d+)",
        r"window\s*=\s*(\d+)",
        r"_(\d+)d\b",
        r"\b(?:MOM|VOL|GAP)\([^)]*,\s*(\d+)\)",
    )
    for path in root.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for item in _walk_json(payload):
            if not isinstance(item, str):
                continue
            for pattern in patterns:
                for match in re.finditer(pattern, item, flags=re.IGNORECASE):
                    window = int(match.group(1))
                    if 1 <= window <= 252:
                        windows.add(window)
    return sorted(windows)


def infer_real_data_windows(
    path: Path | str = DEFAULT_REAL_MARKET_DATASET_PATH,
    *,
    archive_root: Path | str = DEFAULT_A5_ARCHIVE_ROOT,
    max_window: int = 252,
    target_window_count: int = 14,
) -> dict[str, Any]:
    panel_path = Path(path)
    if panel_path.suffix.lower() == ".parquet":
        dates = pd.read_parquet(panel_path, columns=["date"])
    else:
        dates = pd.read_csv(panel_path, usecols=["date"])
    unique_dates = pd.to_datetime(dates["date"], errors="coerce").dropna().drop_duplicates().sort_values()
    trading_day_count = int(len(unique_dates))
    bounded_max = max(2, min(int(max_window), max(2, trading_day_count // 4)))
    data_scales = {
        int(round(value))
        for value in np.geomspace(2, bounded_max, num=max(2, target_window_count))
    }
    data_scales.add(1)
    observed = set(extract_a5_observed_windows(archive_root))
    windows = sorted(window for window in (data_scales | observed) if 1 <= window <= bounded_max)
    short_long_pairs = [
        (short, long)
        for short in windows
        for long in windows
        if short < long and long / max(1, short) >= 1.8
    ]
    return {
        "depends_on_registered_window_prior": False,
        "parameter_source": "real_data_calendar_scales_plus_a5_archive_observed_scales",
        "dataset_path": str(path),
        "a5_archive_root": str(archive_root),
        "trading_day_count": trading_day_count,
        "min_date": unique_dates.min().date().isoformat() if trading_day_count else None,
        "max_date": unique_dates.max().date().isoformat() if trading_day_count else None,
        "max_window": bounded_max,
        "target_window_count": target_window_count,
        "data_adaptive_windows": sorted(data_scales),
        "a5_observed_windows": sorted(observed),
        "windows": windows,
        "short_long_pairs": short_long_pairs,
    }


def _gap_expression(window: int) -> str:
    return f"Div(Sub($open,Delay($close,{window})),Delay($close,{window}))"


def _vol_ratio_expression(short: int, long: int) -> str:
    return f"Div(Mean($volume,{short}),Mean($volume,{long}))"


def _amount_ratio_expression(short: int, long: int) -> str:
    return f"Div(Mean($amount,{short}),Mean($amount,{long}))"


def _amihud_expression(window: int) -> str:
    return f"Mean(Div(Abs($ret),$amount),{window})"


def _dev_ma_expression(window: int) -> str:
    ma = f"Mean($close,{window})"
    return f"Div(Sub($close,{ma}),{ma})"


def _primitive_expressions(parameter_space: dict[str, Any]) -> list[dict[str, str]]:
    windows = [int(window) for window in parameter_space["windows"]]
    pairs = [(int(short), int(long)) for short, long in parameter_space["short_long_pairs"]]
    primitives: list[dict[str, str]] = []
    for window in windows:
        primitives.extend(
            [
                {"family": "a5_gap", "expression": _gap_expression(window)},
                {"family": "a5_momentum", "expression": f"Mom($close,{window})"},
                {"family": "a5_amihud", "expression": _amihud_expression(window)},
                {"family": "a5_dev_ma", "expression": _dev_ma_expression(window)},
                {"family": "a5_volatility", "expression": f"Std($ret,{window})"},
            ]
        )
    for short, long in pairs:
        primitives.extend(
            [
                {"family": "a5_vol_ratio", "expression": _vol_ratio_expression(short, long)},
                {"family": "a5_amount_ratio", "expression": _amount_ratio_expression(short, long)},
                {
                    "family": "a5_gap_vol_interaction",
                    "expression": f"Mul(ZScore({_gap_expression(short)}),ZScore({_vol_ratio_expression(short, long)}))",
                },
                {
                    "family": "a5_liquidity_dev_interaction",
                    "expression": f"Mul(ZScore({_amihud_expression(long)}),ZScore({_dev_ma_expression(short)}))",
                },
            ]
        )
    return primitives


def build_a5_real_parameterized_ledger(
    *,
    path: Path | str = DEFAULT_REAL_MARKET_DATASET_PATH,
    archive_root: Path | str = DEFAULT_A5_ARCHIVE_ROOT,
    candidate_limit: int = 180,
) -> dict[str, Any]:
    parameter_space = infer_real_data_windows(path, archive_root=archive_root)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for primitive in _primitive_expressions(parameter_space):
        for transform in ("CSRank", "ZScore"):
            expression = f"{transform}({primitive['expression']})"
            for direction, directed_expression in (
                ("normal", expression),
                ("inverted", f"Neg({expression})"),
            ):
                if directed_expression in seen:
                    continue
                seen.add(directed_expression)
                records.append(
                    {
                        "candidate_id": f"a5-real-param-{len(records) + 1:04d}",
                        "expression": directed_expression,
                        "retained": True,
                        "source_mode": "a5_real_parameterized_primitive_lane",
                        "frontier_lane": "a5_real_parameterized_lane",
                        "archive_cell": "a5_real_parameterized_probe",
                        "primitive_family": primitive["family"],
                        "direction": direction,
                    }
                )
                if len(records) >= candidate_limit:
                    return {
                        "run_id": "a5-real-parameterized-lane",
                        "scope": "a5_archive_inspired_real_data_parameterized_primitives",
                        "candidate_limit": candidate_limit,
                        "parameter_space": parameter_space,
                        "records": records,
                    }
    return {
        "run_id": "a5-real-parameterized-lane",
        "scope": "a5_archive_inspired_real_data_parameterized_primitives",
        "candidate_limit": candidate_limit,
        "parameter_space": parameter_space,
        "records": records,
    }
