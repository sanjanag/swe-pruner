#!/usr/bin/env python3
"""Tiny local server for the SwePruner review dashboard.

Serves dashboard.html and persists comments to review_<start>.json on disk.
No third-party deps.

Usage: python3 serve_dashboard.py [PORT]   (default 8765)
Then open http://localhost:<PORT>/
"""
import os
import sys
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

DIR = os.path.dirname(os.path.abspath(__file__))
API_PREFIX = "/api/review/"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body=b"", ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _review_path(self, key):
        safe = "".join(c for c in key if c.isalnum() or c in "-_") or "default"
        return os.path.join(DIR, f"review_{safe}.json")

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith(API_PREFIX):
            p = self._review_path(path[len(API_PREFIX):])
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    self._send(200, f.read())
            else:
                self._send(200, b"{}")
            return
        # static files (dashboard.html, results.json, etc.)
        if path in ("/", ""):
            path = "/dashboard.html"
        fp = os.path.normpath(os.path.join(DIR, path.lstrip("/")))
        if not fp.startswith(DIR) or not os.path.isfile(fp):
            self._send(404, "not found", "text/plain")
            return
        ctype = (
            "text/html" if fp.endswith(".html")
            else "application/json" if fp.endswith(".json")
            else "text/plain"
        )
        with open(fp, "rb") as f:
            self._send(200, f.read(), ctype)

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith(API_PREFIX):
            self._send(404, "not found", "text/plain")
            return
        key = path[len(API_PREFIX):]
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except Exception as e:
            self._send(400, json.dumps({"error": str(e)}))
            return
        p = self._review_path(key)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)  # atomic
        commented = sum(
            1 for v in data.values()
            if isinstance(v, dict) and any((v.get(k) or "").strip() for k in ("query", "gold", "pred"))
        )
        print(f"saved {os.path.basename(p)}  ({commented} rows with comments)", flush=True)
        self._send(200, json.dumps({"ok": True, "saved": os.path.basename(p), "commented": commented}))

    def log_message(self, *a):  # silence default per-request noise
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"SwePruner dashboard: http://localhost:{port}/")
    print(f"serving {DIR}")
    print("comments auto-save to review_<start>.json in that folder. Ctrl-C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
