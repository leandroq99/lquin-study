import os
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(os.environ.get("PORT", "3000"))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Todo app\n")


server = HTTPServer(("0.0.0.0", port), Handler)
print(f"Server started in port {port}", flush=True)
server.serve_forever()
