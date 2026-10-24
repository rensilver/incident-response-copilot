import { expect, test } from "@playwright/test";

test("the local foundation loads with keyboard access and no API calls", async ({
  page,
}, testInfo) => {
  const apiRequests: string[] = [];
  const externalRequests: string[] = [];
  const pageErrors: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/api/")) apiRequests.push(url.pathname);
    if (url.origin !== "http://127.0.0.1:3001")
      externalRequests.push(url.origin);
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/");
  await expect(page).toHaveTitle("Incident Response Copilot");
  await expect(
    page.getByRole("heading", { level: 1, name: "Investigate an incident" }),
  ).toBeVisible();
  await expect(page.getByText(/foundation preview/i)).toBeVisible();
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to main content" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await page.evaluate(() => document.fonts.ready);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(apiRequests).toEqual([]);
  expect(externalRequests).toEqual([]);
  expect(pageErrors).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("foundation.png"),
    fullPage: true,
  });
});
