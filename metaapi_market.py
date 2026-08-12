import os
import asyncio
import threading
from concurrent.futures import Future

from metaapi_cloud_sdk import MetaApi


class MetaAPIMarket:
    """
    Persistent MetaApi market-data connection.

    Keeps one MetaApi SDK/account/RPC connection alive instead of
    creating a new websocket client on every candles()/price() call.
    """

    def __init__(self, token=None, account_id=None):
        self.token = token or os.getenv("METAAPI_TOKEN")
        self.account_id = account_id or os.getenv("METAAPI_ACCOUNT_ID")

        if not self.token:
            raise RuntimeError("METAAPI_TOKEN is not set")

        if not self.account_id:
            raise RuntimeError("METAAPI_ACCOUNT_ID is not set")

        self.api = None
        self.account = None
        self.connection = None

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop_worker,
            daemon=True,
            name="metaapi-market-loop",
        )
        self._thread.start()

        self._run(self._connect())

        print(
            "MetaAPI MARKET CONNECTED | "
            f"account={self.account_id}"
        )

    def _loop_worker(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run(self, coro):
        future = asyncio.run_coroutine_threadsafe(
            coro,
            self._loop,
        )
        return future.result()

    async def _connect(self):
        self.api = MetaApi(self.token)

        self.account = await self.api.metatrader_account_api.get_account(
            self.account_id
        )

        await self.account.wait_connected()

        self.connection = self.account.get_rpc_connection()

        await self.connection.connect()
        await self.connection.wait_synchronized()

    async def _candles_async(self, symbol, limit):
        candles = await self.account.get_historical_candles(
            symbol=symbol,
            timeframe="1m",
            start_time=None,
            limit=int(limit),
        )

        return [
            {
                "time": c.get("time") or c.get("brokerTime"),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": float(
                    c.get("volume", c.get("tickVolume", 0))
                ),
                "spread": float(c.get("spread", 0)),
            }
            for c in candles
        ]

    async def _price_async(self, symbol):
        p = await self.connection.get_symbol_price(symbol)

        return {
            "symbol": symbol,
            "bid": float(p.get("bid", 0.0)),
            "ask": float(p.get("ask", 0.0)),
            "time": p.get("time"),
        }

    def candles(self, symbol, limit=200):
        return self._run(
            self._candles_async(symbol, limit)
        )

    def price(self, symbol):
        return self._run(
            self._price_async(symbol)
        )

    def close(self):
        """
        Cleanly close the RPC connection and MetaApi SDK.
        """
        if self._loop.is_closed():
            return

        async def _close():
            try:
                if self.connection:
                    await self.connection.close()
            except Exception as e:
                print("MetaAPI RPC CLOSE WARNING:", repr(e))

            try:
                if self.api:
                    result = self.api.close()

                    if asyncio.iscoroutine(result):
                        await result
            except Exception as e:
                print("MetaAPI SDK CLOSE WARNING:", repr(e))

        try:
            self._run(_close())
        finally:
            self._loop.call_soon_threadsafe(
                self._loop.stop
            )

            if self._thread.is_alive():
                self._thread.join(timeout=5)

            self._loop.close()

            self.connection = None
            self.account = None
            self.api = None

            print("MetaAPI MARKET CLOSED")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
