# M1 XAUUSD V4 — M5 Zone / M1 Confirmation Scalper

V4 is a separate entry model from the previous volatility-only V3/V4 runner.

## Entry model

1. **M5 market structure**
   - Bullish BOS / continuation -> BUY bias.
   - Bearish BOS / continuation -> SELL bias.
   - Protected M5 swing must remain intact.

2. **M5 institutional zone**
   - Fair Value Gap (FVG)
   - Order Block (OB)
   - Breaker Block (derived from a broken M5 OB)

3. **M1 confirmation**
   Price must interact with the selected M5 zone and the latest completed M1 candle must show either:
   - rejection candle, or
   - engulfing candle.

4. **Entry**
   - BUY at current ask after bullish M1 confirmation.
   - SELL at current bid after bearish M1 confirmation.

5. **Initial SL**
   - BUY: below the respected M5 zone.
   - SELL: above the respected M5 zone.
   - The protected M5 swing must remain intact.

6. **Management**
   - No fixed take-profit.
   - Move SL to break-even after `M1_V4_BE_TRIGGER` favorable movement.
   - Then use stepped trailing: every additional `M1_V4_TRAIL_DISTANCE`
     of favorable movement from the previous SL advances the SL by the
     same 300-point distance.
   - The SL does NOT continuously follow price and does NOT update every
     10 points.
   - Stop only moves in the direction that reduces risk.

## Files

- `m1_v4_strategy.py` — pure M5/M1 setup detector.
- `m1_v4_runner.py` — continuous MetaAPI execution runner.
- `m1_v4_backtest.py` — read-only historical test.

Existing V3/V4 files are not required by the new strategy engine.

## Termux test

```bash
cd ~/m1-xau-volatility/m1-xau-volatility-v3

export M1_DRY_RUN=true
export METAAPI_TOKEN='YOUR_EXISTING_TOKEN'
export METAAPI_ACCOUNT_ID='YOUR_EXISTING_ACCOUNT_ID'

python m1_v4_backtest.py
python m1_v4_runner.py
```

For demo execution only, change:

```bash
export M1_DRY_RUN=false
```

## Main parameters

```text
M1_V4_BE_TRIGGER=0.50
M1_V4_TRAIL_DISTANCE=0.50
M1_V4_ZONE_BUFFER=0.03
M1_V4_SL_BUFFER=0.05
M1_V4_MAX_LOT=0.01
```

Keep `M1_DRY_RUN=true` until the read-only backtest and live dry-run logs are reviewed.


## V4 Stop Management — Updated

The V4 management rules are now point-based:

- Initial SL: **300 points**
- Break-even trigger: **+300 points**
- Trailing SL distance/step: **300 points**
- After BE, every additional **+300 points from the previous SL** advances
  the SL by exactly **300 points**
- No continuous 10-point trailing
- No fixed take-profit

Default XAUUSD point size is `0.01`, so 300 points equals `3.00` price units.
If the broker's XAUUSD symbol uses a different point size, set:

```bash
export M1_V4_POINT_SIZE=0.01
```

The M5 FVG/OB/Breaker remains the entry location/context and M1 rejection/engulfing remains the confirmation. The initial SL is fixed at 300 points.

### Stepped trailing example — BUY
Entry = 4400.00  
Initial SL = 4397.00  
At +300 points, SL -> 4400.00 (BE)  
When price reaches 4403.00, SL -> 4403.00  
When price reaches 4406.00, SL -> 4406.00  
When price reaches 4409.00, SL -> 4409.00  

The SELL side mirrors this logic in the opposite direction.


## Locked trailing rule

The V4 stop is **entry-anchored**, not continuously price-following.

For a BUY at 4400.00:
- initial SL = 4397.00 minimum protection (300 points)
- price 4403.00 -> SL 4400.00 (BE)
- price 4406.00 -> SL 4403.00
- price 4409.00 -> SL 4406.00
- price 4412.00 -> SL 4409.00

For a SELL at 4400.00:
- initial SL = 4403.00 minimum protection (300 points)
- price 4397.00 -> SL 4400.00 (BE)
- price 4394.00 -> SL 4397.00
- price 4391.00 -> SL 4394.00

The SL only moves in the profitable direction. There is no fixed TP.
