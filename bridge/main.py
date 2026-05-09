import asyncio
import json
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="MT5 Bridge")

latest_data: dict = {}

TCP_HOST = "0.0.0.0"
TCP_PORT = 8765


async def tcp_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global latest_data
    buf = b""
    try:
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            buf += chunk
            # A single send from MT5 may arrive in pieces; parse every complete JSON object
            while buf:
                try:
                    obj = json.loads(buf.decode("utf-8", errors="replace").strip())
                    latest_data = obj
                    buf = b""
                except json.JSONDecodeError:
                    break
    except (ConnectionResetError, asyncio.IncompleteReadError):
        pass
    finally:
        writer.close()


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


async def start_tcp():
    server = await asyncio.start_server(tcp_handler, TCP_HOST, TCP_PORT)
    async with server:
        await server.serve_forever()


async def main():
    ws_task = asyncio.create_task(start_tcp())
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await asyncio.gather(ws_task, server.serve())


if __name__ == "__main__":
    asyncio.run(main())
