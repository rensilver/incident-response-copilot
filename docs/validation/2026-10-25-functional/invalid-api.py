"""Exercise rejected payloads through the real deployed FastAPI server, without inference."""

import json

import httpx

cases = [
    ("empty question", {"query": ""}),
    ("wrong window type", {"query": "q", "minutes_back": "private-failure-canary"}),
    ("zero window", {"query": "q", "minutes_back": 0}),
    ("excessive window", {"query": "q", "minutes_back": 1441}),
]
with httpx.Client(base_url="http://127.0.0.1:18000", timeout=10) as client:
    for name, body in cases:
        response = client.post("/api/v1/investigations", json=body)
        assert response.status_code == 422, (name, response.status_code)
        assert "private-failure-canary" not in response.text
        print(
            json.dumps(
                {
                    "case": name,
                    "status": response.status_code,
                    "response": response.json(),
                }
            )
        )
    for name, body, content_type in [
        ("malformed JSON", '{"query": private-failure-canary}', "application/json"),
        ("HTML payload", "<h1>private-failure-canary</h1>", "text/html"),
    ]:
        response = client.post(
            "/api/v1/investigations",
            content=body,
            headers={"Content-Type": content_type},
        )
        assert response.status_code == 422, (name, response.status_code)
        assert "private-failure-canary" not in response.text
        print(
            json.dumps(
                {
                    "case": name,
                    "status": response.status_code,
                    "response": response.json(),
                }
            )
        )
print(
    "PASS: six invalid deployed API requests rejected safely; no model inference requested"
)
