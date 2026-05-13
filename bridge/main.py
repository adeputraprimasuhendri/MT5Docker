import asyncio
import json
import os
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="MT5 Bridge")

latest_data: dict = {}

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://alrca:M4tr!xD3b3@pg:5432/trade")


TIMEFRAME_MAP = {
    "D1": "1d",
    "W1": "1w",
    "MN1": "1M",
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H4": "4h",
}


def normalize_timeframe(tf: str) -> str:
    return TIMEFRAME_MAP.get(tf.upper(), tf)


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_conn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS market_data (
                id         bigserial PRIMARY KEY,
                timestamp  bigint NOT NULL,
                ticker     varchar(20) NOT NULL,
                open       double precision,
                high       double precision,
                low        double precision,
                close      double precision,
                volume     double precision,
                created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
                updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
                period     varchar(10) NOT NULL DEFAULT '1d',
                CONSTRAINT unique_ticker_timestamp_period UNIQUE (ticker, timestamp, period)
            )
        """)
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
    timeframe = normalize_timeframe(data.get("timeframe", ""))
    bars = data.get("bars", [])
    if not symbol or not timeframe or not bars:
        return JSONResponse({"error": "symbol, timeframe, bars required"}, status_code=400)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO market_data (ticker, period, timestamp, open, high, low, close, volume)
                VALUES %s
                ON CONFLICT (ticker, timestamp, period) DO UPDATE SET
                    open       = EXCLUDED.open,
                    high       = EXCLUDED.high,
                    low        = EXCLUDED.low,
                    close      = EXCLUDED.close,
                    volume     = EXCLUDED.volume,
                    updated_at = CURRENT_TIMESTAMP
                """,
                [
                    (symbol, timeframe, b["time"], b["open"], b["high"], b["low"], b["close"], b.get("volume", 0))
                    for b in bars
                ],
            )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "symbol": symbol, "timeframe": timeframe, "inserted": len(bars)}


@app.get("/history/{symbol}/{timeframe}")
def get_history(symbol: str, timeframe: str, limit: int = 5000000, from_time: int = 0, to_time: int = 0):
    conn = get_conn()
    try:
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM market_data
            WHERE ticker = %s AND period = %s
        """
        params: list = [symbol.upper(), timeframe.upper()]
        if from_time:
            query += " AND timestamp >= %s"
            params.append(from_time)
        if to_time:
            query += " AND timestamp <= %s"
            params.append(to_time)
        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    finally:
        conn.close()
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe.upper(),
        "count": len(rows),
        "bars": [{"time": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4], "volume": r[5]} for r in rows],
    }


@app.get("/history/{symbol}")
def list_history_timeframes(symbol: str):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT period, COUNT(*) AS bars, MIN(timestamp) AS from_time, MAX(timestamp) AS to_time
                FROM market_data
                WHERE ticker = %s
                GROUP BY period
                """,
                [symbol.upper()],
            )
            rows = cur.fetchall()
    finally:
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
