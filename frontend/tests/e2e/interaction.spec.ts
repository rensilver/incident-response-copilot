import { expect, test } from "@playwright/test";
import { report } from "../components/fixtures";

test("keyboard submission, failure recovery, and result focus", async ({
  page,
}, testInfo) => {
  test.skip(
    testInfo.project.name === "desktop-no-js",
    "Interactive requests require JavaScript; foundation verifies the disabled state.",
  );
  let attempts = 0;
  await page.route("**/api/health", (route) =>
    route.fulfill({ json: { status: "ok", dependencies: { llm: true } } }),
  );
  await page.route("**/api/v1/investigations", async (route) => {
    attempts++;
    expect(route.request().postDataJSON()).toEqual({
      query: "payment-service latency is elevated",
      service: "payment-service",
      minutes_back: 180,
    });
    await route.fulfill(
      attempts === 1
        ? { status: 503, json: { detail: "private-browser-canary" } }
        : { json: report },
    );
  });
  await page.goto("/");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Memory leak" })).toBeFocused();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Incident question")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Service (optional)")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Window (minutes)")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Run investigation" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Investigation failed" }),
  ).toBeFocused();
  await expect(
    page
      .getByRole("region", { name: "Investigation result" })
      .getByRole("alert"),
  ).not.toContainText("private-browser-canary");
  expect(attempts).toBe(1);
  await page.keyboard.press("Shift+Tab");
  await expect(
    page.getByRole("button", { name: "Run investigation" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Investigation report" }),
  ).toBeFocused();
  await expect(page.getByText(report.summary)).toBeVisible();
  expect(attempts).toBe(2);
});
