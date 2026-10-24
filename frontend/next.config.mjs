/** Configure the server-side FastAPI proxy; no credentials belong in this file. */
export default function configure() {
  const value =
    process.env.INCIDENT_COPILOT_BACKEND_ORIGIN ?? "http://127.0.0.1:8000";
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

  return {
    // Next's external rewrite proxy uses milliseconds. Allow delivery of the
    // backend's cooperative 240-second deadline response before timing out.
    experimental: { proxyTimeout: 270_000 },
    async rewrites() {
      return {
        beforeFiles: [
          {
            source: "/api/v1/investigations",
            destination: `${backend.origin}/api/v1/investigations`,
          },
          {
            source: "/api/health",
            destination: `${backend.origin}/health`,
          },
        ],
        afterFiles: [],
        fallback: [],
      };
    },
  };
}
