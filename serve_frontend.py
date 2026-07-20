from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from pathlib import Path


FRONTEND_ROOT = Path(__file__).resolve().parent / "frontend"


class PMSHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Prevent an old demo entry page or application bundle from surviving a restart.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


if __name__ == "__main__":
    handler = partial(PMSHandler, directory=str(FRONTEND_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 3000), handler)
    print("BOU Publication Management System: http://127.0.0.1:3000")
    server.serve_forever()
