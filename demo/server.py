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


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ (no overwrite)."""
    if not path.exists():
        return
    import os
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ROOT / ".env")

from demo.flows import run_trace, scenario_list, SCENARIOS, backend_info  # noqa: E402

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

        if path == "/api/backend":
            self._send_json({"backend": backend_info()})
            return

        if path == "/api/run":
            qs = parse_qs(parsed.query)
            scenario = (qs.get("scenario") or ["pay_bill"])[0]
            mode = (qs.get("mode") or ["collaborative"])[0]
            backend = (qs.get("backend") or ["auto"])[0]
            if scenario not in SCENARIOS:
                self._send_json({"error": f"unknown scenario {scenario!r}"}, code=400)
                return
            if mode not in {"collaborative", "cloud_only"}:
                self._send_json({"error": f"unknown mode {mode!r}"}, code=400)
                return
            if backend not in {"auto", "real", "heuristic"}:
                backend = "auto"
            try:
                self._send_json(run_trace(scenario, mode, backend))
            except Exception as exc:  # real backend may fail (network/key/Ollama)
                self._send_json(
                    {"error": f"{type(exc).__name__}: {exc}",
                     "backend": backend_info()},
                    code=500,
                )
            return

        self._send(404, b"not found", "text/plain")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    bi = backend_info()
    cloud = bi["cloud"] + (f" ({bi['cloud_model']})" if bi["cloud_model"] else "")
    print(f"PrivacyPay demo running at http://localhost:{port}")
    print(f"  cloud backend: {cloud}")
    print(f"  local backend: {bi['local']}")
    if bi["cloud"] == "heuristic":
        print("  (set CLOUD_LLM_API_KEY / CLOUD_LLM_BASE_URL / CLOUD_LLM_MODEL in .env for a real cloud LLM)")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
