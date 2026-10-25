/** Offline Next production proxy probe. Owns its fixture and frontend processes. */
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { createServer } from "node:http";
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontend = fileURLToPath(new URL("../../../frontend/", import.meta.url));
const next = resolve(frontend, "node_modules/next/dist/bin/next");
const report = { summary: "Fixture only", likely_causes: [], confidence: 0.1, next_steps: [] };
const requests = [];
const backend = createServer(async (req, res) => {
  let body = "";
  for await (const chunk of req) body += chunk;
  requests.push({ method: req.method, path: req.url, body });
  res.setHeader("content-type", "application/json");
  if (req.url === "/health") {
    res.end(JSON.stringify({ status: "degraded", dependencies: { llm: false } }));
  } else if (req.url === "/api/v1/investigations") {
    if (JSON.parse(body).query === "deadline-fixture") {
      res.statusCode = 504;
      res.end(JSON.stringify({ detail: "Investigation deadline exceeded." }));
    } else res.end(JSON.stringify(report));
  } else { res.statusCode = 404; res.end("{}"); }
});
await new Promise((resolve) => backend.listen(0, "127.0.0.1", resolve));
const address = backend.address();
assert.ok(address && typeof address !== "string");
const origin = `http://127.0.0.1:${address.port}`;
const canaries = ["fixture-only-model-private-925312", "fixture-only-tracing-private-174032"];
const baseEnvironment = { PATH: process.env.PATH, NEXT_TELEMETRY_DISABLED: "1", OPENAI_API_KEY: canaries[0], LANGSMITH_API_KEY: canaries[1] };

function build(backendOrigin) {
  const result = spawnSync(process.execPath, [next, "build"], {
    cwd: frontend,
    env: { ...baseEnvironment, INCIDENT_COPILOT_BACKEND_ORIGIN: backendOrigin },
    stdio: "inherit", timeout: 120_000,
  });
  assert.equal(result.status, 0);
  const routes = JSON.parse(readFileSync(resolve(frontend, ".next/routes-manifest.json"), "utf8"));
  assert.deepEqual(routes.rewrites.beforeFiles.map(({ source, destination }) => ({ source, destination })), [
    { source: "/api/v1/investigations", destination: `${backendOrigin}/api/v1/investigations` },
    { source: "/api/health", destination: `${backendOrigin}/health` },
  ]);
  let count = 0;
  for (const subdirectory of [".next/static", ".next/server/app"]) {
    const directory = resolve(frontend, subdirectory);
    for (const name of readdirSync(directory, { recursive: true })) {
      if (!/\.(js|html|rsc|txt)$/.test(name)) continue;
      const content = readFileSync(resolve(directory, name), "utf8");
      for (const privateValue of [...canaries, backendOrigin]) assert.equal(content.includes(privateValue), false, name);
      count++;
    }
  }
  console.log(`Build manifest maps both routes correctly; ${count} browser artifacts exclude private canaries and upstream origin.`);
}

let server;
try {
  build(origin);
  server = spawn(process.execPath, [next, "start", "--hostname", "127.0.0.1", "--port", "13001"], {
    cwd: frontend, env: baseEnvironment, stdio: "inherit",
  });
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    assert.equal(server.exitCode, null, "Next exited before readiness");
    try { ready = (await fetch("http://127.0.0.1:13001", { signal: AbortSignal.timeout(1000) })).ok; } catch { /* Startup only. */ }
    if (ready) break;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  assert.ok(ready, "Next did not become ready");
  const health = await fetch("http://127.0.0.1:13001/api/health");
  assert.equal(health.status, 200);
  assert.deepEqual(await health.json(), { status: "degraded", dependencies: { llm: false } });
  const request = { query: "fixture incident", minutes_back: 17, service: "fixture-service" };
  const response = await fetch("http://127.0.0.1:13001/api/v1/investigations", {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request),
  });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), report);
  const deadline = await fetch("http://127.0.0.1:13001/api/v1/investigations", {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ query: "deadline-fixture" }),
  });
  assert.equal(deadline.status, 504);
  assert.deepEqual(await deadline.json(), { detail: "Investigation deadline exceeded." });
  assert.deepEqual(requests, [
    { method: "GET", path: "/health", body: "" },
    { method: "POST", path: "/api/v1/investigations", body: JSON.stringify(request) },
    { method: "POST", path: "/api/v1/investigations", body: '{"query":"deadline-fixture"}' },
  ]);
  console.log("Real Next proxy preserved health/investigation methods, body, status and JSON. All responses came from an offline fixture.");
} finally {
  if (server && server.exitCode === null) {
    server.kill("SIGTERM");
    await new Promise((resolve) => server.once("exit", resolve));
  }
  await new Promise((resolve) => backend.close(resolve));
}
// Container DNS resolution is deployment scope; verify the built routing artifact.
build("http://app:8000");
console.log("Container origin verified in production rewrite manifest; no Docker service was started.");
