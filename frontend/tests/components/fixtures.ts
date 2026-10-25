import type { IncidentReport } from "../../src/lib/api/types";

export const report: IncidentReport = {
  summary: "Dependency timeout observed in payment-service.",
  likely_causes: [
    {
      title: "Possible fraud-api slowdown",
      rationale: "Payment timeouts cite fraud-api; timing needs confirmation.",
      confidence: 0.73,
      supporting_evidence: [
        {
          source: "logs",
          detail: "upstream timeout calling fraud-api after 2000ms",
        },
        {
          source: "metrics",
          detail: "payment-service p95 increased by 140 ms",
        },
      ],
    },
  ],
  confidence: 0.654321,
  next_steps: ["Compare fraud-api timing with payment-service symptoms."],
  investigation_window: {
    start: "2026-10-25T07:13:14.123-03:00",
    end: "2026-10-25T10:13:14.123-03:00",
  },
};

export function healthResponse(): Response {
  return Response.json({
    status: "degraded",
    dependencies: { prometheus: true, elasticsearch: true, llm: false },
  });
}
