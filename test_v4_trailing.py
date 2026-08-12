POINT_SIZE = 0.01
BE_TRIGGER = 300 * POINT_SIZE
TRAIL_DISTANCE = 300 * POINT_SIZE


def target(entry, side, price, previous_sl):
    favorable = price - entry if side == "BUY" else entry - price

    if favorable < BE_TRIGGER:
        return None

    steps = int(favorable // TRAIL_DISTANCE)

    target_sl = (
        entry + (steps - 1) * TRAIL_DISTANCE
        if side == "BUY"
        else entry - (steps - 1) * TRAIL_DISTANCE
    )

    if side == "BUY":
        return target_sl if target_sl > previous_sl else None

    return target_sl if target_sl < previous_sl else None


# BUY
entry = 4400.0
sl = 4397.0

sl = target(entry, "BUY", 4403.0, sl)
assert sl == 4400.0

sl = target(entry, "BUY", 4406.0, sl)
assert sl == 4403.0

sl = target(entry, "BUY", 4409.0, sl)
assert sl == 4406.0


# SELL
entry = 4400.0
sl = 4403.0

sl = target(entry, "SELL", 4397.0, sl)
assert sl == 4400.0

sl = target(entry, "SELL", 4394.0, sl)
assert sl == 4397.0

sl = target(entry, "SELL", 4391.0, sl)
assert sl == 4394.0


print()
print("========================================")
print(" V4 TRAILING TEST PASSED")
print("========================================")
print()
print("BUY:")
print("Entry 4400")
print("Price 4403 -> SL 4400 BE")
print("Price 4406 -> SL 4403")
print("Price 4409 -> SL 4406")
print()
print("SELL:")
print("Entry 4400")
print("Price 4397 -> SL 4400 BE")
print("Price 4394 -> SL 4397")
print("Price 4391 -> SL 4394")
