import json, os, urllib.request, urllib.error

class MetaAPITrade:
    BASE = "https://mt-client-api-v1.new-york.agiliumtrade.ai/users/current/accounts"

    def __init__(self, dry_run=True):
        self.token = os.getenv("METAAPI_TOKEN")
        self.account_id = os.getenv("METAAPI_ACCOUNT_ID")
        self.dry_run = dry_run
        if not self.token: raise RuntimeError("METAAPI_TOKEN is not set")
        if not self.account_id: raise RuntimeError("METAAPI_ACCOUNT_ID is not set")

    def _request(self, payload):
        url = f"{self.BASE}/{self.account_id}/trade"
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"auth-token":self.token, "Content-Type":"application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"MetaAPI trade HTTP {e.code}: {e.read().decode(errors='replace')}")

    def _do(self, payload):
        print("TRADE:", payload, "| DRY_RUN:", self.dry_run)
        if self.dry_run: return {"dry_run": True, "payload": payload}
        return self._request(payload)

    def buy(self, symbol, volume, sl=None):
        p={"actionType":"ORDER_TYPE_BUY","symbol":symbol,"volume":float(volume)}
        if sl is not None: p["stopLoss"]=float(sl)
        return self._do(p)

    def sell(self, symbol, volume, sl=None):
        p={"actionType":"ORDER_TYPE_SELL","symbol":symbol,"volume":float(volume)}
        if sl is not None: p["stopLoss"]=float(sl)
        return self._do(p)

    def close(self, position_id):
        return self._do({"actionType":"POSITION_CLOSE_ID","positionId":str(position_id)})

    def modify_sl(self, position_id, sl):
        return self._do({"actionType":"POSITION_MODIFY","positionId":str(position_id),"stopLoss":float(sl)})

    def positions(self):
        # Used by the runner to recover after restart.
        url=f"{self.BASE}/{self.account_id}/positions"
        req=urllib.request.Request(url,headers={"auth-token":self.token,"Accept":"application/json"})
        try:
            with urllib.request.urlopen(req,timeout=20) as r:
                data=json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"MetaAPI positions HTTP {e.code}: {e.read().decode(errors='replace')}")
        return data
