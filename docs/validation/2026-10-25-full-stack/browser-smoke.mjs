// Explicit live deployment probe: one paid investigation, no retries or fixtures.
// Run from root with a NEW output filename and --live after `make docker-up && make seed`.
import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import {
  chromium,
  expect,
} from "../../../frontend/node_modules/@playwright/test/index.mjs";

const output = process.argv[2];
if (!output || process.argv[3] !== "--live") {
  throw new Error("Usage: node browser-smoke.mjs NEW_OUTPUT.json --live");
}
const result = {
  started_at: new Date().toISOString(),
  scope:
    "One live Chromium to production Next rewrite to FastAPI to OpenAI investigation",
  request: null,
  status: "planned",
};
await writeFile(output, JSON.stringify(result, null, 2) + "\n", { flag: "wx" });
let browser;
try {
  browser = await chromium.launch();
  const page = await browser.newPage();
  const paths = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    paths.push(
      url.origin === "http://127.0.0.1:3001" ? url.pathname : "EXTERNAL_ORIGIN",
    );
  });
  await page.goto("http://127.0.0.1:3001/");
  result.stage = "dependency-health";
  const health = await page.request.get("http://127.0.0.1:3001/api/health");
  assert.equal(health.status(), 200);
  result.health = await health.json();
  assert.equal(result.health.status, "ok");
  assert.deepEqual(result.health.dependencies, {
    prometheus: true,
    elasticsearch: true,
    llm: true,
  });
  await page.getByRole("button", { name: "Bad deploy", exact: true }).click();
  result.stage = "live-investigation";
  const pending = page.waitForResponse(
    (response) =>
      response.url() === "http://127.0.0.1:3001/api/v1/investigations",
    { timeout: 305_000 },
  );
  const started = performance.now();
  await page
    .getByRole("button", { name: "Run investigation", exact: true })
    .click();
  const response = await pending;
  result.request = response.request().postDataJSON();
  result.http_status = response.status();
  result.report = await response.json();
  result.elapsed_seconds_to_body = (performance.now() - started) / 1000;
  assert.equal(response.status(), 200);
  assert.deepEqual(result.request, {
    query: "cart-service error rate spiked after the last deploy",
    service: "cart-service",
    minutes_back: 180,
  });
  result.stage = "rendered-report";
  await expect(
    page.getByRole("heading", { name: "Investigation report", exact: true }),
  ).toBeFocused();
  await expect(page.locator("article.report")).toContainText(
    result.report.summary,
  );
  const times = await page
    .locator("article.report time")
    .evaluateAll((elements) =>
      elements.map((element) => element.getAttribute("datetime")),
    );
  assert.deepEqual(times, [
    result.report.investigation_window.start,
    result.report.investigation_window.end,
  ]);
  assert.equal(new Date(times[1]) - new Date(times[0]), 180 * 60 * 1000);
  assert.ok(result.report.likely_causes.length > 0);
  assert.ok(
    result.report.likely_causes.every(
      (cause) => cause.supporting_evidence.length > 0,
    ),
  );
  assert.ok(!paths.includes("EXTERNAL_ORIGIN"));
  result.browser_paths = [...new Set(paths)];
  result.displayed_timestamps = times;
  result.stage = "complete";
  result.status = "passed";
} catch (error) {
  result.status = "failed";
  result.error_type = error instanceof Error ? error.name : "UnknownError";
  process.exitCode = 1;
} finally {
  await browser?.close();
  result.finished_at = new Date().toISOString();
  await writeFile(output, JSON.stringify(result, null, 2) + "\n");
  console.log(
    JSON.stringify({
      status: result.status,
      http_status: result.http_status,
      elapsed_seconds: result.elapsed_seconds_to_body,
      output,
    }),
  );
}
