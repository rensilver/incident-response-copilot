import assert from "node:assert/strict";
import { mock, test } from "node:test";
import { createApiClient } from "../src/lib/api/client.js";
import type { InvestigationRequest } from "../src/lib/api/types.js";

const request: InvestigationRequest = {
  query: "payment-service latency is elevated",
  service: "payment-service",
  minutes_back: 180,
};
const report = {
  summary: "Dependency timeout observed",
  likely_causes: [],
  confidence: 0.4,
  next_steps: ["Check fraud-api timing"],
  investigation_window: {
    start: "2026-10-24T10:00:00Z",
    end: "2026-10-24T13:00:00Z",
  },
};

test("investigations send JSON only to the same-origin API and validate the report", async () => {
  const input = structuredClone(request);
  const api = createApiClient(async (url, init) => {
    assert.equal(url, "/api/v1/investigations");
    assert.equal(init?.method, "POST");
    assert.equal(init?.body, JSON.stringify(input));
    assert.equal(
      new Headers(init?.headers).get("content-type"),
      "application/json",
    );
    assert.equal(new Headers(init?.headers).get("accept"), "application/json");
    assert.equal(init?.cache, "no-store");
    assert.equal(init?.credentials, "same-origin");
    assert.equal(init?.redirect, "error");
    return Response.json(report);
  });
  assert.deepEqual(await api.investigate(input), report);
  assert.deepEqual(input, request);
});

test("health uses the proxy path and retains degraded dependency results", async () => {
  const api = createApiClient(async (url, init) => {
    assert.equal(url, "/api/health");
    assert.equal(init?.method, "GET");
    assert.equal(init?.body, undefined);
    return Response.json({ status: "degraded", dependencies: { llm: false } });
  });
  assert.deepEqual(await api.health(), {
    status: "degraded",
    dependencies: { llm: false },
  });
});

for (const [status, body, contentType] of [
  [
    422,
    '{"detail":[{"loc":["body","query"],"msg":"private-canary","type":"missing"}]}',
    "application/json",
  ],
  [503, '{"detail":"private-canary"}', "application/json"],
  [504, '{"detail":"private-canary"}', "application/json"],
  [500, "<html>private-canary</html>", "text/html"],
] as const) {
  test(`HTTP ${status} is classified without retrying or exposing response text`, async () => {
    let calls = 0;
    const api = createApiClient(async () => {
      calls++;
      return new Response(body, {
        status,
        headers: { "content-type": contentType },
      });
    });
    await assert.rejects(api.investigate(request), {
      name: "ApiError",
      kind: "http",
      status,
    });
    assert.equal(calls, 1);
  });
}

for (const response of [
  () => Response.json({ ...report, confidence: "0.4" }),
  () => new Response("{", { headers: { "content-type": "application/json" } }),
  () =>
    new Response("<html>private-canary</html>", {
      headers: { "content-type": "text/html" },
    }),
]) {
  test("malformed successful responses are rejected without exposing their body", async () => {
    const api = createApiClient(async () => response());
    await assert.rejects(api.investigate(request), {
      name: "ApiError",
      kind: "invalid-response",
      message: "Invalid API response.",
    });
  });
}

test("health also validates unknown JSON", async () => {
  const api = createApiClient(async () =>
    Response.json({ status: "ok", dependencies: { llm: "true" } }),
  );
  await assert.rejects(api.health(), {
    name: "ApiError",
    kind: "invalid-response",
  });
});

test("network errors are sanitized and never automatically retried", async () => {
  let calls = 0;
  const api = createApiClient(async () => {
    calls++;
    throw new Error("private-canary");
  });
  await assert.rejects(api.investigate(request), {
    name: "ApiError",
    kind: "network",
    message: "Unable to reach the API.",
  });
  assert.equal(calls, 1);
});

function blockedFetch(): typeof fetch {
  return async (_url, init) =>
    new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener(
        "abort",
        () => reject(init.signal?.reason),
        { once: true },
      );
    });
}

for (const [operation, budget] of [
  ["investigate", 300_000],
  ["health", 10_000],
] as const) {
  test(`${operation} aborts at its total budget`, async () => {
    mock.timers.enable({ apis: ["setTimeout"] });
    try {
      const api = createApiClient(blockedFetch());
      let settled = false;
      const pending =
        operation === "investigate" ? api.investigate(request) : api.health();
      const checked = assert.rejects(
        pending.finally(() => {
          settled = true;
        }),
        { name: "ApiError", kind: "timeout" },
      );
      mock.timers.tick(budget - 1);
      await Promise.resolve();
      assert.equal(settled, false);
      mock.timers.tick(1);
      await checked;
    } finally {
      mock.timers.reset();
    }
  });
}

test("the deadline covers a stalled response body as well as headers", async () => {
  mock.timers.enable({ apis: ["setTimeout"] });
  try {
    const api = createApiClient(
      async (_url, init) =>
        ({
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          json: () =>
            new Promise((_resolve, reject) =>
              init?.signal?.addEventListener(
                "abort",
                () => reject(init.signal?.reason),
                { once: true },
              ),
            ),
        }) as Response,
    );
    const checked = assert.rejects(api.investigate(request), {
      name: "ApiError",
      kind: "timeout",
    });
    await Promise.resolve();
    mock.timers.tick(300_000);
    await checked;
  } finally {
    mock.timers.reset();
  }
});

test("caller cancellation aborts the local fetch without claiming backend cancellation", async () => {
  const controller = new AbortController();
  const api = createApiClient(blockedFetch());
  const checked = assert.rejects(
    api.investigate(request, { signal: controller.signal }),
    {
      name: "ApiError",
      kind: "aborted",
      message: "Request abandoned. Backend work may still be running.",
    },
  );
  controller.abort(new Error("private-canary"));
  await checked;
});

test("a previously aborted caller never starts a request", async () => {
  const controller = new AbortController();
  controller.abort();
  let calls = 0;
  const api = createApiClient(async () => {
    calls++;
    return Response.json(report);
  });
  await assert.rejects(
    api.investigate(request, { signal: controller.signal }),
    { kind: "aborted" },
  );
  assert.equal(calls, 0);
});
