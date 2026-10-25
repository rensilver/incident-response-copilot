/** Compile-time checks catch widened unions, missing required fields and unchecked unknown payloads. */
import type {
  Health,
  IncidentReport,
  InvestigationRequest,
} from "../src/lib/api/types.js";

const minimalRequest: InvestigationRequest = { query: "q" };
const filteredRequest: InvestigationRequest = {
  query: "q",
  service: null,
  minutes_back: 17,
};
// @ts-expect-error A query remains required even though other inputs have defaults.
const missingQuery: InvestigationRequest = { minutes_back: 60 };
// @ts-expect-error Browser requests send numbers, not Pydantic coercion inputs.
const stringWindow: InvestigationRequest = { query: "q", minutes_back: "60" };
// @ts-expect-error Health status is a closed wire vocabulary.
const unknownHealth: Health = { status: "maybe", dependencies: {} };
const stringDependency: Health = {
  status: "degraded",
  // @ts-expect-error Health dependencies cannot silently become truthy strings.
  dependencies: { llm: "false" },
};
// @ts-expect-error Reports require all core fields.
const incompleteReport: IncidentReport = { summary: "q" };
const objectWindow: NonNullable<IncidentReport["investigation_window"]> = {
  // @ts-expect-error Timestamps arrive as wire strings, never Date objects.
  start: new Date(),
  // @ts-expect-error The end timestamp also remains a wire string.
  end: new Date(),
};

declare const payload: unknown;
// @ts-expect-error Unknown decoded JSON requires runtime validation.
const uncheckedReport: IncidentReport = payload;

void [
  minimalRequest,
  filteredRequest,
  missingQuery,
  stringWindow,
  unknownHealth,
  stringDependency,
  incompleteReport,
  objectWindow,
  uncheckedReport,
];
