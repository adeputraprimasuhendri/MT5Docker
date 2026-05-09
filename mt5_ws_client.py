import websocket
import json
import threading
import time

WS_URL = "ws://localhost:8000/ws"

class MT5WSClient:
    def __init__(self, url=WS_URL):
        self.url = url
        self.ws = None
        self.data = {}
        self.connected = False

    def on_message(self, ws, message):
        try:
            self.data = json.loads(message)
        except Exception:
            pass

    def on_open(self, ws):
        self.connected = True
        print(f"[ws] Connected to {self.url}")

    def on_close(self, ws, code, msg):
        self.connected = False
        print("[ws] Disconnected")

    def on_error(self, ws, error):
        print(f"[ws] Error: {error}")

    def connect(self):
        self.ws = websocket.WebSocketApp(
            self.url,
            on_message=self.on_message,
            on_open=self.on_open,
            on_close=self.on_close,
            on_error=self.on_error,
        )
        thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        thread.start()

    def get_data(self):
        return self.data


if __name__ == "__main__":
    client = MT5WSClient()
    client.connect()
    while True:
        print(client.get_data())
        time.sleep(1)
