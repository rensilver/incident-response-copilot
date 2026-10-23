import assert from "node:assert/strict";
import { test } from "node:test";

// Import per test so missing configuration is reported alongside the contract.
async function configFor(origin) {
  const previous = process.env.INCIDENT_COPILOT_BACKEND_ORIGIN;
  try {
    if (origin === undefined) {
      delete process.env.INCIDENT_COPILOT_BACKEND_ORIGIN;
    } else {
      process.env.INCIDENT_COPILOT_BACKEND_ORIGIN = origin;
    }
    const { default: configure } = await import("../next.config.mjs");
    return configure();
  } finally {
    if (previous === undefined) {
      delete process.env.INCIDENT_COPILOT_BACKEND_ORIGIN;
    } else {
      process.env.INCIDENT_COPILOT_BACKEND_ORIGIN = previous;
    }
  }
}

test("browser paths map only investigations and health to the local backend", async () => {
  const config = await configFor();
  assert.deepEqual(await config.rewrites(), {
    beforeFiles: [
      {
        source: "/api/v1/investigations",
        destination: "http://127.0.0.1:8000/api/v1/investigations",
      },
      { source: "/api/health", destination: "http://127.0.0.1:8000/health" },
    ],
    afterFiles: [],
    fallback: [],
  });
  // A backend 240-second deadline must fit before this upstream inactivity limit.
  assert.equal(config.experimental.proxyTimeout, 270_000);
  assert.equal(config.env, undefined);
});

for (const [origin, target] of [
  ["http://app:8000", "http://app:8000"],
  ["http://localhost:8000/", "http://localhost:8000"],
  ["https://backend.example.test:8443", "https://backend.example.test:8443"],
]) {
  test(`server configuration selects ${origin} without changing browser paths`, async () => {
    const config = await configFor(origin);
    const { beforeFiles } = await config.rewrites();
    assert.deepEqual(beforeFiles, [
      {
        source: "/api/v1/investigations",
        destination: `${target}/api/v1/investigations`,
      },
      { source: "/api/health", destination: `${target}/health` },
    ]);
    assert.equal(config.env, undefined);
  });
}

for (const origin of [
  "",
  "/relative",
  "not-a-url",
  "ftp://app:8000",
  "http://user:private-canary@app:8000",
  "http://app:8000/api/v1",
  "http://app:8000?token=private-canary",
  "http://app:8000/#private-canary",
]) {
  test(`invalid backend origin is rejected without echoing its value: ${origin.split(":")[0]}`, async () => {
    await assert.rejects(configFor(origin), {
      name: "Error",
      message:
        "INCIDENT_COPILOT_BACKEND_ORIGIN must be an HTTP(S) origin without credentials, path, query, or fragment.",
    });
  });
}
