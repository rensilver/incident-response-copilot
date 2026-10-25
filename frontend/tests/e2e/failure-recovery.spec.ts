import { expect, test } from "@playwright/test";
import { report } from "../components/fixtures";

test.beforeEach(({}, testInfo) =>
  test.skip(
    testInfo.project.name === "desktop-no-js",
    "Interactive requests require JavaScript.",
  ),
);

test("all presets remain editable and submit their actual values without automatic requests", async ({
  page,
}) => {
  let calls = 0;
  const inputs = [
    [
      "Memory leak",
      "checkout-service memory keeps climbing",
      "checkout-service",
    ],
    [
      "Slow dependency",
      "payment-service latency is elevated",
      "payment-service",
    ],
    [
      "Bad deploy",
      "cart-service error rate spiked after the last deploy",
      "cart-service",
    ],
  ] as const;
  await page.route("**/api/health", (route) =>
    route.fulfill({
      json: { status: "degraded", dependencies: { llm: false } },
    }),
  );
  await page.route("**/api/v1/investigations", async (route) => {
    const input = inputs[calls++];
    expect(input).toBeDefined();
    expect(route.request().postDataJSON()).toEqual({
      query: input![1],
      service: input![2],
      minutes_back: 180,
    });
    await route.fulfill({
      json: { ...report, summary: `Controlled ${input![0]} report` },
    });
  });
  await page.goto("/");
  await expect(page.getByText("Model: unreachable")).toBeVisible();
  for (const [index, input] of inputs.entries()) {
    const edit = page.getByRole("button", { name: "Edit question" });
    if (await edit.isVisible()) await edit.click();
    await page.getByRole("button", { name: input[0], exact: true }).click();
    await expect(page.getByLabel("Incident question")).toHaveValue(input[1]);
    await expect(page.getByLabel("Service (optional)")).toHaveValue(input[2]);
    expect(calls).toBe(index);
    await page.getByRole("button", { name: "Run investigation" }).click();
    await expect(page.getByText(`Controlled ${input[0]} report`)).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Investigation report" }),
    ).toBeFocused();
    expect(calls).toBe(index + 1);
  }
  expect(
    await page.evaluate(() => ({
      query: location.search,
      local: localStorage.length,
      session: sessionStorage.length,
    })),
  ).toEqual({ query: "", local: 0, session: 0 });
});

test("HTTP, quota, malformed and connection failures recover only on deliberate retry", async ({
  page,
}, testInfo) => {
  const cases = [
    {
      status: 503,
      contentType: "application/json",
      body: '{"detail":"quota private-browser-canary"}',
      expected: /dependencies or model access/i,
    },
    {
      status: 429,
      contentType: "application/json",
      body: '{"detail":"private-browser-canary"}',
      expected: /rate or quota/i,
    },
    {
      status: 500,
      contentType: "text/html",
      body: "<h1>private-browser-canary</h1>",
      expected: /server could not complete/i,
    },
    {
      status: 504,
      contentType: "application/json",
      body: '{"detail":"private-browser-canary"}',
      expected: /deadline exceeded/i,
    },
    {
      status: 422,
      contentType: "application/json",
      body: '{"detail":[]}',
      expected: /request was rejected/i,
    },
    {
      status: 200,
      contentType: "text/html",
      body: "<h1>private-browser-canary</h1>",
      expected: /invalid response/i,
    },
    {
      status: 200,
      contentType: "application/json",
      body: '{"private-browser-canary":',
      expected: /invalid response/i,
    },
    {
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...report, confidence: "private-browser-canary" }),
      expected: /invalid response/i,
    },
    { status: 0, contentType: "", body: "", expected: /connection was lost/i },
  ];
  let calls = 0;
  await page.route("**/api/health", (route) =>
    route.fulfill({ json: { status: "ok", dependencies: { llm: true } } }),
  );
  await page.route("**/api/v1/investigations", async (route) => {
    const value = cases[calls++];
    if (!value) await route.fulfill({ json: report });
    else if (value.status === 0) await route.abort("connectionreset");
    else
      await route.fulfill({
        status: value.status,
        contentType: value.contentType,
        body: value.body,
      });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Slow dependency" }).click();
  for (const [index, value] of cases.entries()) {
    await page.getByRole("button", { name: "Run investigation" }).click();
    const error = page
      .getByRole("region", { name: "Investigation result" })
      .getByRole("alert");
    await expect(error).toContainText(value.expected);
    await expect(
      page.getByRole("heading", { name: "Investigation failed" }),
    ).toBeFocused();
    await expect(page.getByLabel("Incident question")).toHaveValue(
      "payment-service latency is elevated",
    );
    await expect(page.getByLabel("Service (optional)")).toHaveValue(
      "payment-service",
    );
    await expect(page.getByLabel("Window (minutes)")).toHaveValue("180");
    await expect(page.locator("body")).not.toContainText(
      "private-browser-canary",
    );
    expect(calls).toBe(index + 1);
    if (index === 0)
      await page.screenshot({
        path: testInfo.outputPath("unavailable.png"),
        fullPage: true,
      });
  }
  await page.getByRole("button", { name: "Run investigation" }).click();
  await expect(
    page.getByRole("heading", { name: "Investigation report" }),
  ).toBeFocused();
  expect(calls).toBe(cases.length + 1);
});
