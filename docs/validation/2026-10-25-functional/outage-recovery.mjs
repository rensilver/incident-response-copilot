// Actual deployed backend outage, then one paid same-page retry after restoration.
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { writeFile } from "node:fs/promises";
import { promisify } from "node:util";
import {
  chromium,
  expect,
} from "../../../frontend/node_modules/@playwright/test/index.mjs";

const output = process.argv[2];
if (!output || process.argv[3] !== "--live")
  throw new Error("Supply NEW_OUTPUT.json --live");
const result = {
  started_at: new Date().toISOString(),
  scope:
    "Real backend container outage and one real OpenAI recovery investigation; no interception",
  status: "started",
  stages: [],
};
await writeFile(output, JSON.stringify(result, null, 2) + "\n", { flag: "wx" });
const run = promisify(execFile);
const compose = [
  "compose",
  "-f",
  "docker-compose.yml",
  "-f",
  "docs/validation/2026-10-25-functional/ports.override.yml",
];
let restored = false;
let browser;
try {
  browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:3001/");
  await page.getByRole("button", { name: "Bad deploy", exact: true }).click();
  await run("docker", [...compose, "stop", "app"], { timeout: 280_000 });
  result.stages.push("backend stopped");
  const failed = page.waitForResponse(
    (r) => r.url().endsWith("/api/v1/investigations"),
    { timeout: 30_000 },
  );
  await page
    .getByRole("button", { name: "Run investigation", exact: true })
    .click();
  const response = await failed;
  result.outage_http_status = response.status();
  assert.ok(response.status() >= 500);
  await expect(
    page.getByRole("heading", { name: "Investigation failed" }),
  ).toBeFocused();
  result.safe_error = await page
    .getByRole("region", { name: "Investigation result" })
    .getByRole("alert")
    .textContent();
  await expect(page.getByLabel("Incident question")).toHaveValue(
    "cart-service error rate spiked after the last deploy",
  );
  await expect(page.getByLabel("Service (optional)")).toHaveValue(
    "cart-service",
  );
  await expect(page.getByLabel("Window (minutes)")).toHaveValue("180");
  result.stages.push("safe failure and retained form verified");
  await run(
    "docker",
    [
      ...compose,
      "up",
      "-d",
      "--no-deps",
      "--no-build",
      "--wait",
      "--wait-timeout",
      "90",
      "app",
    ],
    { timeout: 120_000 },
  );
  restored = true;
  result.stages.push("backend healthy after restart");
  const pending = page.waitForResponse(
    (r) => r.url().endsWith("/api/v1/investigations"),
    { timeout: 305_000 },
  );
  const started = performance.now();
  await page
    .getByRole("button", { name: "Run investigation", exact: true })
    .click();
  const recovered = await pending;
  result.recovery_http_status = recovered.status();
  result.request = recovered.request().postDataJSON();
  result.report = await recovered.json();
  result.recovery_click_to_body_seconds = (performance.now() - started) / 1000;
  assert.equal(recovered.status(), 200);
  await expect(
    page.getByRole("heading", { name: "Investigation report", exact: true }),
  ).toBeFocused();
  await expect(page.locator("article.report")).toContainText(
    result.report.summary,
  );
  result.stages.push("same-page deliberate retry rendered live report");
  result.status = "passed";
} catch (error) {
  result.status = "failed";
  result.error = { type: error.name, message: error.message };
  process.exitCode = 1;
} finally {
  if (!restored) {
    try {
      await run(
        "docker",
        [
          ...compose,
          "up",
          "-d",
          "--no-deps",
          "--no-build",
          "--wait",
          "--wait-timeout",
          "90",
          "app",
        ],
        { timeout: 120_000 },
      );
    } catch (error) {
      result.restore_error = error.name;
    }
  }
  await browser?.close();
  result.finished_at = new Date().toISOString();
  await writeFile(output, JSON.stringify(result, null, 2) + "\n");
  console.log(
    JSON.stringify({
      status: result.status,
      outage: result.outage_http_status,
      recovery: result.recovery_http_status,
    }),
  );
}
