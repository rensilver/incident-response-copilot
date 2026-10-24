import assert from "node:assert/strict";
import test from "node:test";
import {
  InvalidApiResponseError,
  parseHealth,
  parseInvestigationError,
  parseReport,
  parseRequestError,
} from "../src/lib/api/validation.js";

const report = {
  summary: "cart-service errors rose",
  likely_causes: [{
    title: "deployment regression",
    rationale: "Errors followed deployment",
    confidence: 0.8,
    supporting_evidence: [{ source: "logs", detail: "<script>alert('untrusted')</script>" }],
  }],
  confidence: 0.8,
  next_steps: ["Compare deployment versions"],
  investigation_window: { start: "2026-10-23T20:00:00Z", end: "2026-10-23T21:00:00Z" },
};

test("accepts actual report shapes, preserves text and never coerces or mutates", () => {
  const input = structuredClone(report);
  assert.deepEqual(parseReport(input), report);
  assert.deepEqual(input, report);
  assert.deepEqual(parseReport({ ...report, likely_causes: [], next_steps: [], investigation_window: null }).likely_causes, []);
  const { investigation_window: _, ...withoutWindow } = report;
  assert.equal(parseReport(withoutWindow).investigation_window, undefined);
});

const invalidReports: [string, unknown][] = [
  ["null", null], ["array", []], ["HTML", "<html>upstream failure</html>"],
  ["missing required summary", { confidence: 0.5, likely_causes: [], next_steps: [] }],
  ["coerced confidence", { ...report, confidence: "0.8" }],
  ["low confidence", { ...report, confidence: -0.01 }],
  ["high confidence", { ...report, confidence: 1.01 }],
  ["non-finite confidence", { ...report, confidence: NaN }],
  ["invalid candidate confidence", { ...report, likely_causes: [{ ...report.likely_causes[0], confidence: 2 }] }],
  ["missing evidence detail", { ...report, likely_causes: [{ ...report.likely_causes[0], supporting_evidence: [{ source: "logs" }] }] }],
  ["unknown evidence source", { ...report, likely_causes: [{ ...report.likely_causes[0], supporting_evidence: [{ source: "grafana", detail: "observation" }] }] }],
  ["invalid steps", { ...report, next_steps: [42] }],
  ["invalid date", { ...report, investigation_window: { start: "yesterday", end: "2026-10-23T21:00:00Z" } }],
  ["missing window end", { ...report, investigation_window: { start: "2026-10-23T20:00:00Z" } }],
];
for (const [name, value] of invalidReports) {
  test(`rejects ${name} before treating a response as a report`, () => {
    assert.throws(() => parseReport(value), InvalidApiResponseError);
  });
}

test("accepts healthy/degraded dependency booleans and rejects unknown statuses", () => {
  for (const status of ["ok", "degraded"]) {
    assert.equal(parseHealth({ status, dependencies: { llm: false } }).dependencies.llm, false);
  }
  for (const value of [
    { status: "maybe", dependencies: {} },
    { status: "ok", dependencies: { llm: "false" } },
    { status: "ok" },
  ]) assert.throws(() => parseHealth(value), InvalidApiResponseError);
});

test("validates both public error shapes without rendering raw rejected payloads", () => {
  assert.deepEqual(parseInvestigationError({ detail: "Investigation unavailable; no usable report was produced." }), {
    detail: "Investigation unavailable; no usable report was produced.",
  });
  const invalidInput = { detail: [{ loc: ["body", "minutes_back", 0], msg: "Invalid request value.", type: "int_parsing" }] };
  assert.deepEqual(parseRequestError(invalidInput), invalidInput);
  for (const value of [invalidInput, {}, { detail: 42 }]) {
    assert.throws(() => parseInvestigationError(value), InvalidApiResponseError);
  }
  for (const value of [{ detail: "error" }, { detail: [{ loc: [true], msg: "invalid", type: "missing" }] }]) {
    assert.throws(() => parseRequestError(value), InvalidApiResponseError);
  }
  assert.throws(() => parseReport({ secret: "private-canary" }), (error: unknown) => {
    assert.ok(error instanceof InvalidApiResponseError);
    assert.equal(error.message, "Invalid API response.");
    assert.equal(JSON.stringify(error).includes("private-canary"), false);
    return true;
  });
});
