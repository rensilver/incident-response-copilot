import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import Page from "../../src/app/page";
import { healthResponse, report } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

async function show(value: unknown): Promise<void> {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (url) =>
      url === "/api/health" ? healthResponse() : Response.json(value),
    ),
  );
  render(<Page />);
  fireEvent.click(screen.getByRole("button", { name: "Slow dependency" }));
  fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
}

test("blank report fields and empty evidence are explicit without inventing content", async () => {
  await show({
    ...report,
    summary: " \n ",
    likely_causes: [
      {
        title: " ",
        rationale: "\n",
        confidence: 0,
        supporting_evidence: [{ source: "logs", detail: " " }],
      },
      {
        title: "Another candidate",
        rationale: "Unconfirmed",
        confidence: 1,
        supporting_evidence: [],
      },
    ],
    next_steps: [" "],
  });
  for (const text of [
    "Summary unavailable.",
    "Candidate title unavailable.",
    "Rationale unavailable.",
    "Observation text unavailable.",
    "No supporting observations returned.",
    "Next step text unavailable.",
  ])
    expect(await screen.findByText(text)).toBeVisible();
  expect(screen.getByText("0 / 1")).toBeVisible();
  expect(screen.getByText("1 / 1")).toBeVisible();
});

test("markup and markdown from all model fields stay literal and never become elements", async () => {
  const hostile =
    '<img src=x onerror="alert(1)"><script>alert(2)</script> [open](javascript:alert(3))';
  await show({
    ...report,
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
    debug: {
      api_key: "private-extra-canary",
      logs: ["private-diagnostic-canary"],
    },
  });
  await screen.findByRole("heading", { name: "Investigation report" });
  const result = screen.getByRole("region", { name: "Investigation result" });
  expect(within(result).getAllByText(hostile)).toHaveLength(5);
  expect(result.querySelector("script, img, a, iframe")).toBeNull();
  expect(result).not.toHaveTextContent("private-extra-canary");
  expect(result).not.toHaveTextContent("private-diagnostic-canary");
});

test("long observations retain all characters, distinct repeated messages and dependencies", async () => {
  const identifier = "com.shop.cart.PromotionEngine." + "A".repeat(8000);
  const first =
    "raw query: stable p95; anomaly_detected=false\nfraud-api timeout 2000ms";
  const second =
    "raw query: stable p95; anomaly_detected=false\nfraud-api timeout 2100ms";
  await show({
    ...report,
    likely_causes: [
      {
        ...report.likely_causes[0],
        title: "Candidate",
        rationale: "Compare observations",
        confidence: 0.01,
        supporting_evidence: [
          { source: "metrics", detail: first },
          { source: "logs", detail: second },
          { source: "logs", detail: identifier },
        ],
      },
    ],
  });
  await screen.findByRole("heading", { name: "Investigation report" });
  const evidence = document.querySelector(".evidence");
  expect(evidence?.textContent).toContain(first);
  expect(evidence?.textContent).toContain(second);
  expect(evidence?.textContent).toContain(identifier);
});

for (const window of [
  { start: "2026-12-31T23:59:60Z", end: "2027-01-01T00:01:00Z" },
  { start: "2026-10-25T13:00:00Z", end: "2026-10-25T12:00:00Z" },
]) {
  test("unrenderable or reversed server intervals become safe invalid-response errors", async () => {
    await show({ ...report, investigation_window: window });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /invalid response/i,
    );
    expect(
      screen.queryByRole("heading", { name: "Investigation report" }),
    ).not.toBeInTheDocument();
  });
}
