import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import Page from "../../src/app/page";
import { healthResponse, report } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

function mockApi(): ReturnType<typeof vi.fn<typeof fetch>> {
  const fetcher = vi.fn<typeof fetch>(async (url) =>
    url === "/api/health" ? healthResponse() : Response.json(report),
  );
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}

test("the workspace exposes labeled inputs and live degraded dependency results", async () => {
  mockApi();
  render(<Page />);
  expect(
    within(screen.getByRole("main")).getByRole("heading", { level: 1 }),
  ).toHaveTextContent("Investigate an incident");
  expect(screen.getByLabelText("Incident question")).toHaveValue("");
  expect(screen.getByLabelText("Service (optional)")).toHaveValue("");
  expect(screen.getByLabelText("Window (minutes)")).toHaveValue(60);
  expect(await screen.findByText("Model: unreachable")).toBeVisible();
  expect(screen.getByText("Prometheus: reachable")).toBeVisible();
  expect(screen.getByText(/dependencies degraded/i)).toBeVisible();
});

for (const [name, query, service] of [
  ["Memory leak", "checkout-service memory keeps climbing", "checkout-service"],
  ["Slow dependency", "payment-service latency is elevated", "payment-service"],
  [
    "Bad deploy",
    "cart-service error rate spiked after the last deploy",
    "cart-service",
  ],
] as const) {
  test(`${name} fills editable inputs without starting an investigation`, async () => {
    const fetcher = mockApi();
    render(<Page />);
    fireEvent.click(screen.getByRole("button", { name }));
    expect(screen.getByLabelText("Incident question")).toHaveValue(query);
    expect(screen.getByLabelText("Service (optional)")).toHaveValue(service);
    expect(screen.getByLabelText("Window (minutes)")).toHaveValue(180);
    await screen.findByText("Model: unreachable");
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual(["/api/health"]);
  });
}

test("whitespace questions and invalid durations never reach the API", async () => {
  const fetcher = mockApi();
  render(<Page />);
  fireEvent.change(screen.getByLabelText("Incident question"), {
    target: { value: "  " },
  });
  fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
  expect(screen.getByText("Enter an incident question.")).toBeVisible();
  fireEvent.change(screen.getByLabelText("Incident question"), {
    target: { value: "why?" },
  });
  for (const value of ["", "0", "1441", "1.5"] as const) {
    fireEvent.change(screen.getByLabelText("Window (minutes)"), {
      target: { value },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
    expect(
      screen.getByText("Enter a whole number from 1 to 1440."),
    ).toBeVisible();
  }
  await screen.findByText("Model: unreachable");
  expect(fetcher.mock.calls.map(([url]) => url)).toEqual(["/api/health"]);
});

for (const minutes of [1, 1440] as const) {
  test(`submission trims text, accepts ${minutes} minutes and omits an empty filter`, async () => {
    const fetcher = mockApi();
    render(<Page />);
    fireEvent.change(screen.getByLabelText("Incident question"), {
      target: { value: "  why payment latency?  " },
    });
    fireEvent.change(screen.getByLabelText("Service (optional)"), {
      target: { value: "  " },
    });
    fireEvent.change(screen.getByLabelText("Window (minutes)"), {
      target: { value: String(minutes) },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
    await waitFor(() =>
      expect(
        fetcher.mock.calls.some(([url]) => url === "/api/v1/investigations"),
      ).toBe(true),
    );
    const call = fetcher.mock.calls.find(
      ([url]) => url === "/api/v1/investigations",
    );
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      query: "why payment latency?",
      minutes_back: minutes,
    });
  });
}

test("a failed health check remains unknown and permits explicit investigation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (url) => {
      if (url === "/api/health") throw new TypeError("private diagnostic");
      return Response.json(report);
    }),
  );
  render(<Page />);
  expect(await screen.findByText("Dependency check unavailable")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Slow dependency" }));
  fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
  expect(await screen.findByText("Investigation received.")).toBeVisible();
});
