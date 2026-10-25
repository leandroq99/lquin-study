import os
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG_FILE = os.environ.get("LOG_FILE", "/usr/src/app/files/log.txt")
PONG_FILE = os.environ.get("PONG_FILE", "/usr/src/app/files/pongs.txt")


def read_last_line(path):
    try:
        with open(path) as f:
            lines = f.read().strip().splitlines()
        return lines[-1] if lines else "no log yet"
    except FileNotFoundError:
        return "no log yet"


def read_pongs(path):
    try:
        with open(path) as f:
            return int(f.read().strip() or 0)
    except FileNotFoundError:
        return 0


class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"{read_last_line(LOG_FILE)}\nPing / Pongs: {read_pongs(PONG_FILE)}\n".encode()
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
    HTTPServer(("0.0.0.0", port), StatusHandler).serve_forever()
