// Three additional real provider calls, excluded from the evaluation population.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  chromium,
  expect,
} from "../../../frontend/node_modules/@playwright/test/index.mjs";

if (process.argv[2] !== "--live") throw new Error("Requires explicit --live");
const evidence = resolve("docs/validation/2026-10-26-evaluation");
const media = resolve("docs/media/2026-10-26");
await mkdir(`${media}/raw`, { recursive: true });
const capture = {
  started_at: new Date().toISOString(),
  scope:
    "Three real deployed browser investigations; no fixtures or retries; excluded from evaluation",
  model: "gpt-6-luna",
  reasoning: { effort: "none" },
  tracing: false,
  attempts: [],
};
await writeFile(
  `${evidence}/browser-demo.json`,
  JSON.stringify(capture, null, 2) + "\n",
  { flag: "wx" },
);
const browser = await chromium.launch();
capture.chromium = browser.version();
try {
  for (const [scenario, preset] of [
    ["memory_leak", "Memory leak"],
    ["slow_dependency", "Slow dependency"],
    ["bad_deploy", "Bad deploy"],
  ]) {
    const entry = {
      scenario,
      preset,
      started_at: new Date().toISOString(),
      status: "started",
    };
    capture.attempts.push(entry);
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      deviceScaleFactor: 1,
      reducedMotion: "reduce",
      recordVideo: { dir: `${media}/raw`, size: { width: 1440, height: 1000 } },
    });
    const page = await context.newPage();
    const video = page.video();
    const origin = performance.now();
    let networkStart;
    page.on("request", (request) => {
      if (request.url().endsWith("/api/v1/investigations"))
        networkStart = performance.now();
    });
    try {
      await page.goto("http://127.0.0.1:3001/");
      await page.evaluate(() => document.fonts.ready);
      await page.getByRole("button", { name: preset, exact: true }).click();
      entry.navigation_and_setup_seconds = (performance.now() - origin) / 1000;
      await page.waitForTimeout(2000);
      const pending = page.waitForResponse(
        (r) => r.url().endsWith("/api/v1/investigations"),
        { timeout: 305000 },
      );
      const clicked = performance.now();
      entry.click_offset_seconds = (clicked - origin) / 1000;
      await page
        .getByRole("button", { name: "Run investigation", exact: true })
        .click();
      const response = await pending;
      entry.request = response.request().postDataJSON();
      entry.http_status = response.status();
      entry.report = await response.json();
      entry.http_request_to_body_seconds =
        (performance.now() - networkStart) / 1000;
      assert.equal(entry.http_status, 200);
      await expect(
        page.getByRole("heading", {
          name: "Investigation report",
          exact: true,
        }),
      ).toBeFocused();
      await expect(page.locator("article.report")).toContainText(
        entry.report.summary,
      );
      entry.click_to_render_seconds = (performance.now() - clicked) / 1000;
      entry.render_offset_seconds = (performance.now() - origin) / 1000;
      entry.displayed_times = await page
        .locator("article.report time")
        .evaluateAll((nodes) =>
          nodes.map((n) => ({ datetime: n.dateTime, text: n.textContent })),
        );
      assert.deepEqual(
        entry.displayed_times.map((t) => t.datetime),
        [
          entry.report.investigation_window.start,
          entry.report.investigation_window.end,
        ],
      );
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(1200);
      await page.screenshot({
        path: `${media}/${scenario}-desktop.png`,
        fullPage: true,
      });
      await page.waitForTimeout(3500);
      await page
        .getByRole("heading", { name: "Possible causes", exact: true })
        .scrollIntoViewIfNeeded();
      await page.waitForTimeout(4500);
      await page
        .getByRole("heading", { name: "Next steps", exact: true })
        .scrollIntoViewIfNeeded();
      await page.waitForTimeout(3500);
      entry.desktop_recording_end_offset_seconds =
        (performance.now() - origin) / 1000;
      await page.setViewportSize({ width: 390, height: 844 });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(1000);
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
      await page.screenshot({
        path: `${media}/${scenario}-mobile.png`,
        fullPage: true,
      });
      entry.mobile_viewport = { width: 390, height: 844 };
      entry.status = "passed";
    } catch (error) {
      entry.status = "failed";
      entry.error = { type: error.name, message: error.message };
      process.exitCode = 1;
    } finally {
      entry.total_seconds = (performance.now() - origin) / 1000;
      await context.close();
      await video.saveAs(`${media}/raw/${scenario}.webm`);
      entry.finished_at = new Date().toISOString();
      await writeFile(
        `${evidence}/browser-demo.json`,
        JSON.stringify(capture, null, 2) + "\n",
      );
      console.log(
        JSON.stringify({
          scenario,
          status: entry.status,
          http_seconds: entry.http_request_to_body_seconds,
          browser_seconds: entry.click_to_render_seconds,
        }),
      );
    }
  }
} finally {
  await browser.close();
  capture.finished_at = new Date().toISOString();
  await writeFile(
    `${evidence}/browser-demo.json`,
    JSON.stringify(capture, null, 2) + "\n",
  );
}
