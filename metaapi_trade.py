import json
import os
import urllib.error
import urllib.request
import uuid


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

        # Local simulated positions used only in DRY_RUN mode.
        self._dry_positions = {}

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

        if self.dry_run:
            position_id = f"DRY-{uuid.uuid4().hex[:12]}"

            self._dry_positions[position_id] = {
                "id": position_id,
                "positionId": position_id,
                "symbol": symbol,
                "type": "POSITION_TYPE_BUY",
                "volume": float(volume),
                "openPrice": None,
                "stopLoss": None if sl is None else float(sl),
                "takeProfit": None if tp is None else float(tp),
            }

            print(
                f"DRY RUN POSITION OPENED | "
                f"{position_id} | BUY | "
                f"{symbol} | volume={float(volume):.2f}"
            )

            return {
                "dry_run": True,
                "position_id": position_id,
                "payload": payload,
            }

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

        if self.dry_run:
            position_id = f"DRY-{uuid.uuid4().hex[:12]}"

            self._dry_positions[position_id] = {
                "id": position_id,
                "positionId": position_id,
                "symbol": symbol,
                "type": "POSITION_TYPE_SELL",
                "volume": float(volume),
                "openPrice": None,
                "stopLoss": None if sl is None else float(sl),
                "takeProfit": None if tp is None else float(tp),
            }

            print(
                f"DRY RUN POSITION OPENED | "
                f"{position_id} | SELL | "
                f"{symbol} | volume={float(volume):.2f}"
            )

            return {
                "dry_run": True,
                "position_id": position_id,
                "payload": payload,
            }

        return self._do(payload)

    def close(self, position_id):
        position_id = str(position_id)

        if self.dry_run:
            existed = self._dry_positions.pop(
                position_id,
                None,
            )

            print(
                f"DRY RUN POSITION CLOSED | "
                f"{position_id} | existed={existed is not None}"
            )

            return {
                "dry_run": True,
                "position_id": position_id,
                "closed": existed is not None,
            }

        return self._do({
            "actionType": "POSITION_CLOSE_ID",
            "positionId": position_id,
        })

    def modify_position(self, position_id, sl):
        position_id = str(position_id)
        sl = float(sl)

        if self.dry_run:
            position = self._dry_positions.get(position_id)

            if position is None:
                print(
                    f"DRY RUN MODIFY FAILED | "
                    f"position={position_id} not found"
                )
                return False

            position["stopLoss"] = sl

            print(
                f"DRY RUN SL MODIFIED | "
                f"position={position_id} | "
                f"SL={sl:.2f}"
            )

            return True

        return self._do({
            "actionType": "POSITION_MODIFY",
            "positionId": position_id,
            "stopLoss": sl,
        })

    def modify_sl(self, position_id, sl):
        return self.modify_position(position_id, sl)

    def positions(self, symbol=None):
        if self.dry_run:
            data = list(self._dry_positions.values())
        else:
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
