// Three concurrent paid investigations: two browser tabs and one direct API.
import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import {
  chromium,
  expect,
} from "../../../frontend/node_modules/@playwright/test/index.mjs";

const output = process.argv[2];
if (!output || process.argv[3] !== "--live")
  throw new Error("Supply NEW_OUTPUT.json --live");
const evidence = {
  started_at: new Date().toISOString(),
  scope:
    "Concurrent real provider investigations through validation-only transparent local data proxies",
  planned: [
    { service: "checkout-service", minutes: 17, channel: "browser" },
    { service: "payment-service", minutes: 43, channel: "browser" },
    { service: "cart-service", minutes: 91, channel: "api" },
  ],
  attempts: [],
};
await writeFile(output, JSON.stringify(evidence, null, 2) + "\n", {
  flag: "wx",
});
const browser = await chromium.launch();
async function attempt(preset, service, minutes, channel) {
  const entry = {
    preset,
    channel,
    started_at: new Date().toISOString(),
    request: {
      query: `${service}: investigate metrics and logs`,
      service,
      minutes_back: minutes,
    },
    status: "started",
  };
  evidence.attempts.push(entry);
  const page = channel === "browser" ? await browser.newPage() : null;
  try {
    let response;
    if (page) {
      await page.goto("http://127.0.0.1:3001/");
      await page.getByRole("button", { name: preset, exact: true }).click();
      await page.getByLabel("Incident question").fill(entry.request.query);
      await page.getByLabel("Window (minutes)").fill(String(minutes));
      const pending = page.waitForResponse(
        (r) => r.url().endsWith("/api/v1/investigations"),
        { timeout: 305_000 },
      );
      entry.sent_at = new Date().toISOString();
      await page
        .getByRole("button", { name: "Run investigation", exact: true })
        .click();
      response = await pending;
      assert.deepEqual(response.request().postDataJSON(), entry.request);
    } else {
      entry.sent_at = new Date().toISOString();
      response = await fetch("http://127.0.0.1:18000/api/v1/investigations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry.request),
        signal: AbortSignal.timeout(255_000),
      });
    }
    entry.http_status = page ? response.status() : response.status;
    entry.report = await response.json();
    entry.body_at = new Date().toISOString();
    assert.equal(entry.http_status, 200);
    const window = entry.report.investigation_window;
    assert.equal(
      Date.parse(window.end) - Date.parse(window.start),
      minutes * 60_000,
    );
    assert.ok(Date.parse(window.end) >= Date.parse(entry.sent_at) - 1000);
    assert.ok(Date.parse(window.end) <= Date.parse(entry.body_at));
    if (page) {
      await expect(
        page.getByRole("heading", {
          name: "Investigation report",
          exact: true,
        }),
      ).toBeFocused();
      entry.displayed_times = await page
        .locator("article.report time")
        .evaluateAll((nodes) =>
          nodes.map((node) => ({
            datetime: node.getAttribute("datetime"),
            text: node.textContent,
          })),
        );
      assert.deepEqual(
        entry.displayed_times.map((t) => t.datetime),
        [window.start, window.end],
      );
      const rendered = await page
        .locator("article.report time")
        .allTextContents();
      assert.equal(rendered.length, 2);
      const timestamp = new Intl.DateTimeFormat("en-US", {
        timeZone: "UTC",
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        fractionalSecondDigits: 3,
        hourCycle: "h23",
      });
      assert.deepEqual(
        rendered,
        [window.start, window.end].map(
          (value) => `${timestamp.format(new Date(value))} UTC`,
        ),
      );
    }
    entry.status = "passed";
  } catch (error) {
    entry.status = "failed";
    entry.error = { type: error.name, message: error.message };
    process.exitCode = 1;
  } finally {
    entry.finished_at = new Date().toISOString();
    await page?.close();
    console.log(JSON.stringify({ channel, minutes, status: entry.status }));
  }
}
try {
  await Promise.all([
    attempt("Memory leak", "checkout-service", 17, "browser"),
    attempt("Slow dependency", "payment-service", 43, "browser"),
    attempt("Bad deploy", "cart-service", 91, "api"),
  ]);
  assert.equal(
    new Set(evidence.attempts.map((a) => a.report?.investigation_window.end))
      .size,
    3,
  );
  const latestStart = Math.max(
    ...evidence.attempts.map((a) => Date.parse(a.sent_at)),
  );
  const firstFinish = Math.min(
    ...evidence.attempts.map((a) => Date.parse(a.body_at)),
  );
  assert.ok(latestStart < firstFinish, "Requests must overlap in execution");
  evidence.concurrent_overlap_verified = true;
} finally {
  await browser.close();
  evidence.finished_at = new Date().toISOString();
  await writeFile(output, JSON.stringify(evidence, null, 2) + "\n");
}
