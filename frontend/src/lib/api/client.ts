/** Same-origin browser transport. Import from interactive leaves only. */
import {
  InvalidApiResponseError,
  parseHealth,
  parseReport,
} from "./validation.ts";
import type { Health, IncidentReport, InvestigationRequest } from "./types.js";

type ApiErrorKind =
  "http" | "network" | "invalid-response" | "timeout" | "aborted";
const messages: Record<ApiErrorKind, string> = {
  http: "The API returned an unsuccessful response.",
  network: "Unable to reach the API.",
  "invalid-response": "Invalid API response.",
  timeout:
    "No response received within the request budget. Backend work may still be running.",
  aborted: "Request abandoned. Backend work may still be running.",
};

/** Public failures carry only safe categories and optional HTTP status. */
export class ApiError extends Error {
  constructor(
    readonly kind: ApiErrorKind,
    readonly status?: number,
  ) {
    super(messages[kind]);
    this.name = "ApiError";
  }
}

type RequestOptions = Readonly<{ signal?: AbortSignal }>;

/** Inject fetch for offline consumers; never retry paid investigation work. */
export function createApiClient(fetcher: typeof fetch = fetch): {
  investigate: (
    request: InvestigationRequest,
    options?: RequestOptions,
  ) => Promise<IncidentReport>;
  health: (options?: RequestOptions) => Promise<Health>;
} {
  async function send<T>(
    path: string,
    init: RequestInit,
    parse: (value: unknown) => T,
    budget: number,
    options: RequestOptions,
  ): Promise<T> {
    if (options.signal?.aborted) throw new ApiError("aborted");
    const deadline = new AbortController();
    const signal = options.signal
      ? AbortSignal.any([options.signal, deadline.signal])
      : deadline.signal;
    const timer = setTimeout(() => deadline.abort(), budget);
    try {
      const response = await fetcher(path, {
        ...init,
        signal,
        cache: "no-store",
        credentials: "same-origin",
        redirect: "error",
      });
      if (!response.ok) throw new ApiError("http", response.status);
      const contentType = response.headers
        .get("content-type")
        ?.split(";")[0]
        ?.trim()
        .toLowerCase();
      if (contentType !== "application/json")
        throw new ApiError("invalid-response");
      const value: unknown = await response.json();
      return parse(value);
    } catch (error: unknown) {
      if (signal.aborted) {
        throw new ApiError(options.signal?.aborted ? "aborted" : "timeout");
      }
      if (error instanceof ApiError) throw error;
      if (
        error instanceof InvalidApiResponseError ||
        error instanceof SyntaxError
      ) {
        throw new ApiError("invalid-response");
      }
      throw new ApiError("network");
    } finally {
      clearTimeout(timer);
    }
  }

  return {
    investigate: (request, options = {}) =>
      send(
        "/api/v1/investigations",
        {
          method: "POST",
          headers: {
            "content-type": "application/json",
            accept: "application/json",
          },
          body: JSON.stringify(request),
        },
        parseReport,
        300_000,
        options,
      ),
    health: (options = {}) =>
      send(
        "/api/health",
        { method: "GET", headers: { accept: "application/json" } },
        parseHealth,
        10_000,
        options,
      ),
  };
}
