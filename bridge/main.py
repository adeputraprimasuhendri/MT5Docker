import asyncio
import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="MT5 Bridge")

latest_data: dict = {}


async def tcp_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global latest_data
    buffer = b""
    try:
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            buffer += chunk
            # Parse all complete JSON objects from the buffer (handles concatenated messages)
            while buffer:
                try:
                    obj, idx = json.JSONDecoder().raw_decode(buffer.decode("utf-8"))
                    latest_data = obj
                    buffer = buffer[idx:].lstrip()
                except (json.JSONDecodeError, UnicodeDecodeError):
                    break
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
        latest_data = await request.json()
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


async def main():
    tcp_server = await asyncio.start_server(tcp_handler, "0.0.0.0", 8765)
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    async with tcp_server:
        await asyncio.gather(tcp_server.serve_forever(), server.serve())


if __name__ == "__main__":
    asyncio.run(main())