import html
import json
import os
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(os.environ.get("PORT", "3000"))
IMAGE_DIR = os.environ.get("IMAGE_DIR", "/usr/src/app/files")
IMAGE_URL = os.environ.get("IMAGE_URL", "https://picsum.photos/1200")
IMAGE_TTL = int(os.environ.get("IMAGE_TTL", "600"))  # 10 minutos
TODO_BACKEND_URL = os.environ.get("TODO_BACKEND_URL", "http://todo-backend-svc:2345/todos")

IMAGE_FILE = os.path.join(IMAGE_DIR, "image.jpg")
STALE_FLAG = os.path.join(IMAGE_DIR, "stale_served")

PAGE = """<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Todo App</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: #333;
      background: #fff;
    }}
    main {{
      max-width: 800px;
      margin: 0 auto;
      padding: 40px 16px;
      text-align: center;
    }}
    h1 {{
      font-size: 2.6rem;
      margin: 0 0 24px;
    }}
    img {{
      width: 100%;
      max-width: 300px;
      aspect-ratio: 1 / 1;
      object-fit: cover;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }}
    form {{
      display: flex;
      gap: 12px;
      max-width: 640px;
      margin: 48px auto 32px;
    }}
    input {{
      flex: 1;
      min-width: 0;
      padding: 12px 14px;
      font-size: 1rem;
      border: 2px solid #4caf50;
      border-radius: 4px;
      outline: none;
    }}
    button {{
      padding: 12px 28px;
      font-size: 1rem;
      color: #fff;
      background: #4caf50;
      border: none;
      border-radius: 4px;
      cursor: pointer;
    }}
    button:hover {{
      background: #43a047;
    }}
    h2 {{
      font-size: 1.8rem;
      margin: 0 0 20px;
    }}
    ul {{
      list-style: none;
      padding: 0;
      margin: 0;
      text-align: left;
    }}
    li {{
      background: #f8f8f8;
      border-left: 5px solid #4caf50;
      border-radius: 4px;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
      padding: 18px 24px;
      margin-bottom: 14px;
      font-size: 1.1rem;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Todo App</h1>
    <img src="/image.jpg?v={version}" alt="Imagem aleatória">
    <form method="POST" action="/todos">
      <input type="text" name="todo" maxlength="140" placeholder="Enter a new todo (max 140 characters)" required>
      <button type="submit">Send</button>
    </form>
    <h2>Todos</h2>
    <ul>
{todos}
    </ul>
  </main>
</body>
</html>
"""


def download_image():
    os.makedirs(IMAGE_DIR, exist_ok=True)
    tmp = IMAGE_FILE + ".tmp"
    with urllib.request.urlopen(IMAGE_URL, timeout=10) as resp, open(tmp, "wb") as f:
        f.write(resp.read())
    os.replace(tmp, IMAGE_FILE)
    if os.path.exists(STALE_FLAG):
        os.remove(STALE_FLAG)
    print("New image downloaded", flush=True)


def refresh_image():
    """Baixa uma imagem nova se não houver nenhuma, ou se a atual expirou
    e já foi servida uma última vez depois de expirar."""
    if not os.path.exists(IMAGE_FILE):
        download_image()
        return

    age = time.time() - os.path.getmtime(IMAGE_FILE)
    if age < IMAGE_TTL:
        return

    if not os.path.exists(STALE_FLAG):
        open(STALE_FLAG, "w").close()  # serve a imagem antiga mais uma vez
        return

    try:
        download_image()
    except Exception as e:
        print(f"Failed to download image, keeping the old one: {e}", flush=True)


def fetch_todos():
    try:
        with urllib.request.urlopen(TODO_BACKEND_URL, timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Failed to fetch todos from {TODO_BACKEND_URL}: {e}", flush=True)
        return None


def render_todos(todos):
    if todos is None:
        return "      <li>Todo backend unavailable</li>"
    # html.escape evita que um todo com <script> seja executado na página
    return "\n".join(f"      <li>{html.escape(t)}</li>" for t in todos)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path.split("?")[0] != "/todos":
            self.send_error(404)
            return

        # Repassa o formulário para o todo-backend e volta para a página inicial
        length = int(self.headers.get("Content-Length", 0))
        req = urllib.request.Request(
            TODO_BACKEND_URL,
            data=self.rfile.read(length),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=3).close()
        except Exception as e:
            print(f"Failed to create todo: {e}", flush=True)

        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/":
            refresh_image()
            version = int(os.path.getmtime(IMAGE_FILE))
            body = PAGE.format(
                port=port, version=version, todos=render_todos(fetch_todos())
            ).encode("utf-8")
            self.respond(body, "text/html; charset=utf-8")
        elif path == "/image.jpg":
            with open(IMAGE_FILE, "rb") as f:
                self.respond(f.read(), "image/jpeg")
        elif path == "/shutdown":
            self.respond(b"Shutting down\n", "text/plain; charset=utf-8")
            print("Shutdown requested", flush=True)
            os._exit(1)
        else:
            self.send_error(404)

    def respond(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


server = HTTPServer(("0.0.0.0", port), Handler)
print(f"Server started in port {port}", flush=True)
server.serve_forever()
