import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import Page from "../../src/app/page";
import { report, healthResponse } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: Error) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

function start(): void {
  fireEvent.click(screen.getByRole("button", { name: "Slow dependency" }));
  fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
}

test("pending state prevents duplicate submissions and does not invent progress", async () => {
  const pending = deferred<Response>();
  let calls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (url) => {
      if (url === "/api/health") return healthResponse();
      calls++;
      return pending.promise;
    }),
  );
  render(<Page />);
  expect(
    screen.getByText("Describe an incident or choose a seeded scenario."),
  ).toBeVisible();
  start();
  fireEvent.submit(screen.getByRole("form", { name: "Investigation" }));
  fireEvent.submit(screen.getByRole("form", { name: "Investigation" }));
  expect(calls).toBe(1);
  expect(screen.getByRole("button", { name: "Investigating…" })).toBeDisabled();
  expect(
    screen.getByRole("region", { name: "Investigation result" }),
  ).toHaveAttribute("aria-busy", "true");
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  await act(async () => pending.resolve(Response.json(report)));
  expect(
    await screen.findByRole("heading", { name: "Investigation report" }),
  ).toBeVisible();
});

test("errors preserve every input and only an explicit retry sends another request", async () => {
  let calls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (url) => {
      if (url === "/api/health") return healthResponse();
      calls++;
      return calls === 1
        ? new Response("unavailable", { status: 503 })
        : Response.json(report);
    }),
  );
  render(<Page />);
  start();
  expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable/i);
  expect(screen.getByLabelText("Incident question")).toHaveValue(
    "payment-service latency is elevated",
  );
  expect(screen.getByLabelText("Service (optional)")).toHaveValue(
    "payment-service",
  );
  expect(screen.getByLabelText("Window (minutes)")).toHaveValue(180);
  expect(calls).toBe(1);
  fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
  expect(
    await screen.findByRole("heading", { name: "Investigation report" }),
  ).toBeVisible();
  expect(calls).toBe(2);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

for (const stale of ["resolve", "reject"] as const) {
  test(`an abandoned request cannot ${stale} over a newer result`, async () => {
    const old = deferred<Response>();
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (url) => {
        if (url === "/api/health") return healthResponse();
        calls++;
        return calls === 1
          ? old.promise
          : Response.json({ ...report, summary: "New result" });
      }),
    );
    render(<Page />);
    start();
    fireEvent.click(screen.getByRole("button", { name: "Stop waiting" }));
    expect(
      screen.getByText(/backend work may still be running/i),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Incident question"), {
      target: { value: "new question" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
    expect(await screen.findByText("New result")).toBeVisible();
    await act(async () => {
      if (stale === "resolve")
        old.resolve(Response.json({ ...report, summary: "Old result" }));
      else old.reject(new Error("private old error"));
    });
    expect(screen.getByText("New result")).toBeVisible();
    expect(screen.queryByText("Old result")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
}

test("a new request clears the previous report instead of relabeling it", async () => {
  const pending = deferred<Response>();
  let calls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (url) => {
      if (url === "/api/health") return healthResponse();
      return ++calls === 1 ? Response.json(report) : pending.promise;
    }),
  );
  render(<Page />);
  start();
  await screen.findByRole("heading", { name: "Investigation report" });
  fireEvent.change(screen.getByLabelText("Incident question"), {
    target: { value: "next question" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
  expect(screen.queryByText(report.summary)).not.toBeInTheDocument();
  await act(async () => pending.resolve(Response.json(report)));
});

test("an empty valid report explains absent candidates and next steps", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (url) =>
      url === "/api/health"
        ? healthResponse()
        : Response.json({ ...report, likely_causes: [], next_steps: [] }),
    ),
  );
  render(<Page />);
  start();
  expect(
    await screen.findByText("No supported cause candidates returned."),
  ).toBeVisible();
  expect(screen.getByText("No next steps returned.")).toBeVisible();
  await waitFor(() =>
    expect(
      screen.getByRole("region", { name: "Investigation result" }),
    ).toHaveAttribute("aria-busy", "false"),
  );
});

test("Edit question reopens the preserved form and focuses it without replacing the report", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (url) =>
      url === "/api/health" ? healthResponse() : Response.json(report),
    ),
  );
  render(<Page />);
  start();
  await screen.findByRole("heading", { name: "Investigation report" });
  fireEvent.click(screen.getByRole("button", { name: "Edit question" }));
  expect(screen.getByLabelText("Incident question")).toHaveFocus();
  expect(screen.getByLabelText("Service (optional)")).toHaveValue(
    "payment-service",
  );
  expect(screen.getByLabelText("Window (minutes)")).toHaveValue(180);
  expect(screen.getByText(report.summary)).toBeVisible();
});
