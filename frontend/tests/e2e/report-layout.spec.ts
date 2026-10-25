import { expect, test, type Page } from "@playwright/test";
import { report } from "../components/fixtures";

async function show(page: Page, value: unknown): Promise<void> {
  await page.route("**/api/health", (route) =>
    route.fulfill({
      json: {
        status: "ok",
        dependencies: { prometheus: true, elasticsearch: true, llm: true },
      },
    }),
  );
  await page.route("**/api/v1/investigations", (route) =>
    route.fulfill({ json: value }),
  );
  await page.goto("/");
  await page.getByRole("button", { name: "Slow dependency" }).click();
  await page.getByRole("button", { name: "Run investigation" }).click();
  await expect(
    page.getByRole("heading", { name: "Investigation report" }),
  ).toBeFocused();
}

async function fits(page: Page): Promise<void> {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const boxes = await page
    .locator(".report p, .report h2, .report h3, .report h4, .report dd")
    .evaluateAll((items) =>
      items.map((item) => {
        const box = item.getBoundingClientRect();
        return { left: box.left, right: box.right, width: innerWidth };
      }),
    );
  for (const box of boxes) {
    expect(box.left).toBeGreaterThanOrEqual(0);
    expect(box.right).toBeLessThanOrEqual(box.width);
  }
}

test.beforeEach(({}, testInfo) =>
  test.skip(
    testInfo.project.name === "desktop-no-js",
    "Reports require JavaScript; the static shell has separate no-JS coverage.",
  ),
);

test("readable report, compact mobile composer and editable context", async ({
  page,
}, testInfo) => {
  await show(page, report);
  const narrow = (page.viewportSize()?.width ?? 1280) < 1100;
  const edit = page.getByRole("button", { name: "Edit question" });
  if (narrow) {
    await expect(page.getByLabel("Incident question")).toBeHidden();
    await expect(edit).toBeVisible();
  } else await expect(page.getByLabel("Incident question")).toBeVisible();
  await fits(page);
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: testInfo.outputPath("report.png"),
    fullPage: true,
  });
  if (narrow) {
    await edit.click();
    await expect(page.getByLabel("Incident question")).toBeFocused();
    await expect(page.getByLabel("Window (minutes)")).toHaveValue("180");
    await expect(page.getByText(report.summary)).toBeVisible();
  }
});

test("long distinct evidence and empty fields reflow at enlarged text sizes", async ({
  page,
}, testInfo) => {
  const detail = "com.shop.cart.PromotionEngine." + "LongIdentifier".repeat(60);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await show(page, {
    ...report,
    summary: " ",
    investigation_window: null,
    next_steps: [],
    likely_causes: [
      {
        title: "Candidate with long observation",
        rationale: "Verify dependency timing before attribution.",
        confidence: 0.123456789,
        supporting_evidence: [
          { source: "logs", detail },
          { source: "logs", detail: "fraud-api timeout 2000ms" },
          { source: "logs", detail: "fraud-api timeout 2100ms" },
        ],
      },
      {
        title: "Candidate without observations",
        rationale: " ",
        confidence: 0,
        supporting_evidence: [],
      },
    ],
  });
  for (const text of [
    "Summary unavailable.",
    "Investigation window unavailable",
    "No supporting observations returned.",
    "No next steps returned.",
    "fraud-api timeout 2000ms",
    "fraud-api timeout 2100ms",
  ])
    await expect(page.getByText(text, { exact: true })).toBeVisible();
  await expect(page.getByText(detail, { exact: true })).toHaveText(detail);
  for (const size of ["200%", "400%"]) {
    await page.evaluate((size) => {
      document.documentElement.style.fontSize = size;
    }, size);
    await fits(page);
    expect(await page.evaluate(() => document.getAnimations().length)).toBe(0);
  }
  await page.screenshot({
    path: testInfo.outputPath("long-report-enlarged.png"),
    fullPage: true,
  });
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "100%";
  });
  await page
    .getByRole("heading", { name: "Candidate without observations" })
    .scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("empty-evidence.png") });
});
