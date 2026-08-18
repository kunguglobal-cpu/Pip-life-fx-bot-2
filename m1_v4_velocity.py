"""Adaptive M1 velocity-expansion confirmation for V4."""

import os
import statistics


def _f(c, key):
    return float(c[key])


def _touches_zone(c, zone, buffer):
    return (
        _f(c, "low") <= float(zone.high) + buffer
        and _f(c, "high") >= float(zone.low) - buffer
    )


def _velocity(c, prev):
    # XAUUSD price displacement over one completed M1 candle.
    return _f(c, "close") - _f(prev, "close")


def confirm_m1_velocity(m1, zone, buffer=0.03):
    """
    M5 zone touch + directional M1 velocity expansion.

    Trigger:
      - latest completed M1 candle touches the zone
      - velocity agrees with BUY/SELL direction
      - current velocity >= max(minimum velocity,
        median recent velocity * expansion multiplier)
    """

    if len(m1) < 4:
        return None

    trigger = m1[-1]

    if not _touches_zone(trigger, zone, float(buffer)):
        return None

    lookback = int(
        os.getenv("M1_V4_VELOCITY_LOOKBACK", "10")
    )

    multiplier = float(
        os.getenv("M1_V4_VELOCITY_MULTIPLIER", "1.50")
    )

    min_velocity = float(
        os.getenv("M1_V4_MIN_VELOCITY", "0.03")
    )

    current = _velocity(m1[-1], m1[-2])

    direction = str(zone.direction).upper()

    if direction == "BUY" and current <= 0:
        return None

    if direction == "SELL" and current >= 0:
        return None

    if direction not in ("BUY", "SELL"):
        return None

    # Previous candles form the adaptive velocity baseline.
    history = m1[:-1]

    changes = [
        abs(_velocity(history[i], history[i - 1]))
        for i in range(1, len(history))
    ]

    changes = changes[-max(2, lookback):]

    if not changes:
        return None

    baseline = statistics.median(changes)

    threshold = max(
        min_velocity,
        baseline * multiplier
    )

    if abs(current) < threshold:
        return None

    expansion = (
        abs(current) / baseline
        if baseline > 0
        else float("inf")
    )

    return (
        f"VELOCITY_EXPANSION"
        f"(v={current:+.3f},"
        f"base={baseline:.3f},"
        f"x={expansion:.2f})"
    )
