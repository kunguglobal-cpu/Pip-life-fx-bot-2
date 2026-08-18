import os
import time

from metaapi_market import MetaAPIMarket
from metaapi_trade import MetaAPITrade
from m1_risk_manager import calculate_lot_size, risk_percent
import m1_v4_strategy as v4_strategy
from m1_v4_strategy import find_entry
from m1_v4_velocity import confirm_m1_velocity


SYMBOL = os.getenv("M1_SYMBOL", "XAUUSD")
DRY_RUN = os.getenv("M1_DRY_RUN", "true").lower() == "true"
CANDLES = int(os.getenv("M1_V4_CANDLES", "300"))
POLL_SECONDS = float(os.getenv("M1_POLL", "1.0"))

# ============================================================
# V4 PROTECTIVE MANAGEMENT — POINT BASED
# ============================================================
# Default XAUUSD point size is 0.01.
# Therefore 300 points = 3.00 price units when POINT_SIZE=0.01.
POINT_SIZE = float(os.getenv("M1_V4_POINT_SIZE", "0.01"))

INITIAL_SL_POINTS = int(os.getenv("M1_V4_INITIAL_SL_POINTS", "300"))
BE_TRIGGER_POINTS = int(os.getenv("M1_V4_BE_TRIGGER_POINTS", "300"))
TRAIL_DISTANCE_POINTS = int(os.getenv("M1_V4_TRAIL_POINTS", "300"))

# The stop advances in fixed 300-point steps.
# No small 10-point trailing updates are used.

INITIAL_SL_DISTANCE = INITIAL_SL_POINTS * POINT_SIZE
BE_TRIGGER = BE_TRIGGER_POINTS * POINT_SIZE
TRAIL_DISTANCE = TRAIL_DISTANCE_POINTS * POINT_SIZE

RISK_VALUE_PER_PRICE_UNIT = float(
    os.getenv("M1_RISK_VALUE_PER_PRICE_UNIT", "100.0")
)
MAX_LOT = float(os.getenv("M1_V4_MAX_LOT", "0.01"))
ZONE_BUFFER = float(os.getenv("M1_V4_ZONE_BUFFER", "0.03"))
SL_BUFFER = float(os.getenv("M1_V4_SL_BUFFER", "0.05"))


market = MetaAPIMarket()
trade = MetaAPITrade(dry_run=DRY_RUN)

# V4 velocity-expansion confirmation
# Replaces the restrictive M1 rejection/engulfing confirmation.
v4_strategy.confirm_m1 = confirm_m1_velocity


state = {
    "position_id": None,
    "side": None,
    "entry": None,
    "sl": None,
    "volume": None,
    "be_locked": False,
}


def position_id(p):
    return p.get("id") or p.get("positionId") or p.get("position_id")


def position_side(p):
    value = str(p.get("type", "")).upper()
    if "BUY" in value:
        return "BUY"
    if "SELL" in value:
        return "SELL"
    return None


def position_entry(p):
    return float(p.get("openPrice", p.get("price", 0.0)))


def position_sl(p):
    value = p.get("stopLoss", p.get("stopLossPrice"))
    return None if value is None else float(value)


def reset_state():
    state.update(
        position_id=None,
        side=None,
        entry=None,
        sl=None,
        volume=None,
        be_locked=False,
    )


def reconcile():
    if not state["position_id"]:
        return False

    positions = trade.positions(SYMBOL)
    for p in positions:
        pid = position_id(p)
        if pid is not None and str(pid) == str(state["position_id"]):
            state["entry"] = position_entry(p)
            state["sl"] = position_sl(p)
            return True

    print("V4 POSITION CLOSED | state cleared")
    reset_state()
    return False


