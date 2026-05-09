"""
WebSocket client untuk MT5 Bridge.

Usage:
  python mt5_ws_client.py                    # semua tick
  python mt5_ws_client.py EURUSD             # satu symbol
  python mt5_ws_client.py --simulate         # kirim fake tick tiap 1 detik
"""
import asyncio
import json
import sys
import random
import time
import urllib.request


BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"


async def watch_all():
    import websockets
    url = f"{WS_BASE}/ws/ticks"
    print(f"[ws] Connecting to {url}")
    async with websockets.connect(url) as ws:
        print("[ws] Connected — menunggu tick...")
        async for msg in ws:
            data = json.loads(msg)
            ticks = data.get("ticks", [])
            ts = time.strftime("%H:%M:%S")
            for t in ticks:
                print(f"[{ts}] {t['symbol']:10s}  bid={t['bid']:.5f}  ask={t['ask']:.5f}")


async def watch_symbol(symbol: str):
    import websockets
    url = f"{WS_BASE}/ws/tick/{symbol}"
    print(f"[ws] Connecting to {url}")
    async with websockets.connect(url) as ws:
        print(f"[ws] Connected — menunggu {symbol.upper()}...")
        async for msg in ws:
            t = json.loads(msg)
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] {t.get('symbol','?'):10s}  bid={t.get('bid',0):.5f}  ask={t.get('ask',0):.5f}")


def simulate():
    symbols = [
        ("EURUSD", 1.08500, 0.00010),
        ("XAUUSD", 2300.00, 0.50),
        ("BTCUSD", 65000.00, 10.0),
    ]
    print(f"[sim] Mengirim fake tick ke {BASE}/push setiap 1 detik...")
    while True:
        ticks = []
        for sym, base_price, spread in symbols:
            bid = round(base_price + random.uniform(-0.0005, 0.0005) * base_price, 5)
            ask = round(bid + spread, 5)
            ticks.append({"symbol": sym, "bid": bid, "ask": ask, "time": int(time.time())})
        payload = json.dumps({"ticks": ticks}).encode()
        req = urllib.request.Request(
            f"{BASE}/push",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=2)
            ts = time.strftime("%H:%M:%S")
            for t in ticks:
                print(f"[{ts}] PUSH {t['symbol']:10s}  bid={t['bid']:.5f}  ask={t['ask']:.5f}")
        except Exception as e:
            print(f"[sim] Error: {e}")
        time.sleep(1)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--simulate" in args:
        simulate()
    elif args:
        asyncio.run(watch_symbol(args[0]))
    else:
        asyncio.run(watch_all())
