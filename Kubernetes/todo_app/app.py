import os
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(os.environ.get("PORT", "3000"))
IMAGE_DIR = os.environ.get("IMAGE_DIR", "/usr/src/app/files")
IMAGE_URL = os.environ.get("IMAGE_URL", "https://picsum.photos/1200")
IMAGE_TTL = int(os.environ.get("IMAGE_TTL", "600"))  # 10 minutos

IMAGE_FILE = os.path.join(IMAGE_DIR, "image.jpg")
STALE_FLAG = os.path.join(IMAGE_DIR, "stale_served")

PAGE = """<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>Todo app</title>
</head>
<body>
  <h1>Todo app</h1>
  <img src="/image.jpg?v={version}" alt="Imagem aleatória" style="max-width: 600px;">
  <p>Rodando no Kubernetes na porta {port}.</p>
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


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/":
            refresh_image()
            version = int(os.path.getmtime(IMAGE_FILE))
            body = PAGE.format(port=port, version=version).encode("utf-8")
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
