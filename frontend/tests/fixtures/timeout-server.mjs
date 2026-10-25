/** Local-only controlled backend for real proxy/browser budget checks. */
import { createServer } from "node:http";

const attempts = [];
const server = createServer(async (request, response) => {
  if (request.method === "GET" && request.url === "/health") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({ status: "ok", dependencies: { llm: true } }));
    return;
  }
  if (request.method === "GET" && request.url === "/checks") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify(attempts));
    return;
  }
  if (request.method !== "POST" || request.url !== "/api/v1/investigations") {
    response.writeHead(404).end();
    return;
  }
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  let value;
  try {
    value = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    response.writeHead(400).end();
    return;
  }
  if (
    ![
      "backend deadline fixture",
      "proxy inactivity fixture",
      "browser deadline fixture",
    ].includes(value.query)
  ) {
    response.writeHead(400).end();
    return;
  }
  const started = performance.now();
  const record = { mode: value.query, chunks: 0, closedAfterMs: null };
  attempts.push(record);
  let timer;
  response.on("close", () => {
    clearInterval(timer);
    record.closedAfterMs = Math.round(performance.now() - started);
  });
  if (value.query === "backend deadline fixture") {
    timer = setTimeout(() => {
      response.writeHead(504, { "content-type": "application/json" });
      response.end(JSON.stringify({ detail: "Controlled backend deadline" }));
    }, 31_000);
  } else if (value.query === "browser deadline fixture") {
    // Continue body activity beyond the proxy inactivity budget; the browser's
    // total fetch/body budget must still expire without receiving valid JSON.
    response.writeHead(200, { "content-type": "application/json" });
    response.write('{"summary":"');
    timer = setInterval(() => {
      record.chunks++;
      response.write("waiting ");
    }, 10_000);
  }
  // The inactivity fixture sends no headers/body. Next's real proxy timer owns it.
});
server.requestTimeout = 0;
server.listen(18765, "127.0.0.1");
process.on("SIGTERM", () => {
  server.closeAllConnections();
  server.close(() => process.exit(0));
});
