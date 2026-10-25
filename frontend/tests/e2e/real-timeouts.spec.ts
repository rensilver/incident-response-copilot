import { expect, test } from "@playwright/test";
import { writeFile } from "node:fs/promises";

for (const name of [
  "backend deadline",
  "proxy inactivity",
  "browser total deadline",
]) {
  test(`configured real ${name} path`, async ({ page, request }, testInfo) => {
    // This file is selected only by the opt-in config and its build-origin guard.
    const mode = testInfo.title.includes("inactivity")
      ? "proxy inactivity fixture"
      : testInfo.title.includes("total")
        ? "browser deadline fixture"
        : "backend deadline fixture";
    await page.goto("/");
    await page.getByLabel("Incident question").fill(mode);
    await page.getByLabel("Window (minutes)").fill("1");
    const started = performance.now();
    await page.getByRole("button", { name: "Run investigation" }).click();
    const error = page
      .getByRole("region", { name: "Investigation result" })
      .getByRole("alert");
    await expect(error).toBeVisible({ timeout: 325_000 });
    const elapsedMs = Math.round(performance.now() - started);
    await expect(
      page.getByRole("heading", { name: "Investigation failed" }),
    ).toBeFocused();
    await expect(page.getByLabel("Incident question")).toHaveValue(mode);
    if (mode === "backend deadline fixture") {
      expect(elapsedMs).toBeGreaterThanOrEqual(30_500);
      expect(elapsedMs).toBeLessThan(45_000);
      await expect(error).toContainText("Investigation deadline exceeded");
    } else if (mode === "proxy inactivity fixture") {
      expect(elapsedMs).toBeGreaterThanOrEqual(269_000);
      expect(elapsedMs).toBeLessThan(295_000);
      await expect(error).toContainText(
        /server could not complete|unsuccessful response|deadline exceeded/,
      );
    } else {
      expect(elapsedMs).toBeGreaterThanOrEqual(299_000);
      expect(elapsedMs).toBeLessThan(325_000);
      await expect(error).toContainText("within 5 minutes");
      await expect(error).toContainText("Backend work may still be running");
    }
    const checks: unknown = await (
      await request.get("http://127.0.0.1:18765/checks")
    ).json();
    await writeFile(
      testInfo.outputPath("timing.json"),
      JSON.stringify({ mode, elapsedMs, checks }, null, 2) + "\n",
    );
    await page.screenshot({
      path: testInfo.outputPath("timeout.png"),
      fullPage: true,
    });
  });
}
