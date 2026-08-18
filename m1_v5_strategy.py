"""
Pip-life FX Bot V5
M5 directional bias -> M1 impulse expansion -> M1 pullback/reclaim.

DRY-RUN development version.
"""

import os
from statistics import median


POINT_SIZE = float(os.getenv("M1_V5_POINT_SIZE", "0.01"))

LOOKBACK = int(os.getenv("M1_V5_LOOKBACK", "12"))
VELOCITY_MULTIPLIER = float(os.getenv("M1_V5_VELOCITY_MULTIPLIER", "1.35"))
MIN_VELOCITY = float(os.getenv("M1_V5_MIN_VELOCITY", "0.03"))

PULLBACK_MAX = float(os.getenv("M1_V5_PULLBACK_MAX", "0.55"))
MIN_RR = float(os.getenv("M1_V5_MIN_RR", "1.5"))


def _f(c, key):
    return float(c[key])


def _range(c):
    return max(0.0, _f(c, "high") - _f(c, "low"))


def _body(c):
    return abs(_f(c, "close") - _f(c, "open"))


def _bull(c):
    return _f(c, "close") > _f(c, "open")


def _bear(c):
    return _f(c, "close") < _f(c, "open")


def velocity(c, prev):
    return _f(c, "close") - _f(prev, "close")


def atr(candles, period=14):
    if len(candles) < 2:
        return 0.0

    trs = []

    start = max(1, len(candles) - period)

    for i in range(start, len(candles)):
        c = candles[i]
        p = candles[i - 1]

        tr = max(
            _f(c, "high") - _f(c, "low"),
            abs(_f(c, "high") - _f(p, "close")),
            abs(_f(c, "low") - _f(p, "close")),
        )

        trs.append(tr)

    return sum(trs) / len(trs) if trs else 0.0


def m5_bias(m5):
    """
    Simple structure bias.

    BUY:
      latest close > previous swing high
      and recent structure is rising.

    SELL:
      latest close < previous swing low
      and recent structure is falling.
    """

    if len(m5) < 6:
        return None

    recent = m5[-6:]

    highs = [_f(c, "high") for c in recent]
    lows = [_f(c, "low") for c in recent]
    closes = [_f(c, "close") for c in recent]

    last = closes[-1]

    mid_high = max(highs[:-1])
    mid_low = min(lows[:-1])

    rising = closes[-1] > closes[-3]
    falling = closes[-1] < closes[-3]

    if last > mid_high and rising:
        return "BUY"

    if last < mid_low and falling:
        return "SELL"

    return None


def impulse(m1):
    """
    Detect directional M1 velocity expansion.

    The current candle's velocity must exceed both:
      - minimum velocity
      - adaptive recent velocity baseline
    """

    if len(m1) < LOOKBACK + 2:
        return None

    current = m1[-1]
    previous = m1[-2]

    v = velocity(current, previous)
    av = abs(v)

    if av < MIN_VELOCITY:
        return None

    velocities = []

    start = max(1, len(m1) - LOOKBACK - 1)

    for i in range(start, len(m1) - 1):
        velocities.append(abs(velocity(m1[i], m1[i - 1])))

    baseline = median(velocities) if velocities else 0.0

    threshold = max(
        MIN_VELOCITY,
        baseline * VELOCITY_MULTIPLIER,
    )

    if av < threshold:
        return None

    if v > 0:
        return "BUY"

    if v < 0:
        return "SELL"

    return None


def pullback_reclaim(m1, direction):
    """
    Require a pullback after the impulse and then a reclaim.

    This avoids buying/selling the first large expansion candle.
    """

    if len(m1) < 4:
        return None

    impulse_c = m1[-3]
    pullback = m1[-2]
    reclaim = m1[-1]

    impulse_range = _range(impulse_c)

    if impulse_range <= 0:
        return None

    if direction == "BUY":

        impulse_high = _f(impulse_c, "high")
        impulse_low = _f(impulse_c, "low")

        pullback_low = _f(pullback, "low")

        retrace = (
            impulse_high - pullback_low
        ) / impulse_range

        if retrace > PULLBACK_MAX:
            return None

        if (
            _bull(reclaim)
            and _f(reclaim, "close") > _f(impulse_c, "close")
        ):
            return {
                "direction": "BUY",
                "entry": _f(reclaim, "close"),
                "impulse_high": impulse_high,
                "impulse_low": impulse_low,
                "pullback_low": pullback_low,
            }

    if direction == "SELL":

        impulse_high = _f(impulse_c, "high")
        impulse_low = _f(impulse_c, "low")

        pullback_high = _f(pullback, "high")

        retrace = (
            pullback_high - impulse_low
        ) / impulse_range

        if retrace > PULLBACK_MAX:
            return None

        if (
            _bear(reclaim)
            and _f(reclaim, "close") < _f(impulse_c, "close")
        ):
            return {
                "direction": "SELL",
                "entry": _f(reclaim, "close"),
                "impulse_high": impulse_high,
                "impulse_low": impulse_low,
                "pullback_high": pullback_high,
            }

    return None


def find_entry(m5, m1):
    """
    Main V5 signal.

    M5 bias
       +
    M1 impulse
       +
    M1 pullback/reclaim
    """

    bias = m5_bias(m5)

    if bias is None:
        return None

    expansion = impulse(m1)

    if expansion != bias:
        return None

    setup = pullback_reclaim(m1, bias)

    if not setup:
        return None

    entry = setup["entry"]
    current_atr = atr(m1)

    if current_atr <= 0:
        return None

    if bias == "BUY":
        sl = min(
            setup["pullback_low"],
            entry - current_atr * 1.20,
        )

        risk = entry - sl

        if risk <= 0:
            return None

        tp = entry + risk * 2.0

    else:
        sl = max(
            setup["pullback_high"],
            entry + current_atr * 1.20,
        )

        risk = sl - entry

        if risk <= 0:
            return None

        tp = entry - risk * 2.0

    rr = abs(tp - entry) / risk

    if rr < MIN_RR:
        return None

    return {
        "direction": bias,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "risk_price": risk,
        "rr": rr,
        "atr": current_atr,
        "reason": (
            "M5_BIAS+"
            "M1_VELOCITY_EXPANSION+"
            "M1_PULLBACK_RECLAIM"
        ),
    }
