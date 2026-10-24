import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

counter = 0
lock = threading.Lock()


class PingPongHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global counter
        if self.path.rstrip("/") != "/pingpong":
            self.send_error(404)
            return

        with lock:
            body = f"pong {counter}".encode()
            counter += 1

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
