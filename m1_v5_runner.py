"""
Pip-life FX Bot V5 runner.

DRY RUN ONLY during development.
"""

import os
import time

from metaapi_market import MetaAPIMarket
from metaapi_trade import MetaAPITrade
from m1_v5_strategy import find_entry


SYMBOL = os.getenv("M1_V5_SYMBOL", "XAUUSD")

DRY_RUN = (
    os.getenv("M1_DRY_RUN", "true").lower()
    not in ("false", "0", "no")
)

POLL_SECONDS = int(os.getenv("M1_V5_POLL_SECONDS", "60"))

print("=" * 72)
print(" PIP-LIFE FX BOT V5 — IMPULSE / PULLBACK SCALPER")
print("=" * 72)
print(
    "RULE: M5 bias -> M1 velocity expansion -> "
    "M1 pullback/reclaim -> entry -> BE -> trail"
)
print(f"DRY_RUN={DRY_RUN}")
print(
    f"VELOCITY_LOOKBACK={os.getenv('M1_V5_LOOKBACK', '12')} | "
    f"MULTIPLIER={os.getenv('M1_V5_VELOCITY_MULTIPLIER', '1.35')} | "
    f"MIN_VELOCITY={os.getenv('M1_V5_MIN_VELOCITY', '0.03')}"
)
print("=" * 72)


market = MetaAPIMarket()
trade = MetaAPITrade(dry_run=DRY_RUN)


def run_once():
    m1 = market.candles(SYMBOL, 120)

    if len(m1) < 30:
        print("V5 | insufficient M1 candles")
        return

    # Build M5 candles from M1 data.
    # We deliberately use completed 5-minute groups.
    groups = {}

    for c in m1:
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

    signal = find_entry(m5, m1)

    if signal is None:
        print(
            "V5 SCAN | "
            f"{m1[-1]['time']} | "
            "no impulse/pullback setup"
        )
        return

    print(
        "V5 SIGNAL | "
        f"{signal['direction']} | "
        f"entry={signal['entry']:.2f} | "
        f"SL={signal['sl']:.2f} | "
        f"TP={signal['tp']:.2f} | "
        f"RR={signal['rr']:.2f} | "
        f"ATR={signal['atr']:.2f} | "
        f"{signal['reason']}"
    )

    if DRY_RUN:
        print("V5 DRY RUN | trade NOT sent")
        return

    # Execution intentionally remains disabled until V5
    # has been validated in dry-run mode.
    print(
        "V5 SAFETY | live execution disabled "
        "during strategy validation"
    )


try:
    while True:
        run_once()
        time.sleep(POLL_SECONDS)

except KeyboardInterrupt:
    print("V5 STOPPED")

finally:
    try:
        market.close()
    except Exception:
        pass
