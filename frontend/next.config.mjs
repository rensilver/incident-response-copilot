import { readFrontendEnvironment } from "./config/environment.mjs";

/** Configure the server-side FastAPI proxy; no credentials belong in this file. */
export default function configure() {
  const { backendOrigin } = readFrontendEnvironment(process.env);

  return {
    output: "standalone",
    // Next's external rewrite proxy uses milliseconds. Allow delivery of the
    // backend's cooperative 240-second deadline response before timing out.
    experimental: { proxyTimeout: 270_000 },
    async rewrites() {
      return {
        beforeFiles: [
          {
            source: "/api/v1/investigations",
            destination: `${backendOrigin}/api/v1/investigations`,
          },
          {
            source: "/api/health",
            destination: `${backendOrigin}/health`,
          },
        ],
        afterFiles: [],
        fallback: [],
      };
    },
  };
}
