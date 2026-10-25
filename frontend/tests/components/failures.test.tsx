import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import Page from "../../src/app/page";
import { healthResponse, report } from "./fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function start(): void {
  fireEvent.click(screen.getByRole("button", { name: "Slow dependency" }));
  fireEvent.click(screen.getByRole("button", { name: "Run investigation" }));
}

for (const [status, expected] of [
  [422, /request was rejected/i],
  [401, /backend access/i],
  [403, /backend access/i],
  [429, /rate or quota limit/i],
  [500, /server could not complete/i],
  [502, /unsuccessful response/i],
  [503, /dependencies or model access/i],
  [504, /deadline exceeded/i],
] as const) {
  for (const json of [false, true]) {
    test(`HTTP ${status} (${json ? "JSON" : "HTML"}) gives safe, deliberate recovery`, async () => {
      let calls = 0;
      vi.stubGlobal(
        "fetch",
        vi.fn<typeof fetch>(async (url) => {
          if (url === "/api/health") return healthResponse();
          calls++;
          return new Response(
            json
              ? '{"detail":"private-failure-canary"}'
              : "<html>private-failure-canary</html>",
            {
              status,
              headers: {
                "content-type": json ? "application/json" : "text/html",
              },
            },
          );
        }),
      );
      render(<Page />);
      start();
      const error = await screen.findByRole("alert");
      expect(error).toHaveTextContent(expected);
      expect(error).toHaveTextContent(/Run investigation to retry/);
      expect(document.body).not.toHaveTextContent("private-failure-canary");
      expect(calls).toBe(1);
      expect(
        screen.getByRole("button", { name: "Run investigation" }),
      ).toBeEnabled();
    });
  }
}

for (const [name, response, expected] of [
  [
    "invalid JSON",
    () =>
      new Response('{"private-failure-canary":', {
        headers: { "content-type": "application/json" },
      }),
    /invalid response/i,
  ],
  [
    "HTML success",
    () =>
      new Response("<h1>private-failure-canary</h1>", {
        headers: { "content-type": "text/html" },
      }),
    /invalid response/i,
  ],
  [
    "invalid schema",
    () => Response.json({ ...report, confidence: "private-failure-canary" }),
    /invalid response/i,
  ],
  [
    "connection loss",
    () => {
      throw new TypeError("private-failure-canary");
    },
    /connection was lost/i,
  ],
] as const) {
  test(`${name} is classified without displaying response text or diagnostics`, async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (url) =>
        url === "/api/health" ? healthResponse() : response(),
      ),
    );
    render(<Page />);
    start();
    expect(await screen.findByRole("alert")).toHaveTextContent(expected);
    expect(document.body).not.toHaveTextContent("private-failure-canary");
  });
}

test("the configured five minute browser deadline aborts a stalled request", async () => {
  vi.useFakeTimers();
  let requestSignal: AbortSignal | null | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (url, init) => {
      if (url === "/api/health") return healthResponse();
      requestSignal = init?.signal;
      return new Promise<Response>((_resolve, reject) =>
        init?.signal?.addEventListener(
          "abort",
          () => reject(new DOMException("abandoned", "AbortError")),
          { once: true },
        ),
      );
    }),
  );
  render(<Page />);
  start();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(299_999);
  });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1);
  });
  expect(screen.getByRole("alert")).toHaveTextContent(/within 5 minutes/i);
  expect(screen.getByRole("alert")).toHaveTextContent(
    /backend work may still be running/i,
  );
  expect(requestSignal?.aborted).toBe(true);
});

test("unmount aborts the investigation browser fetch", async () => {
  let requestSignal: AbortSignal | null | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn<typeof fetch>(async (url, init) => {
      if (url === "/api/health") return healthResponse();
      requestSignal = init?.signal;
      return new Promise<Response>((_resolve, reject) =>
        init?.signal?.addEventListener(
          "abort",
          () => reject(new Error("private-failure-canary")),
          { once: true },
        ),
      );
    }),
  );
  const { unmount } = render(<Page />);
  start();
  expect(requestSignal?.aborted).toBe(false);
  unmount();
  expect(requestSignal?.aborted).toBe(true);
  await act(async () => {});
});
