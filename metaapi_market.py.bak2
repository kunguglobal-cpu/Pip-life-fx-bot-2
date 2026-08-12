import os
import asyncio
from datetime import datetime, timezone

from metaapi_cloud_sdk import MetaApi


class MetaAPIMarket:
    """
    Persistent synchronous wrapper around MetaApi async SDK.

    One MetaApi/RPC connection is maintained for the lifetime of this object.
    """

    def __init__(self, token=None, account_id=None):
        self.token = token or os.getenv("METAAPI_TOKEN")
        self.account_id = account_id or os.getenv("METAAPI_ACCOUNT_ID")

        if not self.token:
            raise RuntimeError(
                "METAAPI_TOKEN is not set."
            )

        if not self.account_id:
            raise RuntimeError(
                "METAAPI_ACCOUNT_ID is not set."
            )

        self._api = None
        self._account_obj = None
        self._connection = None
        self._ready = False

    async def _connect(self):
        if self._ready and self._connection is not None:
            return

        self._api = MetaApi(self.token)

        self._account_obj = (
            await self._api.metatrader_account_api.get_account(
                self.account_id
            )
        )

        await self._account_obj.wait_connected()

        self._connection = self._account_obj.get_rpc_connection()

        await self._connection.connect()
        await self._connection.wait_synchronized()

        self._ready = True

        print(
            f"MetaAPI MARKET CONNECTED | "
            f"account={self.account_id}"
        )

    async def _candles_async(self, symbol, limit):
        await self._connect()

        try:
            return await self._account_obj.get_historical_candles(
                symbol=symbol,
                timeframe="1m",
                start_time=None,
                limit=int(limit),
            )

        except Exception:
            # Connection may have died. Force reconnect on next request.
            self._ready = False
            raise

    async def _price_async(self, symbol):
        await self._connect()

        try:
            p = await self._connection.get_symbol_price(symbol)

            return {
                "symbol": symbol,
                "bid": float(p.get("bid", 0.0)),
                "ask": float(p.get("ask", 0.0)),
                "time": p.get("time"),
            }

        except Exception:
            self._ready = False
            raise

    def _run(self, coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, coro).result()

    def candles(self, symbol, limit=200):
        rows = self._run(
            self._candles_async(symbol, limit)
        )

        out = []

        for c in rows:
            out.append({
                "time": c.get("time") or c.get("brokerTime"),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": float(
                    c.get(
                        "volume",
                        c.get("tickVolume", 0)
                    )
                ),
                "spread": float(c.get("spread", 0)),
            })

        return out

    def price(self, symbol):
        return self._run(
            self._price_async(symbol)
        )
