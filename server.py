"""
Prep Manager Web & API Server.

Serves static documentation/landing assets from repository root while
providing an API endpoint (/api/check) connecting directly to the
existing package-checking pipeline entry point (src.app.process_unit).

The existing checker implementation in src/ is completely untouched.
"""

import json
import os
import sys
from dataclasses import asdict
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.app import process_unit


class PrepManagerRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler serving static files and routing /api/check to process_unit."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def do_GET(self):
        if self.path == "/api/health":
            self._send_json({"status": "ok", "service": "prep-manager-checker"})
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/check":
            self._handle_check()
            return
        self.send_error(404, "Endpoint not found")

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _handle_check(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_length)
            payload = json.loads(post_body.decode("utf-8")) if post_body else {}

            unit_id = payload.get("unit_id", "DEMO-UNIT-001")
            work_order = payload.get("work_order", {
                "wo_polybag": "True",
                "wo_suffocation_warning": "True",
                "wo_expiry_date": "False",
                "wo_handling_marks": "fragile",
            })
            image_path = payload.get("image_path", "fixtures/prep/a.jpg")

            # Handle base64 uploaded image if supplied
            image_base64 = payload.get("image_base64")
            if image_base64:
                import base64
                if "," in image_base64:
                    image_base64 = image_base64.split(",", 1)[1]
                upload_dir = PROJECT_ROOT / "fixtures" / "prep"
                upload_dir.mkdir(parents=True, exist_ok=True)
                temp_img = upload_dir / f"upload_{unit_id}.jpg"
                temp_img.write_bytes(base64.b64decode(image_base64))
                image_path = str(temp_img.relative_to(PROJECT_ROOT))

            # Call existing checker pipeline
            result = process_unit(
                image_path=image_path,
                unit_id=unit_id,
                work_order=work_order,
            )

            self._send_json(asdict(result), status=200)
        except Exception as e:
            self._send_json({
                "status": "ERROR",
                "error": str(e),
            }, status=500)


def run_server(port: int = 8000):
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, PrepManagerRequestHandler)
    print(f"Prep Manager server running on http://localhost:{port}/")
    print(f"Landing page: http://localhost:{port}/docs/landing/index.html")
    print(f"Checker page: http://localhost:{port}/docs/landing/checker.html")
    print(f"API endpoint: http://localhost:{port}/api/check")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)
