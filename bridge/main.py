import asyncio
import json
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("mt5-bridge")

app = FastAPI(title="MT5 Bridge")

latest_data: dict = {}


async def tcp_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global latest_data
    addr = writer.get_extra_info("peername")
    logger.info(f"[TCP] Client connected: {addr}")
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
                    logger.info(f"[TCP] Data received from {addr}: {obj}")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    break
    except Exception as e:
        logger.error(f"[TCP] Error from {addr}: {e}")
    finally:
        logger.info(f"[TCP] Client disconnected: {addr}")
        writer.close()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"[HTTP] {request.method} {request.url.path}")
    response = await call_next(request)
    if response.status_code >= 400:
        logger.warning(f"[HTTP] {request.method} {request.url.path} -> {response.status_code}")
    return response


@app.get("/")
def root():
    return {"status": "ok", "service": "mt5-bridge"}


@app.get("/ticks")
def get_ticks():
    if not latest_data:
        logger.warning("[HTTP] /ticks requested but no data available")
        return JSONResponse({"error": "no data received yet"}, status_code=503)
    return JSONResponse(latest_data)


@app.post("/push")
async def push_ticks(request: Request):
    global latest_data
    try:
        latest_data = await request.json()
        logger.info(f"[HTTP] /push received: {latest_data}")
    except Exception as e:
        logger.error(f"[HTTP] /push failed to parse body: {e}")
        return JSONResponse({"error": f"invalid JSON: {e}"}, status_code=400)
    return {"ok": True}


@app.get("/tick/{symbol}")
def get_tick(symbol: str):
    if not latest_data:
        logger.warning(f"[HTTP] /tick/{symbol} requested but latest_data is empty")
        return JSONResponse({"error": "no data received yet"}, status_code=503)
    ticks = latest_data.get("ticks", [])
    available = [t.get("symbol") for t in ticks]
    for t in ticks:
        if t.get("symbol", "").upper() == symbol.upper():
            return JSONResponse(t)
    logger.warning(f"[HTTP] /tick/{symbol} not found, available: {available}")
    return JSONResponse(
        {"error": "symbol not found", "requested": symbol, "available": available},
        status_code=404,
    )


async def main():
    logger.info("[TCP] Starting TCP server on 0.0.0.0:8765")
    tcp_server = await asyncio.start_server(tcp_handler, "0.0.0.0", 8765)
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    async with tcp_server:
        await asyncio.gather(tcp_server.serve_forever(), server.serve())


if __name__ == "__main__":
    asyncio.run(main())
