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
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self' http://127.0.0.1:8000 http://localhost:8000; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
        )
        super().end_headers()


if __name__ == "__main__":
    handler = partial(PMSHandler, directory=str(FRONTEND_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 3000), handler)
    print("BOU Publication Management System: http://127.0.0.1:3000")
    server.serve_forever()
