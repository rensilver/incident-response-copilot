// Serve only the current media locally and verify real playback/captions offline.
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { resolve, extname, sep } from "node:path";
import {
  chromium,
  expect,
} from "../../../frontend/node_modules/@playwright/test/index.mjs";

const root = resolve("docs/media/2026-10-26");
const types = {
  ".html": "text/html",
  ".mp4": "video/mp4",
  ".vtt": "text/vtt",
  ".png": "image/png",
};
const server = createServer(async (request, response) => {
  const path = resolve(
    root,
    "." + new URL(request.url, "http://localhost").pathname,
  );
  if (!path.startsWith(root + sep)) return response.writeHead(403).end();
  try {
    const data = await readFile(path);
    const range = /^bytes=(\d+)-(\d*)$/.exec(request.headers.range ?? "");
    const start = range ? Number(range[1]) : 0;
    const end = range?.[2] ? Number(range[2]) : data.length - 1;
    const headers = {
      "Content-Type": types[extname(path)] ?? "text/plain",
      "Content-Length": end - start + 1,
      "Accept-Ranges": "bytes",
    };
    if (range)
      headers["Content-Range"] = `bytes ${start}-${end}/${data.length}`;
    response.writeHead(range ? 206 : 200, headers);
    response.end(data.subarray(start, end + 1));
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));
const browser = await chromium.launch();
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1100 },
  });
  const url = `http://127.0.0.1:${server.address().port}/demo.html`;
  await page.goto(url);
  await expect(
    page.getByRole("heading", { name: "Descriptive transcript" }),
  ).toBeVisible();
  await page.waitForFunction(
    () => document.querySelector("video").readyState >= 2,
  );
  const initial = await page.locator("video").evaluate((video) => ({
    controls: video.controls,
    autoplay: video.autoplay,
    paused: video.paused,
    duration: video.duration,
  }));
  assert.equal(initial.controls, true);
  assert.equal(initial.autoplay, false);
  assert.equal(initial.paused, true);
  assert.ok(initial.duration > 40 && initial.duration < 80);
  await page.locator("video").evaluate((video) => video.play());
  await page.waitForFunction(
    () => document.querySelector("video").currentTime > 1,
  );
  await page.locator("video").evaluate((video) => video.pause());
  await page.waitForFunction(
    () => document.querySelector("track").track.cues?.length === 6,
  );
  const cues = await page.locator("track").evaluate((track) => ({
    mode: track.track.mode,
    count: track.track.cues.length,
  }));
  assert.equal(cues.mode, "showing");
  const edits = JSON.parse(
    await readFile(
      "docs/validation/2026-10-26-evaluation/media-edits.json",
      "utf8",
    ),
  );
  const sought = [];
  for (let i = 0; i < edits.edits.length; i++) {
    const time = edits.edits[i].output_start_seconds + 8;
    await page.locator("video").evaluate((video, seek) => {
      video.currentTime = seek;
    }, time);
    await page.waitForFunction(() => !document.querySelector("video").seeking);
    const actual = await page
      .locator("video")
      .evaluate((video) => video.currentTime);
    assert.ok(
      Math.abs(actual - time) < 0.25,
      `seek target=${time} actual=${actual}`,
    );
    sought.push({ target: time, actual });
    await page
      .locator("video")
      .screenshot({ path: `/tmp/ic-demo-frame-${i}.png` });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await page.screenshot({
    path: "/tmp/ic-demo-player-mobile.png",
    fullPage: true,
  });
  const result = {
    chromium: browser.version(),
    playback: "passed",
    ...initial,
    captions: cues,
    seeked_scenes: 3,
    scene_times: sought,
    mobile_overflow: false,
    scope: "Local media only; zero provider calls",
  };
  await writeFile(
    "docs/validation/2026-10-26-evaluation/media-check.json",
    JSON.stringify(result, null, 2) + "\n",
  );
  console.log(JSON.stringify(result));
} finally {
  await browser.close();
  await new Promise((done) => server.close(done));
}
