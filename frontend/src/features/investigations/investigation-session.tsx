"use client";

import { useState, type FormEvent } from "react";
import { createApiClient } from "../../lib/api/client";
import { InvestigationReport } from "./investigation-report";
import type { IncidentReport, InvestigationRequest } from "../../lib/api/types";

const presets = [
  {
    label: "Memory leak",
    query: "checkout-service memory keeps climbing",
    service: "checkout-service",
  },
  {
    label: "Slow dependency",
    query: "payment-service latency is elevated",
    service: "payment-service",
  },
  {
    label: "Bad deploy",
    query: "cart-service error rate spiked after the last deploy",
    service: "cart-service",
  },
] as const;

/** Browser-owned form state; all investigation work goes through FastAPI. */
export function InvestigationSession(): React.JSX.Element {
  const [query, setQuery] = useState("");
  const [service, setService] = useState("");
  const [minutes, setMinutes] = useState("60");
  const [errors, setErrors] = useState<{
    query?: string | undefined;
    minutes?: string | undefined;
  }>({});
  const [result, setResult] = useState<{
    report: IncidentReport;
    request: InvestigationRequest;
  } | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState(
    "Describe an incident or choose a seeded scenario.",
  );

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (pending) return;
    const duration = Number(minutes);
    const nextErrors = {
      query: query.trim() ? undefined : "Enter an incident question.",
      minutes:
        minutes.trim() &&
        Number.isInteger(duration) &&
        duration >= 1 &&
        duration <= 1440
          ? undefined
          : "Enter a whole number from 1 to 1440.",
    };
    setErrors(nextErrors);
    if (nextErrors.query || nextErrors.minutes) return;
    const request: InvestigationRequest = {
      query: query.trim(),
      minutes_back: duration,
      ...(service.trim() ? { service: service.trim() } : {}),
    };
    setPending(true);
    setMessage("Investigating…");
    try {
      const report = await createApiClient().investigate(request);
      setResult({ report, request });
      setMessage("Investigation received.");
    } catch {
      setMessage(
        "Investigation unavailable. Review the question and try again.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="investigation-grid">
      <form
        className="composer"
        onSubmit={(event) => void submit(event)}
        noValidate
        aria-label="Investigation"
      >
        <fieldset disabled={pending}>
          <legend>Try a seeded scenario</legend>
          <div className="presets">
            {presets.map((preset) => (
              <button
                type="button"
                key={preset.label}
                onClick={() => {
                  setQuery(preset.query);
                  setService(preset.service);
                  setMinutes("180");
                  setErrors({});
                }}
              >
                {preset.label}
              </button>
            ))}
          </div>
          <label htmlFor="incident-query">Incident question</label>
          <textarea
            id="incident-query"
            name="query"
            rows={4}
            autoComplete="off"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-invalid={Boolean(errors.query)}
            aria-describedby={errors.query ? "query-error" : undefined}
          />
          {errors.query ? (
            <p className="field-error" id="query-error">
              {errors.query}
            </p>
          ) : null}
          <div className="form-fields">
            <div>
              <label htmlFor="incident-service">Service (optional)</label>
              <input
                id="incident-service"
                name="service"
                autoComplete="off"
                spellCheck={false}
                value={service}
                onChange={(event) => setService(event.target.value)}
                aria-describedby="service-hint"
              />
              <p id="service-hint">
                Leave blank to investigate without a service filter.
              </p>
            </div>
            <div>
              <label htmlFor="incident-minutes">Window (minutes)</label>
              <input
                id="incident-minutes"
                name="minutes_back"
                type="number"
                inputMode="numeric"
                min={1}
                max={1440}
                step={1}
                value={minutes}
                onChange={(event) => setMinutes(event.target.value)}
                aria-invalid={Boolean(errors.minutes)}
                aria-describedby="minutes-hint minutes-error"
              />
              <p id="minutes-hint">1–1440 minutes</p>
              {errors.minutes ? (
                <p className="field-error" id="minutes-error">
                  {errors.minutes}
                </p>
              ) : null}
            </div>
          </div>
          <button className="primary-action" type="submit">
            {pending ? "Investigating…" : "Run investigation"}
          </button>
        </fieldset>
        <noscript>
          Enable JavaScript to submit investigations and check dependencies.
        </noscript>
      </form>
      <section className="result-area" aria-label="Investigation result">
        <p role="status">{message}</p>
        {result ? (
          <InvestigationReport
            report={result.report}
            request={result.request}
          />
        ) : null}
      </section>
    </div>
  );
}
