import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";
import prettier from "eslint-config-prettier/flat";

export default defineConfig([
  ...nextVitals,
  ...nextTypescript,
  prettier,
  globalIgnores([
    ".next/**",
    ".contract-build/**",
    "next-env.d.ts",
    "src/lib/api/generated/**",
    "playwright-report/**",
    "test-results/**",
  ]),
]);
