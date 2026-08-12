from metaapi_market import MetaAPIMarket
from m1_v4_strategy import (
    find_entry,
    aggregate_m5,
    detect_m5_structure,
    detect_m5_fvg,
    detect_m5_order_blocks,
    detect_m5_breakers,
    confirm_m1,
    _zone_still_valid,
    _touches_zone,
)


SYMBOL = "XAUUSD"
CANDLES = 1000
START_BALANCE = 100.0

POINT_SIZE = 0.01
INITIAL_SL_POINTS = 300
BE_TRIGGER_POINTS = 300
TRAIL_DISTANCE_POINTS = 300

INITIAL_SL_DISTANCE = INITIAL_SL_POINTS * POINT_SIZE
BE_TRIGGER = BE_TRIGGER_POINTS * POINT_SIZE
TRAIL_DISTANCE = TRAIL_DISTANCE_POINTS * POINT_SIZE

ZONE_BUFFER = 0.03
SL_BUFFER = 0.05


market = MetaAPIMarket()
candles = market.candles(SYMBOL, CANDLES)

if len(candles) < 100:
    raise SystemExit("Not enough M1 candles for V4 backtest")

# Remove possible forming candle.
candles = candles[:-1]


# ============================================================
# DIAGNOSTICS
# ============================================================

stats = {
    "iterations": 0,
    "buy_structure": 0,
    "sell_structure": 0,
    "neutral_structure": 0,

    "fvg_zones": 0,
    "ob_zones": 0,
    "breaker_zones": 0,

    "valid_buy_zones": 0,
    "valid_sell_zones": 0,

    "buy_zone_touch": 0,
    "sell_zone_touch": 0,

    "buy_rejection": 0,
    "buy_engulfing": 0,
    "sell_rejection": 0,
    "sell_engulfing": 0,

    "signals": 0,
}


balance = START_BALANCE
position = None
trades = []


def diagnostic_find_entry(history, bid, ask):

    m5 = aggregate_m5(history)

    if len(m5) < 15 or len(history) < 10:
        return None

    structure = detect_m5_structure(m5)
    side = structure["direction"]

    if side == "BUY":
        stats["buy_structure"] += 1
    elif side == "SELL":
        stats["sell_structure"] += 1
    else:
        stats["neutral_structure"] += 1
        return None

    protected = (
        structure["protected_low"]
        if side == "BUY"
        else structure["protected_high"]
    )

    if protected is None:
        return None

    fvg = detect_m5_fvg(m5)
    obs = detect_m5_order_blocks(m5)
    breakers = detect_m5_breakers(m5)

    stats["fvg_zones"] += len(fvg)
    stats["ob_zones"] += len(obs)
    stats["breaker_zones"] += len(breakers)

    zones = fvg + obs + breakers

    zones = [
        z for z in zones
        if z.direction == side
        and _zone_still_valid(z, m5)
    ]

    if side == "BUY":
        stats["valid_buy_zones"] += len(zones)
    else:
        stats["valid_sell_zones"] += len(zones)

    zones.sort(key=lambda z: z.index, reverse=True)

    if side == "BUY" and bid <= protected:
        return None

    if side == "SELL" and ask >= protected:
        return None

    # --------------------------------------------------------
    # M1 confirmation diagnostics
    # --------------------------------------------------------

    for zone in zones:

        if not _touches_zone(history[-1], zone, ZONE_BUFFER):
            continue

        if side == "BUY":
            stats["buy_zone_touch"] += 1
        else:
            stats["sell_zone_touch"] += 1

        confirmation = confirm_m1(
            history,
            zone,
            ZONE_BUFFER,
        )

        if confirmation == "REJECTION":
            if side == "BUY":
                stats["buy_rejection"] += 1
            else:
                stats["sell_rejection"] += 1

        elif confirmation == "ENGULFING":
            if side == "BUY":
                stats["buy_engulfing"] += 1
            else:
                stats["sell_engulfing"] += 1

        if not confirmation:
            continue

        entry = ask if side == "BUY" else bid

        if side == "BUY":
            sl = zone.low - SL_BUFFER

            if sl >= entry:
                continue

        else:
            sl = zone.high + SL_BUFFER

            if sl <= entry:
                continue

        stats["signals"] += 1

        return type(
            "Signal",
            (),
            {
                "side": side,
                "zone_type": zone.kind,
                "stop_loss": sl,
            },
        )()

    return None


# ============================================================
# BACKTEST
# ============================================================

