"""Create a small synthetic panel for paper reproducibility demos."""

from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated" / "synthetic"


def trading_days(start: date, count: int) -> list[date]:
    days: list[date] = []
    cur = start
    while len(days) < count:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def main() -> int:
    rng = random.Random(20260519)
    OUT.mkdir(parents=True, exist_ok=True)
    days = trading_days(date(2025, 1, 2), 180)
    codes = [f"S{i:04d}" for i in range(80)]
    rows = []
    prices = {code: 10.0 + rng.random() * 20.0 for code in codes}
    for t, day in enumerate(days):
        liquidity_state = 0.8 + 0.25 * math.sin(t / 17.0) + rng.gauss(0, 0.04)
        regime_alpha = 0.006 if liquidity_state < 0.78 else -0.001
        for i, code in enumerate(codes):
            quality = ((i % 13) - 6) / 6.0
            ret = rng.gauss(0, 0.018) + regime_alpha * quality
            open_px = prices[code] * (1.0 + rng.gauss(0, 0.003))
            close = max(1.0, open_px * (1.0 + ret))
            high = max(open_px, close) * (1.0 + abs(rng.gauss(0, 0.004)))
            low = min(open_px, close) * (1.0 - abs(rng.gauss(0, 0.004)))
            amount = max(1_000_000, (1.4 - liquidity_state) * 20_000_000 * (1 + rng.random()))
            volume = amount / close
            prices[code] = close
            rows.append(
                {
                    "date": day.isoformat(),
                    "code": code,
                    "open": round(open_px, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close, 4),
                    "volume": round(volume, 2),
                    "amount": round(amount, 2),
                    "float_mcap": round(close * (10_000_000 + i * 1000), 2),
                    "liquidity_state": round(liquidity_state, 6),
                }
            )
    path = OUT / "synthetic_panel.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

