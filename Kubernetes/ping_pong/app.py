import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Contador só em memória: não há mais volume compartilhado com o log_output
counter = 0
lock = threading.Lock()


class PingPongHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global counter
        path = self.path.rstrip("/")

        if path == "/pingpong":
            with lock:
                body = f"pong {counter}"
                counter += 1
        elif path == "/pings":
            # Endpoint interno para o log_output: só lê, não incrementa
            with lock:
                body = str(counter)
        else:
            self.send_error(404)
            return

        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    print(f"Server started on port {port}", flush=True)
    HTTPServer(("0.0.0.0", port), PingPongHandler).serve_forever()
