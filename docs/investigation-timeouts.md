# Investigation timeouts and cancellation

The service applies one cooperative execution deadline around the complete graph
invocation, shared by routing, parallel specialists, tools, correlation, and any
structured-output repairs. It starts immediately before `graph.ainvoke`, after
request validation and creation of the authoritative query window. It uses the
event loop's monotonic clock; the requested telemetry interval is independent.

## Budgets and coordination

| Layer | Current limit or required budget |
|---|---|
| Total graph execution | `INVESTIGATION_TIMEOUT_SECONDS`: default 240 s, finite, greater than zero and at most 240 s. Read through backend settings and injected into the service. |
| Individual model operation | `LLM_OPERATION_TIMEOUT_SECONDS`: default 60 s, configurable up to 180 s. One operation budget includes structured-output repair attempts. The total graph budget can expire first. |
| Current Streamlit HTTP client | 300 s network inactivity per operation; this is **not** a total wall-clock deadline. |
| Next.js proxy configuration | Explicit upstream socket inactivity timeout: 270 s, allowing 30 s beyond the maximum graph budget for cancellation/response delivery. See the [proxy contract](proxy-contract.md). |
| Future browser transport | Required total request budget: 300 s, allowing another 30 s beyond the proxy budget. Implementation belongs to the frontend task. |
| Health caller | Current UI uses 5 s network inactivity. `/health` probes concurrently; it does not run an investigation. |

The 240/270/300 coordination is a default delivery budget, not a strict completion
guarantee. Next.js rewrite configuration is present, but the frontend application
and browser transport are not implemented yet. A temporary socket harness verifies
delivery of a real shortened backend deadline through Next.js; the deployed browser
path must also be tested when introduced, allowing the 504 JSON response to arrive first.
Do not rely on a framework's unspecified proxy default. If introducing different
budgets, preserve the ordering: backend execution < proxy response < browser request.
Shorter client timeouts can still be appropriate for connection establishment.

FastAPI, the evaluation entrypoint, and both live recorders pass the configured
total budget to `IncidentService`. Direct construction without a budget uses the
same 240 s default and performs no environment lookup. The tracing recorder now
uses the service deadline instead of its former independent 180 s wrapper; both
recorders save the configured budget alongside results. Their overall runtimes
also include startup, artifact writing, pacing, health, and tracing delivery.

## Expiry and external cancellation

On expiry, `asyncio.timeout` cancels the graph's task. Normal cancellation reaches
in-flight model/tool calls and both parallel specialists. After cancellation
unwinds, the service raises `InvestigationTimeoutError`, and FastAPI returns:

```json
{"detail":"Investigation deadline exceeded."}
```

The status is 504. A collaborator that swallows cancellation and returns late
cannot turn the expired investigation into a 200 response. A provider's own
operation timeout stays a provider failure (503 if no usable report survives).
An unrelated unclassified `TimeoutError` is propagated as a server bug (500),
not mislabeled as total expiry. No automatic investigation retry is performed.

Cancellation from an ASGI server or caller propagates as `CancelledError`, without
becoming a deadline error or report. A timeout affects one investigation; shared
clients stay open for other requests until lifespan shutdown. The server should
drain/cancel active requests before closing those clients.

Cancellation is cooperative. Cleanup is awaited and can outlast the configured
budget. Blocking event-loop code, a collaborator that suppresses cancellation
indefinitely, repeated cancellation, abrupt process termination, slow request-body
upload/validation, startup, serialization, and response transmission are outside
the bounded graph execution guarantee. Cancelling local I/O does not prove a remote
model stopped computing or prevent charges. This is an execution budget, not a
hard kill timer or durable job system.

## Client disconnects

This synchronous JSON report route does not poll `http.disconnect` after consuming
the request body. A disconnect notification alone therefore leaves investigation
work running until completion or its total deadline. There is no report history
or reconnection endpoint to retrieve that abandoned result. A browser abort,
navigation, lost connection, or proxy timeout must never be presented as proof
that backend or remote-provider work stopped. A server may separately cancel its
request task, in which case the normal cancellation path above applies.

Offline ASGI tests queue a disconnect during blocked graph work and confirm both
normal completion and eventual deadline cancellation, plus explicit request-task
cancellation. Their response sink records attempted responses; it does not prove
delivery to a disconnected socket. No live browser, proxy, or socket behavior is
claimed by these tests.

## References and verification

See [the API response contract](api-contract.md) and
[deadline validation evidence](validation/2026-10-23-investigation-deadlines/README.md).
The implementation follows Python's
[timeout and cancellation semantics](https://docs.python.org/3.12/library/asyncio-task.html#timeouts).
HTTPX distinguishes [connect/read/write/pool timeouts](https://www.python-httpx.org/advanced/timeouts/),
while ASGI specifies a separate
[disconnect receive event](https://asgi.readthedocs.io/en/latest/specs/www.html#disconnect-receive-event).
