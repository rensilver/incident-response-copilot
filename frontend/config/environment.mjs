/** Server configuration only. Browser callers always use relative API paths. */
export function readFrontendEnvironment(environment) {
  // This application has no public environment configuration. Reject every
  // public key, including aliases, before Next can inline values into bundles.
  if (
    Object.keys(environment).some((name) => name.startsWith("NEXT_PUBLIC_"))
  ) {
    throw new Error(
      "This frontend accepts no NEXT_PUBLIC_* settings. Keep model and tracing credentials in the backend.",
    );
  }
  const value =
    environment.INCIDENT_COPILOT_BACKEND_ORIGIN ?? "http://127.0.0.1:8000";
  const invalidOrigin =
    "INCIDENT_COPILOT_BACKEND_ORIGIN must be an HTTP(S) origin without credentials, path, query, or fragment.";
  let backend;
  try {
    backend = new URL(value);
  } catch {
    // URL parser errors include their input; expose only the setting name.
    throw new Error(invalidOrigin);
  }
  if (
    !["http:", "https:"].includes(backend.protocol) ||
    backend.username ||
    backend.password ||
    backend.pathname !== "/" ||
    backend.search ||
    backend.hash
  ) {
    throw new Error(invalidOrigin);
  }

  return { backendOrigin: backend.origin };
}
