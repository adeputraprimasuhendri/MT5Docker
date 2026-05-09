import asyncio
import json
import websockets
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="MT5 Bridge")

latest_data: dict = {}
clients: set = set()


async def ws_server(websocket):
    global latest_data
    clients.add(websocket)
    try:
        async for message in websocket:
            try:
                latest_data = json.loads(message)
            except Exception:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)


@app.get("/")
def root():
    return {"status": "ok", "service": "mt5-bridge"}


@app.get("/ticks")
def get_ticks():
    return JSONResponse(latest_data)


@app.get("/tick/{symbol}")
def get_tick(symbol: str):
    ticks = latest_data.get("ticks", [])
    for t in ticks:
        if t.get("symbol", "").upper() == symbol.upper():
            return JSONResponse(t)
    return JSONResponse({"error": "symbol not found"}, status_code=404)


async def start_ws():
    async with websockets.serve(ws_server, "0.0.0.0", 8765):
        await asyncio.Future()


async def main():
    ws_task = asyncio.create_task(start_ws())
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await asyncio.gather(ws_task, server.serve())


if __name__ == "__main__":
    asyncio.run(main())
