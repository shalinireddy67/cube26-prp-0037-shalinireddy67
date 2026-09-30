"""
Prep Manager Web & API Server.

Serves static documentation/landing assets from repository root while
providing an API endpoint (/api/check) connecting directly to the
existing package-checking pipeline entry point (src.app.process_unit).

The existing checker implementation in src/ is completely untouched.
"""

import base64
from dataclasses import asdict
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import urllib.parse

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.app import process_unit
from src.schemas import PrepResult
from src.storage import init_db, save_image, save_result


class PrepManagerRequestHandler(SimpleHTTPRequestHandler):
    """HTTP handler serving static files and routing /api/check to process_unit."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

    def _is_blocked(self, raw_path: str) -> bool:
        """Check if request targets sensitive files (.env, dotfiles, /data/ tenant storage)."""
        clean_path = urllib.parse.urlparse(raw_path).path
        clean_path = urllib.parse.unquote(clean_path).replace("\\", "/")
        parts = [p for p in clean_path.split("/") if p and p != "."]

        if ".." in parts:
            return True

        if parts:
            first = parts[0].lower()
            if first in ("data", ".env") or first.startswith("."):
                return True
            if any(p.startswith(".") for p in parts):
                return True

        try:
            rel = Path(*parts) if parts else Path(".")
            target = (PROJECT_ROOT / rel).resolve()
            data_dir = (PROJECT_ROOT / "data").resolve()
            if target == data_dir or data_dir in target.parents:
                return True
            if not target.is_relative_to(PROJECT_ROOT):
                return True
        except Exception:
            return True

        return False

    def do_GET(self):
        if self.path == "/api/health":
            self._send_json({"status": "ok", "service": "prep-manager-checker"})
            return

        if self._is_blocked(self.path):
            self.send_error(403, "Access denied")
            return

        super().do_GET()

    def do_HEAD(self):
        if self._is_blocked(self.path):
            self.send_error(403, "Access denied")
            return

        super().do_HEAD()

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
        unit_id = "DEMO-UNIT-001"
        org_id = os.environ.get("TENANT_ORG_ID", "org_demo_alpha")
        image_path = "fixtures/prep/a.jpg"
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_length)
            payload = json.loads(post_body.decode("utf-8")) if post_body else {}

            unit_id = payload.get("unit_id", unit_id)
            # Active tenant comes strictly from server configuration; ignore untrusted client payload (Issue 1)
            org_id = os.environ.get("TENANT_ORG_ID", "org_demo_alpha")
            work_order = payload.get("work_order", {
                "wo_polybag": "True",
                "wo_suffocation_warning": "True",
                "wo_expiry_date": "False",
                "wo_handling_marks": "fragile",
            })

            # Strictly allow either uploaded image via base64 or fixed demo fixture (Issue 2)
            saved_image_path = None
            image_base64 = payload.get("image_base64")
            if image_base64:
                if "," in image_base64:
                    image_base64 = image_base64.split(",", 1)[1]
                image_bytes = base64.b64decode(image_base64)
                # Persist uploaded capture using tenant storage (Rule 3)
                saved_image_path = save_image(org_id, unit_id, image_bytes)
                image_path = saved_image_path
            else:
                # Disallow client-supplied arbitrary paths; strictly use fixed demo fixture
                image_path = "fixtures/prep/a.jpg"

            # Call existing checker pipeline
            result = process_unit(
                image_path=image_path,
                unit_id=unit_id,
                work_order=work_order,
            )

            # Persist PrepResult (including PENDING) using tenant storage (Rule 3)
            try:
                storage_img_path = saved_image_path or image_path
                save_result(org_id, unit_id, str(storage_img_path), result)
            except Exception as e:
                print(f"[Storage Warning] Could not persist result: {e}", file=sys.stderr)

            self._send_json(asdict(result), status=200)
        except Exception as e:
            # Rule 3 fail-open persistence fallback
            try:
                fail_result = PrepResult(
                    unit_id=unit_id,
                    overall_status="PENDING",
                    requires_manual_review=False,
                    checks=[],
                    evidence={"reason": str(e)},
                )
                save_result(org_id, unit_id, str(image_path), fail_result)
            except Exception:
                pass
            self._send_json({
                "status": "ERROR",
                "error": str(e),
            }, status=500)


def run_server(port: int = 8000):
    init_db()
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
