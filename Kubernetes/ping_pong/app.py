import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

PONG_FILE = os.environ.get("PONG_FILE", "/usr/src/app/files/pongs.txt")

lock = threading.Lock()


def load_counter():
    try:
        with open(PONG_FILE) as f:
            return int(f.read().strip() or 0)
    except FileNotFoundError:
        return 0


def save_counter(value):
    os.makedirs(os.path.dirname(PONG_FILE), exist_ok=True)
    with open(PONG_FILE, "w") as f:
        f.write(str(value))


counter = load_counter()


class PingPongHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global counter
        if self.path.rstrip("/") != "/pingpong":
            self.send_error(404)
            return

        with lock:
            body = f"pong {counter}".encode()
            counter += 1
            save_counter(counter)

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    print(f"Server started on port {port}", flush=True)
    HTTPServer(("0.0.0.0", port), PingPongHandler).serve_forever()
