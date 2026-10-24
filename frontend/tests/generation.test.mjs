import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const script = fileURLToPath(new URL('../scripts/generate-api.mjs', import.meta.url));
const schema = fileURLToPath(new URL('../src/lib/api/generated/openapi.json', import.meta.url));

test('generation is deterministic and detects schema/type drift without rewriting', () => {
  const directory = mkdtempSync(join(tmpdir(), 'incident-contract-'));
  try {
    const input = join(directory, 'openapi.json');
    const output = join(directory, 'openapi.d.ts');
    writeFileSync(input, readFileSync(schema));
    const args = [script, '--schema', input, '--output', output];
    const run = (...options) => spawnSync(process.execPath, [...args, ...options], { cwd: directory, encoding: 'utf8' });
    assert.equal(run().status, 0);
    const original = readFileSync(output, 'utf8');
    assert.equal(run().status, 0);
    assert.equal(readFileSync(output, 'utf8'), original);
    assert.equal(run('--check').status, 0);
    const changed = JSON.parse(readFileSync(input, 'utf8'));
    changed.components.schemas.IncidentReport.properties.summary = { type: 'integer' };
    writeFileSync(input, JSON.stringify(changed));
    const drift = run('--check');
    assert.equal(drift.status, 1);
    assert.match(drift.stdout, /drift/i);
    assert.equal(readFileSync(output, 'utf8'), original);
    assert.equal(run().status, 0);
    assert.notEqual(readFileSync(output, 'utf8'), original);
    writeFileSync(output, 'stale types');
    assert.equal(run('--check').status, 1);
    rmSync(output);
    assert.equal(run('--check').status, 1);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
