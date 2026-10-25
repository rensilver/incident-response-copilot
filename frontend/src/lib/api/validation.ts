/** Validate untrusted JSON before handing it to browser consumers. */
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import type { ValidateFunction } from "ajv";
import schema from "./generated/openapi.json" with { type: "json" };
import type {
  Health,
  IncidentReport,
  InvestigationError,
  RequestError,
} from "./types.js";

export class InvalidApiResponseError extends Error {
  constructor() {
    super("Invalid API response.");
    this.name = "InvalidApiResponseError";
  }
}

// Keep OpenAPI's reference container as an annotation, with strict validation of
// every referenced JSON Schema. No coercion, default insertion or field removal.
const ajv = new Ajv2020({ strict: true });
addFormats(ajv);
ajv.addKeyword({ keyword: "components", schemaType: "object" });
const responses = schema.paths["/api/v1/investigations"].post.responses;
const validateReport = ajv.compile<IncidentReport>({
  ...responses["200"].content["application/json"].schema,
  components: schema.components,
});
const validateHealth = ajv.compile<Health>({
  ...schema.paths["/health"].get.responses["200"].content["application/json"]
    .schema,
  components: schema.components,
});
const validateInvestigationError = ajv.compile<InvestigationError>({
  ...responses["503"].content["application/json"].schema,
  components: schema.components,
});
const validateRequestError = ajv.compile<RequestError>({
  ...responses["422"].content["application/json"].schema,
  components: schema.components,
});

function parse<T>(value: unknown, validate: ValidateFunction<T>): T {
  if (!validate(value)) throw new InvalidApiResponseError();
  return value;
}

export function parseReport(value: unknown): IncidentReport {
  const report = parse(value, validateReport);
  if (report.investigation_window) {
    const start = Date.parse(report.investigation_window.start);
    const end = Date.parse(report.investigation_window.end);
    // JSON Schema permits leap seconds that JavaScript Date cannot render.
    if (!Number.isFinite(start) || !Number.isFinite(end) || end < start)
      throw new InvalidApiResponseError();
  }
  return report;
}
export function parseHealth(value: unknown): Health {
  return parse(value, validateHealth);
}
export function parseInvestigationError(value: unknown): InvestigationError {
  return parse(value, validateInvestigationError);
}
export function parseRequestError(value: unknown): RequestError {
  return parse(value, validateRequestError);
}
