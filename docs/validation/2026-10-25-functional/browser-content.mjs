// Controlled browser content validation; no backend/provider calls.
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import {
  chromium,
  expect,
} from "../../../frontend/node_modules/@playwright/test/index.mjs";

const output = process.argv[2];
if (!output) throw new Error("Supply NEW_OUTPUT.json");
const result = {
  scope:
    "Controlled browser responses based on a saved report; no live inference",
  started_at: new Date().toISOString(),
  status: "started",
};
await writeFile(output, JSON.stringify(result, null, 2) + "\n", { flag: "wx" });
const saved = JSON.parse(
  await readFile(new URL("task2-live.json", import.meta.url), "utf8"),
);
const hostile =
  '<img src=x onerror="alert(1)"><script>alert(2)</script> [open](javascript:alert(3))';
const report = {
  ...saved.attempts[0].report,
  summary: hostile,
  likely_causes: [
    {
      title: hostile,
      rationale: hostile,
      confidence: 0.5,
      supporting_evidence: [{ source: "logs", detail: hostile }],
    },
  ],
  next_steps: [hostile],
};
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  let calls = 0;
  let dialogs = 0;
  page.on("dialog", async (dialog) => {
    dialogs++;
    await dialog.dismiss();
  });
  await page.route("**/api/health", (route) =>
    route.fulfill({ json: { status: "ok", dependencies: { llm: true } } }),
  );
  await page.route("**/api/v1/investigations", (route) => {
    calls++;
    return route.fulfill({ json: report });
  });
  await page.goto("http://127.0.0.1:3001/");
  const submit = page.getByRole("button", {
    name: "Run investigation",
    exact: true,
  });
  await submit.click();
  await expect(
    page.getByText("Enter an incident question.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Incident question")).toBeFocused();
  await page.getByLabel("Incident question").fill(" \n ");
  await submit.click();
  await expect(
    page.getByText("Enter an incident question.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Incident question")).toBeFocused();
  assert.equal(calls, 0);
  result.empty_and_whitespace_prevented = true;
  await page
    .getByLabel("Incident question")
    .fill("Controlled HTML report validation");
  await submit.click();
  await expect(
    page.getByRole("heading", { name: "Investigation report", exact: true }),
  ).toBeFocused();
  assert.equal(
    await page
      .locator(
        "article.report script, article.report img, article.report a, article.report iframe",
      )
      .count(),
    0,
  );
  assert.equal(await page.getByText(hostile, { exact: true }).count(), 5);
  assert.equal(dialogs, 0);
  assert.equal(calls, 1);
  result.markup_remained_literal = true;
  result.inference_requests = 0;
  result.intercepted_form_requests = calls;
  result.status = "passed";
} catch (error) {
  result.status = "failed";
  result.error = { type: error.name, message: error.message };
  process.exitCode = 1;
} finally {
  await browser.close();
  result.finished_at = new Date().toISOString();
  await writeFile(output, JSON.stringify(result, null, 2) + "\n");
  console.log(JSON.stringify(result));
}
