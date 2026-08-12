import os, json, urllib.request, urllib.error
BASE="https://mt-client-api-v1.new-york.agiliumtrade.ai/users/current/accounts"
class MetaAPITrade:
    def __init__(self,dry_run=True):
        self.token=os.getenv("METAAPI_TOKEN"); self.account_id=os.getenv("METAAPI_ACCOUNT_ID"); self.dry_run=dry_run
        if not self.token or not self.account_id: raise RuntimeError("METAAPI_TOKEN and METAAPI_ACCOUNT_ID are required")
    def _headers(self,content=False):
        h={"auth-token":self.token,"Accept":"application/json"}
        if content: h["Content-Type"]="application/json"
        return h
    def _get(self,path):
        req=urllib.request.Request(f"{BASE}/{self.account_id}/{path}",headers=self._headers())
        with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read().decode())
    def _post(self,payload):
        if self.dry_run: return {"dry_run":True,"payload":payload,"position_id":"DRY_RUN"}
        req=urllib.request.Request(f"{BASE}/{self.account_id}/trade",data=json.dumps(payload).encode(),headers=self._headers(True),method="POST")
        try:
            with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read().decode())
        except urllib.error.HTTPError as e: raise RuntimeError(f"MetaAPI trade HTTP {e.code}: {e.read().decode(errors='replace')}")
    def account_information(self): return self._get("account-information")
    def positions(self,symbol=None):
        p=self._get("positions")
        return [x for x in p if not symbol or str(x.get("symbol","")).upper()==str(symbol).upper()]
    def buy(self,symbol,volume,sl=None,tp=None):
        p={"actionType":"ORDER_TYPE_BUY","symbol":symbol,"volume":float(volume)}
        if sl is not None:p["stopLoss"]=float(sl)
        if tp is not None:p["takeProfit"]=float(tp)
        return self._post(p)
    def sell(self,symbol,volume,sl=None,tp=None):
        p={"actionType":"ORDER_TYPE_SELL","symbol":symbol,"volume":float(volume)}
        if sl is not None:p["stopLoss"]=float(sl)
        if tp is not None:p["takeProfit"]=float(tp)
        return self._post(p)
    def modify_position(self,position_id,sl):
        return self._post({"actionType":"POSITION_MODIFY","positionId":str(position_id),"stopLoss":float(sl)})
    def close(self,position_id):
        return self._post({"actionType":"POSITION_CLOSE_ID","positionId":str(position_id)})