for i in range(60, len(candles)):

    stats["iterations"] += 1

    history = candles[: i + 1]

    current = history[-1]

    price = float(current["close"])

    signal = diagnostic_find_entry(
        history,
        price,
        price,
    )


    # ========================================================
    # MANAGE EXISTING POSITION
    # ========================================================

    if position is not None and i + 1 < len(candles):

        nxt = candles[i + 1]

        high = float(nxt["high"])
        low = float(nxt["low"])


        if position["side"] == "BUY":

            if low <= position["sl"]:

                exit_price = position["sl"]

                pnl = exit_price - position["entry"]

                balance += pnl

                trades.append(
                    (
                        "SL",
                        "BUY",
                        position["entry"],
                        exit_price,
                        pnl,
                        nxt["time"],
                    )
                )

                position = None

                continue


            favorable = high - position["entry"]

            if favorable >= BE_TRIGGER:

                position["be_locked"] = True


            if position["be_locked"]:

                steps = int(
                    favorable // TRAIL_DISTANCE
                )

                target = (
                    position["entry"]
                    + (steps - 1) * TRAIL_DISTANCE
                )

                if target > position["sl"]:

                    position["sl"] = target


        else:

            if high >= position["sl"]:

                exit_price = position["sl"]

                pnl = position["entry"] - exit_price

                balance += pnl

                trades.append(
                    (
                        "SL",
                        "SELL",
                        position["entry"],
                        exit_price,
                        pnl,
                        nxt["time"],
                    )
                )

                position = None

                continue


            favorable = position["entry"] - low

            if favorable >= BE_TRIGGER:

                position["be_locked"] = True


            if position["be_locked"]:

                steps = int(
                    favorable // TRAIL_DISTANCE
                )

                target = (
                    position["entry"]
                    - (steps - 1) * TRAIL_DISTANCE
                )

                if target < position["sl"]:

                    position["sl"] = target


    # ========================================================
    # OPEN NEW POSITION
    # ========================================================

    if position is None and signal:

        side = signal.side

        entry = price

        initial_sl = signal.stop_loss

        # Enforce minimum 300-point initial SL.

        if side == "BUY":

            minimum_sl = entry - INITIAL_SL_DISTANCE

            initial_sl = min(
                initial_sl,
                minimum_sl,
            )

        else:

            minimum_sl = entry + INITIAL_SL_DISTANCE

            initial_sl = max(
                initial_sl,
                minimum_sl,
            )


        position = {
            "side": side,
            "entry": entry,
            "sl": initial_sl,
            "be_locked": False,
            "zone": signal.zone_type,
        }

        trades.append(
            (
                "OPEN",
                side,
                entry,
                initial_sl,
                0.0,
                current["time"],
            )
        )


# ============================================================
# CLOSE REMAINING POSITION
# ============================================================

if position is not None:

    last = candles[-1]

    exit_price = float(last["close"])

    pnl = (
        exit_price - position["entry"]
        if position["side"] == "BUY"
        else position["entry"] - exit_price
    )

    balance += pnl

    trades.append(
        (
            "END_CLOSE",
            position["side"],
            position["entry"],
            exit_price,
            pnl,
            last["time"],
        )
    )


closed = [
    t for t in trades
    if t[0] in ("SL", "END_CLOSE")
]

wins = [
    t for t in closed
    if t[4] > 0
]

losses = [
    t for t in closed
    if t[4] <= 0
]


# ============================================================
# REPORT
# ============================================================

print()
print("=" * 72)
print(" M1 XAUUSD V4 — DIAGNOSTIC BACKTEST")
print("=" * 72)

print()
print("DATA")
print("-" * 72)
print(f"M1 candles tested       : {len(candles)}")
print(f"Iterations              : {stats['iterations']}")

print()
print("M5 MARKET STRUCTURE")
print("-" * 72)
print(f"BUY structure           : {stats['buy_structure']}")
print(f"SELL structure          : {stats['sell_structure']}")
print(f"NEUTRAL                 : {stats['neutral_structure']}")

print()
print("M5 ZONES DETECTED")
print("-" * 72)
print(f"FVG zones               : {stats['fvg_zones']}")
print(f"Order Blocks            : {stats['ob_zones']}")
print(f"Breaker Blocks          : {stats['breaker_zones']}")

print()
print("VALID ZONES")
print("-" * 72)
print(f"Valid BUY zones         : {stats['valid_buy_zones']}")
print(f"Valid SELL zones        : {stats['valid_sell_zones']}")

print()
print("M1 ZONE TOUCHES")
print("-" * 72)
print(f"BUY zone touches        : {stats['buy_zone_touch']}")
print(f"SELL zone touches       : {stats['sell_zone_touch']}")

print()
print("M1 CONFIRMATIONS")
print("-" * 72)
print(f"BUY rejection           : {stats['buy_rejection']}")
print(f"BUY engulfing           : {stats['buy_engulfing']}")
print(f"SELL rejection          : {stats['sell_rejection']}")
print(f"SELL engulfing          : {stats['sell_engulfing']}")

print()
print("FINAL SIGNALS")
print("-" * 72)
print(f"Valid entries           : {stats['signals']}")

print()
print("RESULT")
print("-" * 72)
print(f"Starting balance        : ${START_BALANCE:.2f}")
print(f"Ending balance          : ${balance:.2f}")
print(f"Closed trades           : {len(closed)}")

if closed:

    winrate = (
        len(wins)
        / len(closed)
        * 100.0
    )

    gross_profit = sum(
        t[4] for t in wins
    )

    gross_loss = sum(
        t[4] for t in losses
    )

    print(f"Winners                 : {len(wins)}")
    print(f"Losers                  : {len(losses)}")
    print(f"Win rate                : {winrate:.1f}%")
    print(f"Gross profit            : {gross_profit:+.4f}")
    print(f"Gross loss              : {gross_loss:+.4f}")
    print(
        f"Net movement            : "
        f"{gross_profit + gross_loss:+.4f}"
    )

print()
print("=" * 72)
print("READ-ONLY — NO ORDERS WERE SENT")
print("=" * 72)
