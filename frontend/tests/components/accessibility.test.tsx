import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { afterEach, expect, test, vi } from "vitest";
import Page from "../../src/app/page";
import { healthResponse, report } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

function api(ok = true): void {
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (url) =>
      url === "/api/health"
        ? healthResponse()
        : ok
          ? Response.json(report)
          : new Response(null, { status: 503 }),
    ),
  );
}

test("invalid submission focuses and describes the first rejected field", async () => {
  api();
  render(<Page />);
  fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
  const query = screen.getByLabelText("Incident question");
  expect(query).toHaveFocus();
  expect(query).toHaveAttribute("aria-invalid", "true");
  expect(query).toHaveAccessibleDescription("Enter an incident question.");
  fireEvent.change(query, { target: { value: "why?" } });
  fireEvent.change(screen.getByLabelText("Window (minutes)"), {
    target: { value: "0" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
  expect(screen.getByLabelText("Window (minutes)")).toHaveFocus();
  expect(screen.getByLabelText("Window (minutes)")).toHaveAccessibleDescription(
    /whole number from 1 to 1440/,
  );
  await screen.findByText("Model: unreachable");
});

for (const ok of [true, false]) {
  test(`${ok ? "success" : "failure"} focuses its result heading without health stealing focus`, async () => {
    api(ok);
    render(<Page />);
    fireEvent.click(screen.getByRole("button", { name: "Slow dependency" }));
    fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
    const heading = await screen.findByRole("heading", {
      name: ok ? "Investigation report" : "Investigation failed",
    });
    await waitFor(() => expect(heading).toHaveFocus());
    await screen.findByText("Model: unreachable");
    expect(heading).toHaveFocus();
  });
}

test("loading is announced outside the busy region and stop waiting returns focus to the form", async () => {
  let finish!: (value: Response) => void;
  const pending = new Promise<Response>((resolve) => {
    finish = resolve;
  });
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (url) =>
      url === "/api/health" ? healthResponse() : pending,
    ),
  );
  render(<Page />);
  fireEvent.click(screen.getByRole("button", { name: "Slow dependency" }));
  fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
  const status = screen
    .getAllByRole("status")
    .find((node) => node.textContent === "Investigating…");
  expect(status).toHaveAttribute("aria-live", "polite");
  expect(status?.closest('[aria-busy="true"]')).toBeNull();
  const stop = screen.getByRole("button", { name: "Stop waiting" });
  expect(stop).toHaveFocus();
  fireEvent.click(stop);
  expect(screen.getByLabelText("Incident question")).toHaveFocus();
  await act(async () => finish(Response.json(report)));
});

test("server HTML disables submission until hydration rather than exposing incident values through GET", () => {
  const html = renderToString(<Page />);
  const page = new DOMParser().parseFromString(html, "text/html");
  const form = page.querySelector("form");
  expect(form?.querySelector("fieldset")?.disabled).toBe(true);
  expect(form?.method).toBe("post");
});
