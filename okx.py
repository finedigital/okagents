import hmac
import hashlib
import base64
import time
import json
import requests

BASE = "https://us.okx.com"


def get_token_price(token: str) -> float:
    inst_id = f"{token.upper()}-USDT"
    r = requests.get(f"{BASE}/api/v5/market/ticker?instId={inst_id}")
    return float(r.json()["data"][0]["last"])


def get_btc_price() -> float:
    return get_token_price("BTC")


def _sign(ts, method, path, body, secret):
    msg = ts + method + path + (body or "")
    return base64.b64encode(
        hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
    ).decode()


def place_market_buy(inst_id, usd_sz, user):
    ts = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    body = json.dumps({
        "instId": inst_id,
        "tdMode": "cash",
        "side": "buy",
        "ordType": "market",
        "sz": str(usd_sz),
    })
    path = "/api/v5/trade/order"
    headers = {
        "Content-Type": "application/json",
        "OK-ACCESS-KEY": user["key"],
        "OK-ACCESS-SIGN": _sign(ts, "POST", path, body, user["secret"]),
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": user["passphrase"],
    }
    return requests.post(BASE + path, headers=headers, data=body).json()
