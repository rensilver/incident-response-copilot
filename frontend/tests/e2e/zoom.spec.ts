import { chromium, expect, test } from "@playwright/test";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { report } from "../components/fixtures";

test.use({
  deviceScaleFactor: async ({}, provide) => {
    await provide(undefined);
  },
});

type ZoomApi = {
  tabs: {
    query: (options: { url: string }) => Promise<{ id?: number }[]>;
    setZoom: (tab: number, factor: number) => Promise<void>;
    getZoom: (tab: number) => Promise<number>;
  };
};

test("actual Chromium tab zoom at 200% and 400% reflows the report", async ({}, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop-chromium",
    "One full Chromium instance checks native tab zoom; other projects cover viewport and text scaling.",
  );
  test.setTimeout(45_000);
  const extension = await mkdtemp(join(tmpdir(), "incident-zoom-"));
  let context;
  try {
    await writeFile(
      join(extension, "manifest.json"),
      JSON.stringify({
        manifest_version: 3,
        name: "Local zoom check",
        version: "1.0",
        permissions: ["tabs"],
        background: { service_worker: "background.js" },
      }),
    );
    await writeFile(
      join(extension, "background.js"),
      "chrome.runtime.onInstalled.addListener(() => {});\n",
    );
    context = await chromium.launchPersistentContext("", {
      channel: "chromium",
      headless: true,
      viewport: null,
      args: [
        "--window-size=1280,1000",
        `--disable-extensions-except=${extension}`,
        `--load-extension=${extension}`,
      ],
    });
    const worker =
      context.serviceWorkers()[0] ??
      (await context.waitForEvent("serviceworker"));
    await context.route("**/api/health", (route) =>
      route.fulfill({ json: { status: "ok", dependencies: { llm: true } } }),
    );
    await context.route("**/api/v1/investigations", (route) =>
      route.fulfill({ json: report }),
    );
    const page = await context.newPage();
    await page.goto("http://127.0.0.1:3001/");
    await page.getByRole("button", { name: "Slow dependency" }).click();
    await page.getByRole("button", { name: "Run investigation" }).click();
    await expect(
      page.getByRole("heading", { name: "Investigation report" }),
    ).toBeFocused();
    const originalWidth = await page.evaluate(() => innerWidth);
    const measurements = [];
    const cdp = await context.newCDPSession(page);
    for (const factor of [1, 2, 4]) {
      const actual = await worker.evaluate(async (factor) => {
        const api = (globalThis as unknown as { chrome: ZoomApi }).chrome;
        const tab = (
          await api.tabs.query({ url: "http://127.0.0.1:3001/*" })
        )[0];
        if (tab?.id === undefined) throw new Error("Missing local check tab");
        await api.tabs.setZoom(tab.id, factor);
        return api.tabs.getZoom(tab.id);
      }, factor);
      expect(actual).toBeCloseTo(factor);
      await expect
        .poll(() => page.evaluate(() => innerWidth))
        .toBeLessThanOrEqual(Math.ceil(originalWidth / factor) + 1);
      const geometry = await page.evaluate(() => ({
        width: innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        rootFontSize: getComputedStyle(document.documentElement).fontSize,
        pixelRatio: devicePixelRatio,
      }));
      expect(geometry.documentWidth).toBeLessThanOrEqual(geometry.width);
      expect(geometry.rootFontSize).toBe("16px");
      await expect(
        page.getByRole("heading", { name: "Investigation report" }),
      ).toBeVisible();
      await expect(
        page.getByText(report.next_steps[0]!, { exact: true }),
      ).toBeVisible();
      if (factor > 1)
        await expect(
          page.getByRole("button", { name: "Edit question" }),
        ).toBeVisible();
      measurements.push({ factor: actual, ...geometry });
      await page
        .getByRole("heading", { name: "Investigation report" })
        .scrollIntoViewIfNeeded();
      const capture = await cdp.send("Page.captureScreenshot", {
        format: "png",
        captureBeyondViewport: false,
      });
      await writeFile(
        testInfo.outputPath(`zoom-${factor}.png`),
        Buffer.from(capture.data, "base64"),
      );
    }
    await writeFile(
      testInfo.outputPath("zoom.json"),
      JSON.stringify(measurements, null, 2) + "\n",
    );
  } finally {
    await context?.close();
    await rm(extension, { recursive: true, force: true });
  }
});
