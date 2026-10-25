import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import Page from "../../src/app/page";
import { healthResponse, report } from "./fixtures";
import type { IncidentReport } from "../../src/lib/api/types";

afterEach(() => vi.unstubAllGlobals());

async function investigate(value: IncidentReport = report): Promise<void> {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (url) =>
      url === "/api/health" ? healthResponse() : Response.json(value),
    ),
  );
  render(<Page />);
  fireEvent.click(screen.getByRole("button", { name: "Slow dependency" }));
  fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
  await screen.findByRole("heading", { name: "Investigation report" });
}

test("renders the actual report and every evidence source in API order", async () => {
  await investigate({
    ...report,
    likely_causes: [
      ...report.likely_causes,
      {
        title: "Alternative explanation",
        rationale: "More evidence needed",
        confidence: 0.81,
        supporting_evidence: [
          { source: "logs", detail: "distinct second log" },
        ],
      },
    ],
  });
  const region = screen.getByRole("region", { name: "Investigation result" });
  expect(within(region).getByText(report.summary)).toBeVisible();
  const candidates = within(region).getByRole("list", {
    name: "Possible causes",
  });
  const entries = within(candidates).getAllByRole("heading", { level: 4 });
  expect(entries.map((item) => item.textContent)).toEqual([
    "Possible fraud-api slowdown",
    "Alternative explanation",
  ]);
  expect(within(region).getByText("0.654321 / 1")).toBeVisible();
  expect(within(region).getByText("0.73 / 1")).toBeVisible();
  expect(within(region).getByText("0.81 / 1")).toBeVisible();
  expect(
    within(region).getByText(report.likely_causes[0]!.rationale),
  ).toBeVisible();
  expect(
    within(region)
      .getAllByText(/^(Metrics|Logs)$/)
      .map((item) => item.textContent),
  ).toEqual(["Logs", "Metrics", "Logs"]);
  for (const evidence of report.likely_causes[0]!.supporting_evidence)
    expect(within(region).getByText(evidence.detail)).toBeVisible();
  expect(within(region).getByText(report.next_steps[0]!)).toBeVisible();
});

test("converts authoritative offset timestamps to UTC without deriving from form time", async () => {
  await investigate();
  const start = screen.getByText("Oct 25, 2026, 10:13:14.123 UTC");
  const end = screen.getByText("Oct 25, 2026, 13:13:14.123 UTC");
  expect(start.closest("time")).toHaveAttribute(
    "datetime",
    "2026-10-25T07:13:14.123-03:00",
  );
  expect(end.closest("time")).toHaveAttribute(
    "datetime",
    "2026-10-25T10:13:14.123-03:00",
  );
});

for (const includeWindow of [false, true]) {
  test(`absent or null authoritative window is explicitly unavailable (${includeWindow})`, async () => {
    const value = structuredClone(report);
    if (includeWindow) value.investigation_window = null;
    else delete value.investigation_window;
    await investigate(value);
    expect(screen.getByText("Investigation window unavailable")).toBeVisible();
    expect(document.querySelector("time")).toBeNull();
  });
}

test("report context is the submitted question even after editing inputs", async () => {
  await investigate();
  fireEvent.change(screen.getByLabelText("Incident question"), {
    target: { value: "a different question" },
  });
  fireEvent.change(screen.getByLabelText("Service (optional)"), {
    target: { value: "another-service" },
  });
  const result = screen.getByRole("region", { name: "Investigation result" });
  expect(
    within(result).getByText("payment-service latency is elevated"),
  ).toBeVisible();
  expect(within(result).getByText("payment-service")).toBeVisible();
  expect(within(result).queryByText("another-service")).not.toBeInTheDocument();
});
