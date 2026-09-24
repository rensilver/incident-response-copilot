"""Record real browser scenarios and controlled UI failure cases, including a 300s wait.

Requires the UI extra, Playwright + Chromium, and a freshly seeded deployed API.
Live cases pass through a local recording relay to the actual API unchanged.
Failure cases use explicit HTTP fixtures, never a live LLM. No secrets are recorded.
"""

import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import psutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = [
    ("memory_leak", "Memory leak", "checkout-service"),
    ("slow_dependency", "Slow dependency", "payment-service"),
    ("bad_deploy", "Bad deploy", "cart-service"),
]


def now():
    """Return a UTC timestamp for evidence."""
    return datetime.now(UTC).isoformat()


def save(path, value):
    """Write readable JSON artifacts."""
    path.write_text(json.dumps(value, indent=2, default=str) + "\n")


class Relay(ThreadingHTTPServer):
    """Forward live traffic or return an explicitly selected failure fixture."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, api, output):
        """Start a recording relay with no default simulated failures."""
        super().__init__(address, Handler)
        self.api = api
        self.output = output
        self.mode = "live"
        self.case = "startup"
        self.events = []
        self.release = threading.Event()


class Handler(BaseHTTPRequestHandler):
    """Minimal capture of API payloads, without forwarding or saving credentials."""

    def log_message(self, *args):
        """Suppress default request logging."""

    def do_GET(self):  # noqa: N802
        """Return a health response."""
        self.handle_request("GET")

    def do_POST(self):  # noqa: N802
        """Record one investigation request and response."""
        self.handle_request("POST")

    def handle_request(self, method):
        """Relay real requests and isolate all injected failures from the backend."""
        server = self.server
        mode = server.mode
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        event = {
            "case": server.case,
            "mode": mode,
            "method": method,
            "path": self.path,
            "started_at": now(),
        }
        if body:
            event["request"] = json.loads(body)
        start = time.monotonic()
        server.events.append(event)
        if mode == "timeout" and method == "POST":
            event["behavior"] = "accepted request; sent no response headers or body"
            save(server.output / "timeout-request.json", event)
            server.release.wait(330)
            return
        if mode == "disconnect":
            self.close_connection = True
            event["behavior"] = "closed socket without a response"
            return
        if mode == "live":
            response = httpx.request(
                method,
                server.api + self.path,
                content=body,
                headers={"Content-Type": "application/json"},
                timeout=310,
            )
            status, content = response.status_code, response.content
        elif method == "GET":
            status, content = (
                200,
                json.dumps(
                    {
                        "status": "ok",
                        "dependencies": {"prometheus": True, "elasticsearch": True, "llm": True},
                    }
                ).encode(),
            )
            if mode == "bad_health":
                content = b"not JSON"
        elif mode == "json_503":
            status, content = 503, b'{"detail":"Both providers unavailable (injected UI fixture)"}'
        elif mode == "text_502":
            status, content = 502, b"<html>Bad gateway (injected UI fixture)</html>"
        elif mode == "invalid_report":
            status, content = 200, b"{}"
        elif mode == "literal_html":
            status = 200
            content = json.dumps(
                {
                    "summary": "Fixture <img src=x onerror=alert(1)>",
                    "likely_causes": [],
                    "confidence": 0,
                    "next_steps": ["Check <literal>"],
                }
            ).encode()
        else:
            status, content = 200, b"{}"
        event.update(status=status, duration_seconds=time.monotonic() - start)
        try:
            event["response"] = json.loads(content)
        except ValueError:
            event["response_text"] = content.decode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def sample_memory(output, stop, ui):
    """Sample the host, Streamlit, recorder/browser, and project containers."""
    while not stop.is_set():
        record = {
            "at": now(),
            "available_mib": psutil.virtual_memory().available / 2**20,
            "swap_used_mib": psutil.swap_memory().used / 2**20,
        }
        try:
            record["streamlit_rss_mib"] = psutil.Process(ui.pid).memory_info().rss / 2**20
            children = psutil.Process().children(recursive=True)
            record["recorder_and_children_rss_mib"] = (
                psutil.Process().memory_info().rss + sum(p.memory_info().rss for p in children)
            ) / 2**20
            result = subprocess.run(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{json .}}",
                    "ic-app",
                    "ic-elasticsearch",
                    "ic-prometheus",
                    "ic-grafana",
                    "ic-ollama",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            record["containers"] = [json.loads(line) for line in result.stdout.splitlines()]
        except (psutil.Error, subprocess.SubprocessError) as exc:
            record["error"] = str(exc)
        with (output / "memory.jsonl").open("a") as stream:
            stream.write(json.dumps(record) + "\n")
        stop.wait(15)


def main():
    """Run each browser case once; preserve failures without replacing attempts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--delay-seconds", type=float, default=65)
    parser.add_argument("--ui-port", type=int, default=8501)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "media").mkdir()
    relay = Relay(("127.0.0.1", 0), args.api_url, args.output)
    thread = threading.Thread(target=relay.serve_forever, daemon=True)
    thread.start()
    log = (args.output / "streamlit.log").open("w")
    env = {**os.environ, "INCIDENT_COPILOT_API_URL": f"http://127.0.0.1:{relay.server_port}"}
    ui = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "streamlit_app/app.py",
            "--server.headless=true",
            "--server.address=127.0.0.1",
            f"--server.port={args.ui_port}",
            "--browser.gatherUsageStats=false",
        ],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    stop = threading.Event()
    sampler = threading.Thread(target=sample_memory, args=(args.output, stop, ui), daemon=True)
    sampler.start()
    results = []
    runtime = {
        "started_at": now(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ["streamlit", "playwright", "httpx", "pydantic"]
        },
        "api_url": args.api_url,
        "delay_seconds": args.delay_seconds,
        "method": "Browser -> Streamlit -> recording HTTP relay -> deployed API (live cases only)",
    }
    try:
        for _ in range(60):
            try:
                if httpx.get(f"http://127.0.0.1:{args.ui_port}/_stcore/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("Streamlit failed to start")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            runtime["browser"] = browser.version
            save(args.output / "runtime.json", runtime)

            def run_case(name, mode, label=None, expected=None, record=False):
                relay.mode, relay.case = mode, name
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1000},
                    **(
                        {
                            "record_video_dir": str(args.output / "media"),
                            "record_video_size": {"width": 1440, "height": 1000},
                        }
                        if record
                        else {}
                    ),
                )
                page = context.new_page()
                page.set_default_timeout(20000)
                result = {"case": name, "mode": mode, "started_at": now()}
                start_event = len(relay.events)
                try:
                    page.goto(f"http://127.0.0.1:{args.ui_port}")
                    page.get_by_role("button", name="Memory leak", exact=True).wait_for()
                    page.locator(".ic-statusbar").wait_for()
                    if label:
                        page.get_by_role("button", name=label, exact=True).click()
                        page.get_by_label("service", exact=True).wait_for()
                        # Wait for the example-selection rerun before submitting.
                        from playwright.sync_api import expect

                        service = next(s for _, item, s in SCENARIOS if item == label)
                        expect(page.get_by_label("service", exact=True)).to_have_value(service)
                        expect(page.get_by_label("window (minutes)", exact=True)).to_have_value(
                            "180"
                        )
                    if name == "bad_health":
                        assert "API UNREACHABLE" in page.locator(".ic-statusbar").inner_text()
                    elif name == "unreachable":
                        assert "API UNREACHABLE" in page.locator(".ic-statusbar").inner_text()
                        page.get_by_label("query", exact=True).fill("fixture incident")
                    if record:
                        page.wait_for_timeout(1200)
                    begin = time.monotonic()
                    page.get_by_role("button", name="RUN INVESTIGATION", exact=False).click()
                    if expected:
                        page.locator(".ic-error").wait_for(
                            timeout=320000 if mode == "timeout" else 20000
                        )
                        text = page.locator(".ic-error").inner_text()
                        assert expected in text, text
                        result["displayed_error"] = text
                    elif name == "bad_health":
                        page.locator(".ic-error").wait_for()
                    else:
                        page.locator(".ic-card, .ic-error").first.wait_for(timeout=320000)
                        assert page.locator(".ic-error").count() == 0, page.locator(
                            ".ic-error"
                        ).all_text_contents()
                        if mode == "live":
                            caption = page.get_by_text("Queried window:")
                            assert "180 minutes; API timestamps" in caption.inner_text()
                            result["displayed_window"] = caption.inner_text()
                        if mode == "literal_html":
                            assert page.locator(".ic-card img").count() == 0
                            assert (
                                "<img src=x onerror=alert(1)>"
                                in page.locator(".ic-card").first.inner_text()
                            )
                    result["submit_to_result_seconds"] = time.monotonic() - begin
                    if mode == "timeout":
                        assert 299 <= result["submit_to_result_seconds"] <= 315
                    assert page.locator('[data-testid="stException"]').count() == 0
                    if record:
                        page.wait_for_timeout(2500)
                        for card in page.locator(".ic-card").all():
                            card.scroll_into_view_if_needed()
                            page.wait_for_timeout(1800)
                        page.get_by_role(
                            "button", name="Memory leak", exact=True
                        ).scroll_into_view_if_needed()
                    page.screenshot(path=str(args.output / "media" / f"{name}.png"), full_page=True)
                    result["passed"] = True
                except Exception as exc:
                    result.update(passed=False, error=str(exc))
                    page.screenshot(
                        path=str(args.output / "media" / f"{name}-failed.png"), full_page=True
                    )
                finally:
                    result["events"] = relay.events[start_event:]
                    (args.output / f"{name}-page.txt").write_text(page.locator("body").inner_text())
                    video = page.video
                    context.close()
                    if video:
                        video.save_as(str(args.output / "media" / f"{name}.webm"))
                        video.delete()
                    results.append(result)
                    save(args.output / f"{name}.json", result)
                    save(args.output / "summary.json", results)
                    print(
                        json.dumps({k: v for k, v in result.items() if k != "events"}), flush=True
                    )

            for i, (name, label, _) in enumerate(SCENARIOS):
                if i:
                    time.sleep(args.delay_seconds)
                run_case(name, "live", label, record=True)
            run_case("empty_query", "json_503", expected="query is required")
            run_case("json_503", "json_503", "Memory leak", "Both providers unavailable")
            run_case("text_502", "text_502", "Memory leak", "API error 502")
            run_case(
                "invalid_report", "invalid_report", "Memory leak", "invalid investigation report"
            )
            run_case("literal_html", "literal_html", "Memory leak")
            run_case("bad_health", "bad_health")
            run_case("unreachable", "disconnect", expected="can't reach the API")
            run_case("timeout", "timeout", "Memory leak", "300 seconds")
            relay.release.set()
            run_case("recovery", "literal_html", "Memory leak")
            browser.close()
    finally:
        relay.release.set()
        stop.set()
        sampler.join(timeout=12)
        ui.terminate()
        try:
            ui.wait(timeout=10)
        except subprocess.TimeoutExpired:
            ui.kill()
            ui.wait()
        log.close()
        relay.shutdown()
        relay.server_close()
        save(args.output / "events.json", relay.events)
        runtime["finished_at"] = now()
        save(args.output / "runtime.json", runtime)
    return 0 if results and all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
