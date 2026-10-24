import os
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

random_string = str(uuid.uuid4())
current_status = ""


def log_loop():
    global current_status
    while True:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        current_status = f"{timestamp}: {random_string}"
        print(current_status, flush=True)
        time.sleep(5)


class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = current_status.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # keep the pod logs clean: only our timestamp lines


if __name__ == "__main__":
    threading.Thread(target=log_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 3000))
    print(f"Server started on port {port}", flush=True)
    HTTPServer(("0.0.0.0", port), StatusHandler).serve_forever()
