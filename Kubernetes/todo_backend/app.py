import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

port = int(os.environ.get("PORT", "3000"))
MAX_LENGTH = 140

# Todos só em memória por enquanto (o banco de dados vem depois)
todos = ["Learn Kubernetes basics", "Deploy application to cluster"]
lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0].rstrip("/") != "/todos":
            self.send_error(404)
            return
        with lock:
            body = json.dumps(todos)
        self.respond(200, body)

    def do_POST(self):
        if self.path.split("?")[0].rstrip("/") != "/todos":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")

        # Aceita JSON {"todo": "..."} ou formulário todo=...
        if self.headers.get("Content-Type", "").startswith("application/json"):
            try:
                text = str(json.loads(raw).get("todo", ""))
            except (ValueError, AttributeError):
                text = ""
        else:
            text = parse_qs(raw).get("todo", [""])[0]

        text = text.strip()
        if not text or len(text) > MAX_LENGTH:
            self.respond(400, json.dumps({"error": f"todo must have 1-{MAX_LENGTH} characters"}))
            return

        with lock:
            todos.append(text)
        print(f"New todo: {text}", flush=True)
        self.respond(201, json.dumps({"todo": text}))

    def respond(self, status, body):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass


server = HTTPServer(("0.0.0.0", port), Handler)
print(f"Server started in port {port}", flush=True)
server.serve_forever()
