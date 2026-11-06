import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


def route(path):
    if path in ("/healthz", "/ready"):
        return 200, "text/plain", b"ok"
    if path == "/":
        body = {"app": "{{APP_NAME}}", "lang": "python", "status": "running"}
        return 200, "application/json", json.dumps(body).encode()
    return 404, "text/plain", b"not found"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        status, content_type, body = route(self.path)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)


def main():
    port = int(os.environ.get("PORT", "{{APP_PORT}}"))
    print(f"{{APP_NAME}} listening on {port}", flush=True)
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
