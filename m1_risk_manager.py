import math
import os


def risk_percent(balance):
    """
    V4 risk policy.

    Default:
        1% of account balance per trade.

    Can be overridden with:
        M1_V4_RISK_PERCENT
    """
    configured = float(
        os.getenv("M1_V4_RISK_PERCENT", "1.0")
    )

    if balance <= 0:
        return 0.0

    return configured / 100.0


def calculate_lot_size(
    balance,
    entry,
    stop_loss,
    value_per_price_unit=100.0,
    max_lot=1.0,
):
    """
    Calculate position size from account risk.

    Risk amount:
        balance * risk_percent(balance)

    Price risk:
        abs(entry - stop_loss)

    Monetary risk per 1.00 lot:
        price risk * value_per_price_unit

    Returns a broker-friendly lot size.
    """

    balance = float(balance)
    entry = float(entry)
    stop_loss = float(stop_loss)
    value_per_price_unit = float(value_per_price_unit)
    max_lot = float(max_lot)

    if balance <= 0:
        return 0.0

    if value_per_price_unit <= 0:
        return 0.0

    if max_lot <= 0:
        return 0.0

    price_risk = abs(entry - stop_loss)

    if price_risk <= 0:
        return 0.0

    risk_amount = balance * risk_percent(balance)

    if risk_amount <= 0:
        return 0.0

    risk_per_lot = (
        price_risk *
        value_per_price_unit
    )

    if risk_per_lot <= 0:
        return 0.0

    raw_volume = (
        risk_amount /
        risk_per_lot
    )

    # XAUUSD lot sizing normally uses 0.01 lot increments.
    volume_step = float(
        os.getenv("M1_V4_VOLUME_STEP", "0.01")
    )

    min_lot = float(
        os.getenv("M1_V4_MIN_LOT", "0.01")
    )

    if volume_step <= 0:
        volume_step = 0.01

    if min_lot <= 0:
        min_lot = volume_step

    volume = (
        math.floor(
            raw_volume / volume_step
        ) * volume_step
    )

    volume = min(
        volume,
        max_lot
    )

    if volume < min_lot:
        return 0.0

    return round(
        volume,
        2
    )
