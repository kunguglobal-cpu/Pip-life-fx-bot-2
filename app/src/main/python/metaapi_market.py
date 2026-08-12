import os, json, urllib.request, urllib.parse
from datetime import datetime, timezone

CLIENT = "https://mt-client-api-v1.new-york.agiliumtrade.ai"
MARKET = "https://mt-market-data-client-api-v1.new-york.agiliumtrade.ai"

class MetaAPIMarket:
    def __init__(self, token=None, account_id=None):
        self.token = token or os.getenv("METAAPI_TOKEN")
        self.account_id = account_id or os.getenv("METAAPI_ACCOUNT_ID")
        if not self.token or not self.account_id:
            raise RuntimeError("METAAPI_TOKEN and METAAPI_ACCOUNT_ID are required")
    def _get(self, base, path, params=None):
        url = base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"auth-token":self.token,"Accept":"application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    def candles(self, symbol, limit=200):
        data=self._get(MARKET, f"/users/current/accounts/{self.account_id}/historical-market-data/symbols/{urllib.parse.quote(symbol)}/timeframes/1m/candles", {"limit":min(int(limit),1000)})
        out=[]
        for c in data:
            t=c.get("time") or c.get("brokerTime")
            try: ts=datetime.fromisoformat(str(t).replace("Z","+00:00"))
            except Exception: ts=t
            out.append({"time":ts,"open":float(c["open"]),"high":float(c["high"]),"low":float(c["low"]),"close":float(c["close"]),"volume":float(c.get("volume",c.get("tickVolume",0))),"spread":float(c.get("spread",0))})
        out.sort(key=lambda x:str(x["time"]))
        return out
    def price(self, symbol):
        p=self._get(CLIENT, f"/users/current/accounts/{self.account_id}/symbols/{urllib.parse.quote(symbol)}/current-tick")
        return {"symbol":symbol,"bid":float(p.get("bid",0)),"ask":float(p.get("ask",0)),"time":p.get("time")}
