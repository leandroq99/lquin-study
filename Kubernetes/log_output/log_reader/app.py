import os
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG_FILE = os.environ.get("LOG_FILE", "/usr/src/app/files/log.txt")


class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            with open(LOG_FILE) as f:
                content = f.read()
        except FileNotFoundError:
            content = "no log yet\n"

        body = content.encode()
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
