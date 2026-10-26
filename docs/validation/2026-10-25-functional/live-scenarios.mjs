// Six paid live investigations: one API and one browser attempt per scenario.
import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import {
  chromium,
  expect,
} from "../../../frontend/node_modules/@playwright/test/index.mjs";

const output = process.argv[2];
if (!output || process.argv[3] !== "--live")
  throw new Error("Usage: live-scenarios.mjs NEW_OUTPUT.json --live");
const evidence = {
  started_at: new Date().toISOString(),
  scope:
    "Deployed production containers, real OpenAI, fresh synthetic observability data, no fixtures/retries/scoring",
  attempts: [],
};
await writeFile(output, JSON.stringify(evidence, null, 2) + "\n", {
  flag: "wx",
});
const scenarios = [
  ["Memory leak", "checkout-service memory keeps climbing", "checkout-service"],
  ["Slow dependency", "payment-service latency is elevated", "payment-service"],
  [
    "Bad deploy",
    "cart-service error rate spiked after the last deploy",
    "cart-service",
  ],
];
const browser = await chromium.launch();
try {
  for (const channel of ["api", "browser"]) {
    for (const [preset, query, service] of scenarios) {
      const entry = {
        channel,
        preset,
        started_at: new Date().toISOString(),
        request: { query, service, minutes_back: 180 },
        status: "started",
      };
      evidence.attempts.push(entry);
      await writeFile(output, JSON.stringify(evidence, null, 2) + "\n");
      const page = channel === "browser" ? await browser.newPage() : null;
      const started = performance.now();
      try {
        let response;
        if (page) {
          await page.goto("http://127.0.0.1:3001/");
          await page.getByRole("button", { name: preset, exact: true }).click();
          const pending = page.waitForResponse(
            (r) => r.url().endsWith("/api/v1/investigations"),
            { timeout: 305_000 },
          );
          entry.click_started_at = new Date().toISOString();
          entry.click_clock = performance.now();
          await page
            .getByRole("button", { name: "Run investigation", exact: true })
            .click();
          response = await pending;
          assert.deepEqual(response.request().postDataJSON(), entry.request);
        } else {
          response = await fetch(
            "http://127.0.0.1:18000/api/v1/investigations",
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(entry.request),
              signal: AbortSignal.timeout(255_000),
            },
          );
        }
        entry.http_status = page ? response.status() : response.status;
        entry.report = await response.json();
        entry.seconds_to_body =
          (performance.now() - (entry.click_clock ?? started)) / 1000;
        delete entry.click_clock;
        assert.equal(entry.http_status, 200);
        const window = entry.report.investigation_window;
        assert.equal(
          Date.parse(window.end) - Date.parse(window.start),
          180 * 60_000,
        );
        assert.ok(entry.report.summary.length > 0);
        if (page) {
          await expect(
            page.getByRole("heading", {
              name: "Investigation report",
              exact: true,
            }),
          ).toBeFocused();
          await expect(page.locator("article.report")).toContainText(
            entry.report.summary,
          );
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
        }
        entry.status = "passed";
      } catch (error) {
        entry.status = "failed";
        entry.error_type = error.name;
        entry.error_message = error.message;
        process.exitCode = 1;
      } finally {
        delete entry.click_clock;
        entry.total_seconds = (performance.now() - started) / 1000;
        entry.finished_at = new Date().toISOString();
        await page?.close();
        await writeFile(output, JSON.stringify(evidence, null, 2) + "\n");
        console.log(
          JSON.stringify({
            channel,
            preset,
            status: entry.status,
            seconds: entry.seconds_to_body,
          }),
        );
      }
    }
  }
} finally {
  await browser.close();
  evidence.finished_at = new Date().toISOString();
  await writeFile(output, JSON.stringify(evidence, null, 2) + "\n");
}
