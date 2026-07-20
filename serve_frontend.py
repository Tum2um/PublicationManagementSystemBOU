from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class PMSHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path.split("?", 1)[0] in ("", "/", "/index.html"):
            return str(ROOT / "BOU_PMS_Mockup.html")
        return super().translate_path(path)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 3000), PMSHandler)
    print("BOU Publication Management System: http://127.0.0.1:3000")
    server.serve_forever()
