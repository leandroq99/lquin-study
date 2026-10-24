import os
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(os.environ.get("PORT", "3000"))

PAGE = """<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>Todo app</title>
</head>
<body>
  <h1>Todo app</h1>
  <p>Rodando no Kubernetes na porta {port}.</p>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGE.format(port=port).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


server = HTTPServer(("0.0.0.0", port), Handler)
print(f"Server started in port {port}", flush=True)
server.serve_forever()
