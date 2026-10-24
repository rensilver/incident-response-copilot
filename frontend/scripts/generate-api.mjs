/** Generate frontend types from the checked-in, resource-free FastAPI schema. */
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { parseArgs } from "node:util";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const { values } = parseArgs({
  options: {
    check: { type: "boolean", default: false },
    schema: {
      type: "string",
      default: fileURLToPath(
        new URL("../src/lib/api/generated/openapi.json", import.meta.url),
      ),
    },
    output: {
      type: "string",
      default: fileURLToPath(
        new URL("../src/lib/api/generated/openapi.d.ts", import.meta.url),
      ),
    },
  },
});
const schema = JSON.parse(await readFile(values.schema, "utf8"));
// Defaults describe server input behavior; optional request fields stay optional.
const types = astToString(
  await openapiTS(schema, { defaultNonNullable: false }),
);
if (values.check) {
  let existing;
  try {
    existing = await readFile(values.output, "utf8");
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  if (existing !== types) {
    console.log("OpenAPI type drift: run make api-contract to regenerate.");
    process.exitCode = 1;
  } else {
    console.log("OpenAPI types match the schema.");
  }
} else {
  await mkdir(dirname(values.output), { recursive: true });
  await writeFile(values.output, types);
  console.log("OpenAPI types generated.");
}
