from __future__ import annotations

from dataclasses import dataclass, asdict
import datetime as dt

@dataclass
class Zone:
    kind: str
    direction: str
    low: float
    high: float
    index: int
    created_at: str = ""
    broken: bool = False

@dataclass
class Signal:
    side: str
    zone_type: str
    zone_low: float
    zone_high: float
    entry_price: float
    stop_loss: float
    confirmation: str
    m5_structure: str
    protected_level: float

    def to_dict(self):
        return asdict(self)

def _f(c, k):
    return float(c[k])

def _bull(c):
    return _f(c, "close") > _f(c, "open")

def _bear(c):
    return _f(c, "close") < _f(c, "open")

def aggregate_m5(m1_candles):
    buckets = {}

    for c in m1_candles:
        t = c.get("time")
        if not t:
            continue

        try:
            if isinstance(t, str):
                ts = dt.datetime.fromisoformat(
                    t.replace("Z", "+00:00")
                )
            else:
                ts = dt.datetime.fromtimestamp(
                    float(t),
                    tz=dt.timezone.utc
                )

            ts = ts.replace(
                minute=(ts.minute // 5) * 5,
                second=0,
                microsecond=0
            )

            key = ts.isoformat()

        except Exception:
            key = str(t)

        b = buckets.get(key)

        if b is None:
            buckets[key] = {
                "time": key,
                "open": _f(c, "open"),
                "high": _f(c, "high"),
                "low": _f(c, "low"),
                "close": _f(c, "close"),
                "count": 1,
            }
        else:
            b["high"] = max(
                b["high"],
                _f(c, "high")
            )
            b["low"] = min(
                b["low"],
                _f(c, "low")
            )
            b["close"] = _f(c, "close")
            b["count"] += 1

    result = [
        v for v in buckets.values()
        if v["count"] == 5
    ]

    result.sort(key=lambda x: x["time"])

    for x in result:
        x.pop("count", None)

    return result


def _swing_high(candles, i, strength=2):
    if i < strength or i + strength >= len(candles):
        return False

    h = _f(candles[i], "high")

    return all(
        h > _f(candles[i-j], "high")
        and h > _f(candles[i+j], "high")
        for j in range(1, strength + 1)
    )


def _swing_low(candles, i, strength=2):
    if i < strength or i + strength >= len(candles):
        return False

    l = _f(candles[i], "low")

    return all(
        l < _f(candles[i-j], "low")
        and l < _f(candles[i+j], "low")
        for j in range(1, strength + 1)
    )


def _last_bos(m5, strength=2):

    highs = [
        (i, _f(c, "high"))
        for i, c in enumerate(m5)
        if _swing_high(m5, i, strength)
    ]

    lows = [
        (i, _f(c, "low"))
        for i, c in enumerate(m5)
        if _swing_low(m5, i, strength)
    ]

    events = []

    for hi, hv in highs:

        for j in range(
            hi + strength + 1,
            len(m5)
        ):

            if _f(m5[j], "close") > hv:

                protected = [
                    x for x in lows
                    if x[0] < j
                ]

                if protected:
                    events.append(
                        (
                            j,
                            "BUY",
                            hv,
                            protected[-1]
                        )
                    )

                break

    for li, lv in lows:

        for j in range(
            li + strength + 1,
            len(m5)
        ):

            if _f(m5[j], "close") < lv:

                protected = [
                    x for x in highs
                    if x[0] < j
                ]

                if protected:
                    events.append(
                        (
                            j,
                            "SELL",
                            lv,
                            protected[-1]
                        )
                    )

                break

    if not events:
        return None

    return sorted(
        events,
        key=lambda x: x[0]
    )[-1]


def detect_m5_structure(m5):

    bos = _last_bos(m5)

    if bos:

        j, side, level, protected = bos

        return {
            "direction": side,
            "protected_low":
                protected[1]
                if side == "BUY"
                else None,
            "protected_high":
                protected[1]
                if side == "SELL"
                else None,
            "bos":
                "bullish"
                if side == "BUY"
                else "bearish",
            "bos_index": j,
            "bos_level": level,
            "protected_index": protected[0],
        }

    highs = [
        (i, _f(c, "high"))
        for i, c in enumerate(m5)
        if _swing_high(m5, i)
    ]

    lows = [
        (i, _f(c, "low"))
        for i, c in enumerate(m5)
        if _swing_low(m5, i)
    ]

    if len(highs) >= 2 and len(lows) >= 2:

        h1, h2 = highs[-2:]
        l1, l2 = lows[-2:]

        if (
            h2[1] > h1[1]
            and l2[1] > l1[1]
        ):
            return {
                "direction": "BUY",
                "protected_low": l2[1],
                "protected_high": h2[1],
                "bos": None,
            }

        if (
            h2[1] < h1[1]
            and l2[1] < l1[1]
        ):
            return {
                "direction": "SELL",
                "protected_low": l2[1],
                "protected_high": h2[1],
                "bos": None,
            }

    return {
        "direction": "NEUTRAL",
        "protected_low": None,
        "protected_high": None,
        "bos": None,
    }


def detect_m5_fvg(m5, max_age=40):

    zones = []

    for i in range(
        max(2, len(m5) - max_age),
        len(m5)
    ):

        a, _, c = (
            m5[i-2],
            m5[i-1],
            m5[i]
        )

        if _f(a, "high") < _f(c, "low"):

            zones.append(
                Zone(
                    "FVG",
                    "BUY",
                    _f(a, "high"),
                    _f(c, "low"),
                    i,
                    str(c.get("time", ""))
                )
            )

        elif _f(a, "low") > _f(c, "high"):

            zones.append(
                Zone(
                    "FVG",
                    "SELL",
                    _f(c, "high"),
                    _f(a, "low"),
                    i,
                    str(c.get("time", ""))
                )
            )

    return zones


def detect_m5_order_blocks(m5, max_age=40):

    zones = []

    bos = _last_bos(m5)

    end = bos[0] + 1 if bos else len(m5)

    for i in range(
        max(1, end - max_age),
        end
    ):

        if _bear(m5[i]):

            for j in range(
                i + 1,
                min(i + 4, end)
            ):

                if (
                    _bull(m5[j])
                    and _f(m5[j], "close")
                    > _f(m5[i], "high")
                ):

                    zones.append(
                        Zone(
                            "OB",
                            "BUY",
                            _f(m5[i], "low"),
                            _f(m5[i], "high"),
                            i,
                            str(m5[i].get("time", ""))
                        )
                    )

                    break

        elif _bull(m5[i]):

            for j in range(
                i + 1,
                min(i + 4, end)
            ):

                if (
                    _bear(m5[j])
                    and _f(m5[j], "close")
                    < _f(m5[i], "low")
                ):

                    zones.append(
                        Zone(
                            "OB",
                            "SELL",
                            _f(m5[i], "low"),
                            _f(m5[i], "high"),
                            i,
                            str(m5[i].get("time", ""))
                        )
                    )

                    break

    return zones


def detect_m5_breakers(m5, max_age=50):

    out = []

    for ob in detect_m5_order_blocks(
        m5,
        max_age
    ):

        for j in range(
            ob.index + 1,
            len(m5)
        ):

            close = _f(
                m5[j],
                "close"
            )

            if (
                ob.direction == "BUY"
                and close < ob.low
            ):

                out.append(
                    Zone(
                        "BREAKER",
                        "SELL",
                        ob.low,
                        ob.high,
                        j,
                        str(m5[j].get("time", "")),
                        True
                    )
                )

                break

            if (
                ob.direction == "SELL"
                and close > ob.high
            ):

                out.append(
                    Zone(
                        "BREAKER",
                        "BUY",
                        ob.low,
                        ob.high,
                        j,
                        str(m5[j].get("time", "")),
                        True
                    )
                )

                break

    return out


def _zone_still_valid(zone, m5):

    for c in m5[zone.index + 1:]:

        close = _f(
            c,
            "close"
        )

        if (
            zone.direction == "BUY"
            and close < zone.low
        ):
            return False

        if (
            zone.direction == "SELL"
            and close > zone.high
        ):
            return False

    return True


def _touches_zone(
    c,
    zone,
    buffer=0.03
):

    return (
        _f(c, "low")
        <= zone.high + buffer
        and
        _f(c, "high")
        >= zone.low - buffer
    )


def _bullish_rejection(c):

    o, h, l, cl = (
        _f(c, k)
        for k in (
            "open",
            "high",
            "low",
            "close"
        )
    )

    body = abs(cl - o)
    rng = h - l

    if rng <= 0 or cl <= o:
        return False

    lower_wick = (
        min(o, cl) - l
    )

    return (
        lower_wick
        >= max(
            body * 1.2,
            rng * 0.30
        )
        and
        cl >= l + rng * 0.60
    )


def _bearish_rejection(c):

    o, h, l, cl = (
        _f(c, k)
        for k in (
            "open",
            "high",
            "low",
            "close"
        )
    )

    body = abs(cl - o)
    rng = h - l

    if rng <= 0 or cl >= o:
        return False

    upper_wick = (
        h - max(o, cl)
    )

    return (
        upper_wick
        >= max(
            body * 1.2,
            rng * 0.30
        )
        and
        cl <= l + rng * 0.40
    )


def _bullish_engulfing(prev, c):

    return (
        _bear(prev)
        and _bull(c)
        and _f(c, "open")
        <= _f(prev, "close")
        and _f(c, "close")
        >= _f(prev, "open")
    )


def _bearish_engulfing(prev, c):

    return (
        _bull(prev)
        and _bear(c)
        and _f(c, "open")
        >= _f(prev, "close")
        and _f(c, "close")
        <= _f(prev, "open")
    )


def confirm_m1(
    m1,
    zone,
    buffer=0.03
):

    if len(m1) < 2:
        return None

    c = m1[-1]
    prev = m1[-2]

    if not _touches_zone(
        c,
        zone,
        buffer
    ):
        return None

    if zone.direction == "BUY":

        if _bullish_engulfing(
            prev,
            c
        ):
            return "ENGULFING"

        if _bullish_rejection(c):
            return "REJECTION"

    else:

        if _bearish_engulfing(
            prev,
            c
        ):
            return "ENGULFING"

        if _bearish_rejection(c):
            return "REJECTION"

    return None


def find_entry(
    m1_completed,
    bid,
    ask,
    zone_buffer=0.03,
    sl_buffer=0.05
):

    m5 = aggregate_m5(
        m1_completed
    )

    if (
        len(m5) < 15
        or len(m1_completed) < 10
    ):
        return None

    structure = detect_m5_structure(m5)

    side = structure["direction"]

    if side not in (
        "BUY",
        "SELL"
    ):
        return None

    protected = (
        structure.get("protected_low")
        if side == "BUY"
        else structure.get("protected_high")
    )

    if protected is None:
        return None

    bos_index = structure.get(
        "bos_index"
    )

    zones = (
        detect_m5_fvg(m5)
        + detect_m5_order_blocks(m5)
        + detect_m5_breakers(m5)
    )

    zones = [
        z for z in zones
        if (
            z.direction == side
            and _zone_still_valid(
                z,
                m5
            )
            and (
                bos_index is None
                or z.index <= bos_index
            )
        )
    ]

    zones.sort(
        key=lambda z: z.index,
        reverse=True
    )

    for zone in zones:

        confirmation = confirm_m1(
            m1_completed,
            zone,
            zone_buffer
        )

        if not confirmation:
            continue

        entry = (
            ask
            if side == "BUY"
            else bid
        )

        sl = (
            zone.low - sl_buffer
            if side == "BUY"
            else zone.high + sl_buffer
        )

        if (
            side == "BUY"
            and sl >= entry
        ):
            continue

        if (
            side == "SELL"
            and sl <= entry
        ):
            continue

        return Signal(
            side,
            zone.kind,
            zone.low,
            zone.high,
            entry,
            sl,
            confirmation,
            (
                "BULLISH"
                if side == "BUY"
                else "BEARISH"
            ),
            protected
        )

    return None
