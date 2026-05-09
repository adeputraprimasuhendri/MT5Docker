import asyncio
import json
import sqlite3
import os
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="MT5 Bridge")

latest_data: dict = {}

DB_PATH = os.environ.get("DB_PATH", "/data/history.db")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv (
            symbol    TEXT    NOT NULL,
            timeframe TEXT    NOT NULL,
            time      INTEGER NOT NULL,
            open      REAL    NOT NULL,
            high      REAL    NOT NULL,
            low       REAL    NOT NULL,
            close     REAL    NOT NULL,
            volume    INTEGER NOT NULL,
            PRIMARY KEY (symbol, timeframe, time)
        )
    """)
    conn.commit()
    conn.close()


init_db()


class ConnectionManager:
    def __init__(self):
        self.all: list[WebSocket] = []
        self.symbol_subs: dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, symbol: str | None = None):
        await ws.accept()
        if symbol:
            self.symbol_subs.setdefault(symbol.upper(), []).append(ws)
        else:
            self.all.append(ws)

    def disconnect(self, ws: WebSocket, symbol: str | None = None):
        if symbol:
            key = symbol.upper()
            if key in self.symbol_subs:
                self.symbol_subs[key].discard(ws) if hasattr(self.symbol_subs[key], "discard") else None
                try:
                    self.symbol_subs[key].remove(ws)
                except ValueError:
                    pass
        else:
            try:
                self.all.remove(ws)
            except ValueError:
                pass

    async def broadcast(self, data: dict):
        payload = json.dumps(data)
        dead = []
        for ws in list(self.all):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

        ticks = data.get("ticks", [])
        for tick in ticks:
            sym = tick.get("symbol", "").upper()
            if sym not in self.symbol_subs:
                continue
            tick_payload = json.dumps(tick)
            dead = []
            for ws in list(self.symbol_subs[sym]):
                try:
                    await ws.send_text(tick_payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.disconnect(ws, sym)


manager = ConnectionManager()


async def tcp_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global latest_data
    buffer = b""
    try:
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            buffer += chunk
            try:
                data = json.loads(buffer.decode("utf-8"))
                latest_data = data
                buffer = b""
                await manager.broadcast(data)
            except json.JSONDecodeError:
                pass
    except Exception:
        pass
    finally:
        writer.close()


@app.get("/")
def root():
    return {"status": "ok", "service": "mt5-bridge"}


@app.get("/ticks")
def get_ticks():
    return JSONResponse(latest_data)


@app.post("/push")
async def push_ticks(request: Request):
    global latest_data
    try:
        data = await request.json()
        latest_data = data
        await manager.broadcast(data)
    except Exception:
        pass
    return {"ok": True}


@app.get("/tick/{symbol}")
def get_tick(symbol: str):
    ticks = latest_data.get("ticks", [])
    for t in ticks:
        if t.get("symbol", "").upper() == symbol.upper():
            return JSONResponse(t)
    return JSONResponse({"error": "symbol not found"}, status_code=404)


@app.post("/history")
async def push_history(request: Request):
    data = await request.json()
    symbol = data.get("symbol", "").upper()
    timeframe = data.get("timeframe", "").upper()
    bars = data.get("bars", [])
    if not symbol or not timeframe or not bars:
        return JSONResponse({"error": "symbol, timeframe, bars required"}, status_code=400)
    conn = sqlite3.connect(DB_PATH)
    conn.executemany(
        "INSERT OR REPLACE INTO ohlcv (symbol, timeframe, time, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?,?)",
        [(symbol, timeframe, b["time"], b["open"], b["high"], b["low"], b["close"], b.get("volume", 0)) for b in bars],
    )
    conn.commit()
    conn.close()
    return {"ok": True, "symbol": symbol, "timeframe": timeframe, "inserted": len(bars)}


@app.get("/history/{symbol}/{timeframe}")
def get_history(symbol: str, timeframe: str, limit: int = 1000, from_time: int = 0, to_time: int = 0):
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT time, open, high, low, close, volume FROM ohlcv WHERE symbol=? AND timeframe=?"
    params: list = [symbol.upper(), timeframe.upper()]
    if from_time:
        query += " AND time >= ?"
        params.append(from_time)
    if to_time:
        query += " AND time <= ?"
        params.append(to_time)
    query += " ORDER BY time ASC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe.upper(),
        "count": len(rows),
        "bars": [{"time": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5]} for r in rows],
    }


@app.get("/history/{symbol}")
def list_history_timeframes(symbol: str):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT timeframe, COUNT(*) as bars, MIN(time) as from_time, MAX(time) as to_time FROM ohlcv WHERE symbol=? GROUP BY timeframe",
        [symbol.upper()],
    ).fetchall()
    conn.close()
    return {
        "symbol": symbol.upper(),
        "timeframes": [{"timeframe": r[0], "bars": r[1], "from": r[2], "to": r[3]} for r in rows],
    }


@app.websocket("/ws/ticks")
async def ws_all_ticks(ws: WebSocket):
    await manager.connect(ws)
    if latest_data:
        await ws.send_text(json.dumps(latest_data))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


@app.websocket("/ws/tick/{symbol}")
async def ws_symbol_tick(ws: WebSocket, symbol: str):
    await manager.connect(ws, symbol)
    ticks = latest_data.get("ticks", [])
    for t in ticks:
        if t.get("symbol", "").upper() == symbol.upper():
            await ws.send_text(json.dumps(t))
            break
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws, symbol)


async def main():
    tcp_server = await asyncio.start_server(tcp_handler, "0.0.0.0", 8765)
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    async with tcp_server:
        await asyncio.gather(tcp_server.serve_forever(), server.serve())


if __name__ == "__main__":
    asyncio.run(main())
