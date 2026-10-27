import os
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG_FILE = os.environ.get("LOG_FILE", "/usr/src/app/files/log.txt")
PINGPONG_URL = os.environ.get("PINGPONG_URL", "http://ping-pong-svc:2323/pings")


def read_last_line(path):
    try:
        with open(path) as f:
            lines = f.read().strip().splitlines()
        return lines[-1] if lines else "no log yet"
    except FileNotFoundError:
        return "no log yet"


def fetch_pongs(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return resp.read().decode().strip()
    except Exception as e:
        print(f"Failed to fetch pongs from {url}: {e}", flush=True)
        return "unavailable"


class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = f"{read_last_line(LOG_FILE)}\nPing / Pongs: {fetch_pongs(PINGPONG_URL)}\n".encode()
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
