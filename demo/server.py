"""Zero-dependency web server for the PrivacyPay demo.

Serves the static frontend and a small JSON API backed by the real engine.

Run from the prototype root:
    python3 demo/server.py
then open http://localhost:8000 in a browser.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

DEMO_DIR = Path(__file__).resolve().parent
ROOT = DEMO_DIR.parent
sys.path.insert(0, str(ROOT))

from demo.flows import run_trace, scenario_list, SCENARIOS  # noqa: E402

STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quieter console
        pass

    def _send(self, code, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data, code=200):
        self._send(code, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in STATIC:
            filename, ctype = STATIC[path]
            file_path = DEMO_DIR / filename
            if file_path.exists():
                self._send(200, file_path.read_bytes(), ctype)
            else:
                self._send(404, b"not found", "text/plain")
            return

        if path == "/api/scenarios":
            self._send_json({"scenarios": scenario_list()})
            return

        if path == "/api/run":
            qs = parse_qs(parsed.query)
            scenario = (qs.get("scenario") or ["pay_bill"])[0]
            mode = (qs.get("mode") or ["collaborative"])[0]
            if scenario not in SCENARIOS:
                self._send_json({"error": f"unknown scenario {scenario!r}"}, code=400)
                return
            if mode not in {"collaborative", "cloud_only"}:
                self._send_json({"error": f"unknown mode {mode!r}"}, code=400)
                return
            self._send_json(run_trace(scenario, mode))
            return

        self._send(404, b"not found", "text/plain")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"PrivacyPay demo running at http://localhost:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
