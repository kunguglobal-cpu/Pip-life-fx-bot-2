import json
import os
import urllib.error
import urllib.request


class MetaAPITrade:
    BASE = "https://mt-client-api-v1.new-york.agiliumtrade.ai/users/current/accounts"

    def __init__(self, dry_run=True):
        self.token = os.getenv("METAAPI_TOKEN")
        self.account_id = os.getenv("METAAPI_ACCOUNT_ID")
        self.dry_run = dry_run

        if not self.token:
            raise RuntimeError("METAAPI_TOKEN is not set")
        if not self.account_id:
            raise RuntimeError("METAAPI_ACCOUNT_ID is not set")

    def _request(self, payload):
        url = f"{self.BASE}/{self.account_id}/trade"

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "auth-token": self.token,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"MetaAPI trade HTTP {e.code}: "
                f"{e.read().decode(errors='replace')}"
            )

    def _get(self, path):
        url = f"{self.BASE}/{self.account_id}/{path}"

        req = urllib.request.Request(
            url,
            headers={
                "auth-token": self.token,
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"MetaAPI HTTP {e.code}: "
                f"{e.read().decode(errors='replace')}"
            )

    def _do(self, payload):
        print("TRADE:", payload, "| DRY_RUN:", self.dry_run)

        if self.dry_run:
            return {
                "dry_run": True,
                "payload": payload,
            }

        return self._request(payload)

    def buy(self, symbol, volume, sl=None, tp=None):
        payload = {
            "actionType": "ORDER_TYPE_BUY",
            "symbol": symbol,
            "volume": float(volume),
        }

        if sl is not None:
            payload["stopLoss"] = float(sl)

        if tp is not None:
            payload["takeProfit"] = float(tp)

        return self._do(payload)

    def sell(self, symbol, volume, sl=None, tp=None):
        payload = {
            "actionType": "ORDER_TYPE_SELL",
            "symbol": symbol,
            "volume": float(volume),
        }

        if sl is not None:
            payload["stopLoss"] = float(sl)

        if tp is not None:
            payload["takeProfit"] = float(tp)

        return self._do(payload)

    def close(self, position_id):
        return self._do({
            "actionType": "POSITION_CLOSE_ID",
            "positionId": str(position_id),
        })

    def modify_position(self, position_id, sl):
        return self._do({
            "actionType": "POSITION_MODIFY",
            "positionId": str(position_id),
            "stopLoss": float(sl),
        })

    def modify_sl(self, position_id, sl):
        return self.modify_position(position_id, sl)

    def positions(self, symbol=None):
        data = self._get("positions")

        if symbol is None:
            return data

        return [
            p for p in data
            if str(p.get("symbol", "")).upper()
            == str(symbol).upper()
        ]

    def account_information(self):
        return self._get("accountInformation")
