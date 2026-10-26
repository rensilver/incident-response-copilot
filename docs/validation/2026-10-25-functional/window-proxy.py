"""Validation-only transparent local connector proxy; retain outgoing query bodies."""

import http.client
import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from typing import Any

lock = threading.Lock()


class Capture(BaseHTTPRequestHandler):
    """Forward local observability requests and log only their synthetic query scope."""

    def log_message(self, fmt: str, *args: Any) -> None:
        """Suppress default request logging; the selected JSON record is sufficient."""

    def forward(self) -> None:
        """Forward one request and record its actual outgoing scope."""
        is_metrics = self.server.server_port == 19090
        host, port = ("prometheus", 9090) if is_metrics else ("elasticsearch", 9200)
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        connection = http.client.HTTPConnection(host, port, timeout=35)
        try:
            connection.request(
                self.command,
                self.path,
                body=body,
                headers={
                    key: value
                    for key, value in self.headers.items()
                    if key.lower() in {"content-type", "accept", "accept-encoding"}
                },
            )
            response = connection.getresponse()
            result = response.read()
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in {
                    "content-length",
                    "connection",
                    "transfer-encoding",
                }:
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(result)
            path = urlsplit(self.path)
            event = {
                "at": datetime.now(UTC).isoformat(),
                "source": host,
                "method": self.command,
                "path": path.path,
                "params": parse_qs(path.query),
                "status": response.status,
            }
            if body:
                event["body"] = json.loads(body)
            with lock:
                print(json.dumps(event), flush=True)
        finally:
            connection.close()

    do_GET = forward
    do_POST = forward
    do_HEAD = forward


metrics = ThreadingHTTPServer(("0.0.0.0", 19090), Capture)
logs = ThreadingHTTPServer(("0.0.0.0", 19200), Capture)
threading.Thread(target=metrics.serve_forever, daemon=True).start()
logs.serve_forever()
