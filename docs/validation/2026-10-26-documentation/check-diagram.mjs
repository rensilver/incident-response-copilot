// Render the actual README diagram with a separately installed Mermaid bundle.
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { chromium } from "../../../frontend/node_modules/@playwright/test/index.mjs";

const markdown = await readFile("README.md", "utf8");
const diagrams = [...markdown.matchAll(/```mermaid\n([\s\S]*?)```/g)];
assert.equal(diagrams.length, 1);
const bundle = process.argv[2];
assert.ok(bundle, "Provide the installed mermaid/dist/mermaid.min.js path");
const output = "docs/validation/2026-10-26-documentation";
const browser = await chromium.launch();
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  await page.setContent(
    "<!doctype html><html><body><main></main></body></html>",
  );
  await page.addScriptTag({ path: bundle });
  const rendered = await page.evaluate(async (source) => {
    window.mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });
    const { svg } = await window.mermaid.render("readme-system", source);
    document.querySelector("main").innerHTML = svg;
    return {
      svg,
      nodes: [...document.querySelectorAll("g.node")].map((node) =>
        node.textContent.trim(),
      ),
      edges: document.querySelectorAll(".flowchart-link").length,
    };
  }, diagrams[0][1]);
  for (const label of [
    "Next.js",
    "FastAPI",
    "MetricsSource",
    "LogSource",
    "LLMProvider",
    "Grafana",
    "LangSmith",
  ])
    assert.ok(
      rendered.nodes.some((node) => node.includes(label)),
      label,
    );
  assert.ok(rendered.nodes.length >= 20 && rendered.edges >= 20);
  await writeFile(`${output}/system-design.svg`, rendered.svg);
  await page.locator("svg").screenshot({ path: `${output}/system-design.png` });
  const result = {
    status: "passed",
    renderer: "mermaid 11.12.0",
    chromium: browser.version(),
    nodes: rendered.nodes,
    edges: rendered.edges,
  };
  await writeFile(
    `${output}/diagram-check.json`,
    JSON.stringify(result, null, 2) + "\n",
  );
  console.log(JSON.stringify(result));
} finally {
  await browser.close();
}
