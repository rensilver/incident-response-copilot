import assert from "node:assert/strict";
import test from "node:test";
import { readFrontendEnvironment } from "../config/environment.mjs";

for (const name of [
  "NEXT_PUBLIC_OPENAI_API_KEY",
  "NEXT_PUBLIC_LANGSMITH_API_KEY",
  "NEXT_PUBLIC_LANGCHAIN_API_KEY",
  "NEXT_PUBLIC_MODEL_TOKEN",
  "NEXT_PUBLIC_BACKEND_ORIGIN",
]) {
  test(`public configuration is rejected without echoing ${name}'s value`, () => {
    assert.throws(() => readFrontendEnvironment({ [name]: "private-canary" }), {
      message:
        "This frontend accepts no NEXT_PUBLIC_* settings. Keep model and tracing credentials in the backend.",
    });
  });
}

test("backend-only provider/tracing settings are never forwarded into frontend configuration", () => {
  assert.deepEqual(
    readFrontendEnvironment({
      INCIDENT_COPILOT_BACKEND_ORIGIN: "http://app:8000/",
      OPENAI_API_KEY: "private-canary",
      LANGSMITH_API_KEY: "private-canary",
      LANGCHAIN_TRACING_V2: "true",
    }),
    { backendOrigin: "http://app:8000" },
  );
});
