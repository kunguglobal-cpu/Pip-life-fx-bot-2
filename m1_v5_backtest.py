"""
Lightweight V5 signal backtest using historical candles.

This evaluates signal generation only.
"""

import sys

from m1_v5_strategy import find_entry


def load_csv(path):
    import csv
    from datetime import datetime, timezone

    rows = []

    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            t = r.get("time") or r.get("timestamp")

            try:
                dt = datetime.fromisoformat(
                    t.replace("Z", "+00:00")
                )
            except Exception:
                continue

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            rows.append({
                "time": dt,
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r.get("volume", 0)),
            })

    return rows


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python m1_v5_backtest.py "
            "<m1_candles.csv>"
        )
        return

    candles = load_csv(sys.argv[1])

    signals = []

    for i in range(40, len(candles)):
        window = candles[:i + 1]

        groups = {}

        for c in window:
            ts = c["time"]
            minute = (ts.minute // 5) * 5

            key = ts.replace(
                minute=minute,
                second=0,
                microsecond=0,
            )

            groups.setdefault(key, []).append(c)

        m5 = []

        for key in sorted(groups):
            g = groups[key]

            if len(g) < 5:
                continue

            m5.append({
                "time": key,
                "open": g[0]["open"],
                "high": max(x["high"] for x in g),
                "low": min(x["low"] for x in g),
                "close": g[-1]["close"],
                "volume": sum(
                    float(x.get("volume", 0))
                    for x in g
                ),
            })

        signal = find_entry(m5, window)

        if signal:
            signals.append(signal)

    print("=" * 72)
    print(" PIP-LIFE FX BOT V5 — SIGNAL BACKTEST")
    print("=" * 72)
    print(f"Candles: {len(candles)}")
    print(f"Signals: {len(signals)}")

    buys = sum(
        1 for x in signals
        if x["direction"] == "BUY"
    )

    sells = sum(
        1 for x in signals
        if x["direction"] == "SELL"
    )

    print(f"BUY signals:  {buys}")
    print(f"SELL signals: {sells}")

    if signals:
        print("\nLAST SIGNAL:")
        print(signals[-1])

    print("=" * 72)


if __name__ == "__main__":
    main()
