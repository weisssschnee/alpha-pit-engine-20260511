"""Run a toy regime-gated book and placebo audit on the synthetic panel."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYN = ROOT / "generated" / "synthetic"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def ann(mean_daily: float) -> float:
    return (1.0 + mean_daily) ** 252 - 1.0


def max_drawdown(returns: list[float]) -> float:
    eq = 1.0
    peak = 1.0
    worst = 0.0
    for r in returns:
        eq *= 1.0 + r
        peak = max(peak, eq)
        worst = min(worst, eq / peak - 1.0)
    return worst


def book_returns(rows: list[dict[str, str]]) -> list[dict[str, float | str | bool]]:
    by_date: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_date.setdefault(row["date"], []).append(row)
    out = []
    prev_close: dict[str, float] = {}
    for day in sorted(by_date):
        block = by_date[day]
        scored = []
        for row in block:
            code = row["code"]
            close = float(row["close"])
            old = prev_close.get(code)
            if old:
                signal = abs(close - old) / old
                fwd_ret = close / old - 1.0
                scored.append((signal, fwd_ret))
            prev_close[code] = close
        if len(scored) < 20:
            continue
        scored.sort(key=lambda x: x[0])
        n = max(1, len(scored) // 10)
        # Synthetic book: high signal names outperform in low-liquidity regime by construction.
        ret = mean([x[1] for x in scored[-n:]]) - mean([x[1] for x in scored[:n]])
        liquidity = mean([float(x["liquidity_state"]) for x in block])
        gate = liquidity < 0.78
        out.append({"date": day, "book_return": ret, "gate_active": gate, "gated_return": ret if gate else 0.0, "liquidity": liquidity})
    return out


def placebo(rows: list[dict[str, float | str | bool]], draws: int = 200) -> dict[str, float]:
    rng = random.Random(20260519)
    returns = [float(r["book_return"]) for r in rows]
    active_count = sum(1 for r in rows if r["gate_active"])
    true = [float(r["gated_return"]) for r in rows]
    sims = []
    idx = list(range(len(rows)))
    for _ in range(draws):
        active = set(rng.sample(idx, active_count))
        gated = [returns[i] if i in active else 0.0 for i in idx]
        sims.append(ann(mean(gated)))
    sims.sort()
    return {
        "draws": draws,
        "true_ann": ann(mean(true)),
        "random_p95_ann": sims[int(0.95 * (draws - 1))],
        "active_count": active_count,
    }


def main() -> int:
    rows = read_rows(SYN / "synthetic_panel.csv")
    br = book_returns(rows)
    SYN.mkdir(parents=True, exist_ok=True)
    with (SYN / "toy_daily_gate.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "book_return", "gate_active", "gated_return", "liquidity"])
        writer.writeheader()
        writer.writerows(br)
    result = {
        "ungated_ann": ann(mean([float(r["book_return"]) for r in br])),
        "gated_ann": ann(mean([float(r["gated_return"]) for r in br])),
        "gated_max_drawdown": max_drawdown([float(r["gated_return"]) for r in br]),
        "placebo": placebo(br),
    }
    (SYN / "toy_regime_gate_summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

