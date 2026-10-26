// Three paid README preset submissions; retain errors without replacement attempts.
import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  chromium,
  expect,
} from "../../../frontend/node_modules/@playwright/test/index.mjs";

if (process.argv[2] !== "--live") throw new Error("Requires explicit --live");
const origin = process.env.README_BROWSER_ORIGIN ?? "http://127.0.0.1:3001";
const output = resolve("docs/validation/2026-10-26-documentation");
const filename = `${output}/walkthrough.json`;
const capture = {
  started_at: new Date().toISOString(),
  scope:
    "Three live README presets; separate from the nine-attempt evaluation; no retries or fixtures",
  model: "gpt-6-luna",
  reasoning: { effort: "none" },
  tracing: false,
  pause_before_first_attempt_seconds: 65,
  pause_between_attempts_seconds: 65,
  attempts: [],
};
await writeFile(filename, JSON.stringify(capture, null, 2) + "\n", {
  flag: "wx",
});
const browser = await chromium.launch();
try {
  capture.chromium = browser.version();
  await new Promise((done) => setTimeout(done, 65_000));
  for (const [scenario, preset, service] of [
    ["memory_leak", "Memory leak", "checkout-service"],
    ["slow_dependency", "Slow dependency", "payment-service"],
    ["bad_deploy", "Bad deploy", "cart-service"],
  ]) {
    if (capture.attempts.length)
      await new Promise((done) => setTimeout(done, 65_000));
    const entry = {
      scenario,
      preset,
      started_at: new Date().toISOString(),
      status: "started",
    };
    capture.attempts.push(entry);
    await writeFile(filename, JSON.stringify(capture, null, 2) + "\n");
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    const external = [];
    page.on("request", (request) => {
      if (new URL(request.url()).origin !== origin)
        external.push("external-origin");
    });
    try {
      await page.goto(origin);
      await page.getByRole("button", { name: preset, exact: true }).click();
      const pending = page.waitForResponse(
        (response) => response.url() === `${origin}/api/v1/investigations`,
        { timeout: 305_000 },
      );
      const clicked = performance.now();
      await page
        .getByRole("button", { name: "Run investigation", exact: true })
        .click();
      const response = await pending;
      entry.request = response.request().postDataJSON();
      entry.http_status = response.status();
      entry.report = await response.json();
      entry.click_to_body_seconds = (performance.now() - clicked) / 1000;
      assert.equal(entry.http_status, 200);
      assert.equal(entry.request.service, service);
      assert.equal(entry.request.minutes_back, 180);
      await expect(
        page.getByRole("heading", {
          name: "Investigation report",
          exact: true,
        }),
      ).toBeFocused();
      await expect(page.locator("article.report")).toContainText(
        entry.report.summary,
      );
      entry.displayed_timestamps = await page
        .locator("article.report time")
        .evaluateAll((nodes) => nodes.map((node) => node.dateTime));
      assert.deepEqual(entry.displayed_timestamps, [
        entry.report.investigation_window.start,
        entry.report.investigation_window.end,
      ]);
      assert.equal(
        new Date(entry.displayed_timestamps[1]) -
          new Date(entry.displayed_timestamps[0]),
        180 * 60 * 1000,
      );
      await expect(
        page.getByRole("heading", { name: "Next steps", exact: true }),
      ).toBeVisible();
      assert.equal(external.length, 0);
      await page.screenshot({
        path: `${output}/${scenario}-walkthrough.png`,
        fullPage: true,
      });
      await page.setViewportSize({ width: 390, height: 844 });
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
      entry.status = "passed";
    } catch (error) {
      entry.status = "failed";
      entry.error_type = error instanceof Error ? error.name : "UnknownError";
      process.exitCode = 1;
    } finally {
      entry.finished_at = new Date().toISOString();
      await page.close();
      await writeFile(filename, JSON.stringify(capture, null, 2) + "\n");
      console.log(
        JSON.stringify({
          scenario,
          status: entry.status,
          http_status: entry.http_status,
          click_to_body_seconds: entry.click_to_body_seconds,
        }),
      );
    }
  }
} finally {
  await browser.close();
  capture.finished_at = new Date().toISOString();
  await writeFile(filename, JSON.stringify(capture, null, 2) + "\n");
}
