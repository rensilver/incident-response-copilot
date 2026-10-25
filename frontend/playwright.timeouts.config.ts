import { defineConfig } from "@playwright/test";
import { readFileSync } from "node:fs";

// Refuse a normal build: these tests must never reach an owner's backend/model.
const manifest = JSON.parse(
  readFileSync(new URL(".next/routes-manifest.json", import.meta.url), "utf8"),
) as {
  rewrites: { beforeFiles: { source: string; destination: string }[] };
};
if (
  !manifest.rewrites.beforeFiles.some(
    (route) =>
      route.source === "/api/v1/investigations" &&
      route.destination === "http://127.0.0.1:18765/api/v1/investigations",
  )
)
  throw new Error(
    "Build with INCIDENT_COPILOT_BACKEND_ORIGIN=http://127.0.0.1:18765 before real-timeout checks.",
  );

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "real-timeouts.spec.ts",
  fullyParallel: true,
  workers: 3,
  timeout: 335_000,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  use: {
    baseURL: "http://127.0.0.1:3001",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: "node tests/fixtures/timeout-server.mjs",
      url: "http://127.0.0.1:18765/health",
      reuseExistingServer: false,
      timeout: 10_000,
      gracefulShutdown: { signal: "SIGTERM", timeout: 5_000 },
    },
    {
      command: "npm run start -- --hostname 127.0.0.1",
      url: "http://127.0.0.1:3001",
      reuseExistingServer: false,
      timeout: 60_000,
      gracefulShutdown: { signal: "SIGTERM", timeout: 5_000 },
      env: { NEXT_TELEMETRY_DISABLED: "1" },
    },
  ],
});
