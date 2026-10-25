// Independent diagnostic: a child process must return its literal stdout.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";

for (const detached of [false, true]) {
  const result = await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ["-e", "process.stdout.write('probe')"], {
      detached,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8").on("data", (data) => (stdout += data));
    child.stderr.setEncoding("utf8").on("data", (data) => (stderr += data));
    child.on("error", reject);
    child.on("close", (code) => resolve({ detached, code, stdout, stderr }));
  });
  console.log(JSON.stringify(result));
  assert.equal(result.code, 0);
  assert.equal(result.stdout, "probe");
  assert.equal(result.stderr, "");
}
