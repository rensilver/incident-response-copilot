# Isolating an asyncio/thread stall

If a bounded offline check stalls in a restricted execution environment, retain
its output and run this standard-library-only probe in both the restricted
environment and the normal host context:

```sh
timeout 10 .venv/bin/python docs/validation/probe_asyncio.py
```

The expected output is `worker ran` followed by `event loop received: thread result`.
The probe awaits `asyncio.to_thread` with a two-second async deadline and prints a
traceback after five seconds. The external bound also limits interpreter shutdown.
It imports no application or graph code and needs no dotenv, Docker or network.

If the probe and unchanged tests stall only in one context, record the difference
as an execution-environment limitation. That comparison does not identify the
precise sandbox mechanism or establish an application defect. Do not change graph
code solely to work around an independently reproduced environment stall. Preserve
both failures and successful comparisons, with commands and bounds in new evidence.
