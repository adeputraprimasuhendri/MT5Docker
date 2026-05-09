import socket
import threading

def forward(src, dst):
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        for s in (src, dst):
            try:
                s.close()
            except Exception:
                pass

def handle(client):
    try:
        remote = socket.create_connection(("mt5-bridge", 8000))
        t = threading.Thread(target=forward, args=(client, remote), daemon=True)
        t.start()
        forward(remote, client)
    except Exception as e:
        print("proxy error:", e)
        try:
            client.close()
        except Exception:
            pass

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 8000))
srv.listen(50)
print("bridge-proxy 127.0.0.1:8000 -> mt5-bridge:8000", flush=True)
while True:
    client, _ = srv.accept()
    threading.Thread(target=handle, args=(client,), daemon=True).start()