def manage_position(bid, ask):
    if not reconcile():
        return

    side = state["side"]
    entry = state["entry"]
    current_sl = state["sl"]

    if entry is None or current_sl is None:
        return

    # ========================================================
    # ENTRY-ANCHORED 300-POINT STEPPED TRAILING
    # ========================================================
    # BUY example:
    # 4400 entry -> 4403 => SL 4400
    # 4406       -> SL 4403
    # 4409       -> SL 4406
    #
    # SELL is the exact mirror.
    #
    # The calculation is anchored to ENTRY, not to the initial SL.
    # The stop only moves in the profitable direction.

    if side == "BUY":
        favorable = bid - entry
    else:
        favorable = entry - ask

    if favorable < BE_TRIGGER:
        return

    steps = int(favorable // TRAIL_DISTANCE)

    # +300 -> BE
    # +600 -> entry +300
    # +900 -> entry +600
    target_sl = (
        entry + (steps - 1) * TRAIL_DISTANCE
        if side == "BUY"
        else entry - (steps - 1) * TRAIL_DISTANCE
    )

    if side == "BUY":
        if target_sl <= current_sl:
            return
    else:
        if target_sl >= current_sl:
            return

    result = trade.modify_position(
        state["position_id"],
        target_sl
    )

    if result:
        old_sl = current_sl
        state["sl"] = target_sl
        state["be_locked"] = target_sl >= entry if side == "BUY" else target_sl <= entry

        print(
            f"V4 STEP TRAIL | {side} | "
            f"entry={entry:.2f} | "
            f"price={(bid if side == 'BUY' else ask):.2f} | "
            f"old_sl={old_sl:.2f} | "
            f"new_sl={target_sl:.2f} | "
            f"profit_points={favorable / POINT_SIZE:.0f}"
        )


def open_signal(signal, bid, ask):
    account = trade.account_information()
    balance = float(account.get("balance", 0.0))

    entry = ask if signal.side == "BUY" else bid

    # V4 structural initial SL:
    # - BUY: below the respected M5 FVG/OB/Breaker
    # - SELL: above the respected M5 FVG/OB/Breaker
    # - Never closer than 300 points from entry.
    structural_sl = float(signal.stop_loss)

    if signal.side == "BUY":
        initial_sl = min(
            structural_sl,
            entry - INITIAL_SL_DISTANCE
        )
    else:
        initial_sl = max(
            structural_sl,
            entry + INITIAL_SL_DISTANCE
        )

    volume = calculate_lot_size(
        balance=balance,
        entry=entry,
        stop_loss=initial_sl,
        value_per_price_unit=RISK_VALUE_PER_PRICE_UNIT,
        max_lot=MAX_LOT,
    )

    if volume <= 0:
        print(
            f"V4 RISK BLOCK | balance=${balance:.2f} | "
            f"risk={risk_percent(balance)*100:.2f}% | "
            f"stop={initial_sl:.2f}"
        )
        return False

    print(
        "\nV4 ENTRY | "
        f"{signal.side} | zone={signal.zone_type} "
        f"{signal.zone_low:.2f}-{signal.zone_high:.2f} | "
        f"M1={signal.confirmation} | "
        f"entry={entry:.2f} | "
        f"SL={initial_sl:.2f} "
        f"({INITIAL_SL_POINTS} points) | "
        f"volume={volume:.2f}"
    )

    if signal.side == "BUY":
        result = trade.buy(SYMBOL, volume, initial_sl, None)
    else:
        result = trade.sell(SYMBOL, volume, initial_sl, None)

    pid = result.get("position_id") if isinstance(result, dict) else None
    if not pid:
        print(f"V4 ENTRY FAILED | result={result}")
        return False

    state.update(
        position_id=pid,
        side=signal.side,
        entry=entry,
        sl=initial_sl,
        volume=volume,
        be_locked=False,
    )
    return True


def main():
    print("=" * 72)
    print(" M1 XAUUSD V4 — M5 ZONE / M1 CONFIRMATION RUNNER")
    print("=" * 72)
    print(
        "RULE: M5 structure -> M5 FVG/OB/Breaker -> "
        "M1 rejection/engulfing -> entry -> BE -> trail"
    )
    print(
        f"DRY_RUN={DRY_RUN} | "
        f"INITIAL_SL={INITIAL_SL_POINTS}pts | "
        f"BE={BE_TRIGGER_POINTS}pts | "
        f"TRAIL={TRAIL_DISTANCE_POINTS}pts | "
        f"POINT_SIZE={POINT_SIZE}"
    )

    last_completed_time = None

    while True:
        try:
            candles = market.candles(SYMBOL, CANDLES)
            if len(candles) < 20:
                print("V4 WAIT | insufficient M1 candles")
                time.sleep(POLL_SECONDS)
                continue

            # MetaAPI historical candles may include the currently forming
            # M1 candle. The last candle is intentionally excluded from entry.
            completed = candles[:-1]
            # Use the latest completed M1 candle instead of the
            # MetaAPI RPC price call, which can hang on Termux.
            candle_price = float(completed[-1]["close"])
            bid = candle_price
            ask = candle_price

            manage_position(bid, ask)

            current_completed_time = completed[-1].get("time")
            if current_completed_time != last_completed_time:
                last_completed_time = current_completed_time

                if not state["position_id"]:
                    signal = find_entry(
                        completed,
                        bid,
                        ask,
                        zone_buffer=ZONE_BUFFER,
                        sl_buffer=SL_BUFFER,
                    )

                    if signal:
                        open_signal(signal, bid, ask)
                    else:
                        print(
                            f"V4 SCAN | {current_completed_time} | "
                            "no M1 velocity expansion"
                        )

            time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            print("\nV4 STOPPED")
            break
        except Exception as exc:
            print(f"V4 LOOP ERROR | {exc!r}")
            time.sleep(max(POLL_SECONDS, 2.0))


if __name__ == "__main__":
    main()
