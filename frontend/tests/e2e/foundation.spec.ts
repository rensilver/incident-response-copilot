import { expect, test } from "@playwright/test";

test("the workspace loads with keyboard access and no automatic investigations", async ({
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

  await page.route("**/api/health", (route) =>
    route.fulfill({ json: { status: "ok", dependencies: { llm: true } } }),
  );
  await page.goto("/");
  await expect(page).toHaveTitle("Incident Response Copilot");
  await expect(
    page.getByRole("heading", { level: 1, name: "Investigate an incident" }),
  ).toBeVisible();
  await expect(page.getByLabel("Incident question")).toBeVisible();
  if (testInfo.project.name === "desktop-no-js") {
    await expect(
      page.getByRole("button", { name: "Run investigation" }),
    ).toBeDisabled();
    await expect(page.getByText(/Enable JavaScript/)).toBeVisible();
  }
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
  expect(apiRequests.every((path) => path === "/api/health")).toBe(true);
  expect(externalRequests).toEqual([]);
  expect(pageErrors).toEqual([]);
  await page.screenshot({
    path: testInfo.outputPath("foundation.png"),
    fullPage: true,
  });
});

test("the shell reflows with enlarged text and reduced motion", async ({
  page,
}, testInfo) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.route("**/api/health", (route) =>
    route.fulfill({ json: { status: "ok", dependencies: { llm: true } } }),
  );
  await page.goto("/");
  // Text-size stress, not a claim to emulate browser UI zoom.
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "200%";
  });
  const heading = page.getByRole("heading", {
    level: 1,
    name: "Investigate an incident",
  });
  await expect(heading).toBeVisible();
  await expect(page.getByLabel("Incident question")).toBeVisible();
  if (testInfo.project.name === "desktop-no-js") {
    await expect(
      page.getByRole("button", { name: "Run investigation" }),
    ).toBeDisabled();
    await expect(page.getByText(/Enable JavaScript/)).toBeVisible();
  }
  const geometry = await page.evaluate(() => ({
    width: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    text: Array.from(document.querySelectorAll("h1, h2, p")).map((element) => {
      const box = element.getBoundingClientRect();
      return {
        left: box.left,
        right: box.right,
        fontSize: parseFloat(getComputedStyle(element).fontSize),
      };
    }),
    headingWords: Array.from(document.querySelectorAll("h1, h2")).map(
      (element) => {
        const text = element.firstChild;
        if (!text) throw new Error("Missing heading text");
        const word = text.textContent?.trim().split(/\s+/)[0] ?? "";
        const range = document.createRange();
        range.setStart(text, 0);
        range.setEnd(text, word.length);
        return { word, lines: range.getClientRects().length };
      },
    ),
    animations: document.getAnimations().length,
  }));
  expect(geometry.documentWidth).toBeLessThanOrEqual(geometry.width);
  expect(geometry.animations).toBe(0);
  for (const heading of geometry.headingWords) {
    expect(
      heading.lines,
      `Keep “${heading.word}” readable without splitting`,
    ).toBe(1);
  }
  for (const box of geometry.text) {
    expect(box.left).toBeGreaterThanOrEqual(0);
    expect(box.right).toBeLessThanOrEqual(geometry.width);
    expect(box.fontSize).toBeGreaterThanOrEqual(28);
  }
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to main content" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: testInfo.outputPath("enlarged-text.png"),
    fullPage: true,
  });
});
