# Ollama hardware assessment — 2026-09-21

Groq is the primary provider. The assessed laptop does not currently have enough
available RAM for the application's conservative `qwen3:4b` cold-load threshold.
Automatic fallback is implemented, but successful local inference on this laptop
has not been demonstrated.

## Observed environment

| Measurement | Observed value |
|---|---|
| CPU | AMD Ryzen 5 7520U, 4 cores / 8 threads |
| Usable RAM | 6.5 GiB |
| Available RAM at inspection | Approximately 2.9 GiB |
| Swap | 4.0 GiB total; approximately 2.7 GiB already used |
| Existing container | Another project's Ollama server, approximately 28 MiB idle |
| Port conflict | That server binds `127.0.0.1:11434` |
| This project's stack | Stopped during assessment |
| GPU access in this project's Compose file | Not configured |

Read-only checks: `free -h`, `lscpu`, `docker ps`, and
`docker stats --no-stream`. Available RAM changes with other applications.
No existing container was stopped or modified. The idle Ollama server's memory
usage is not the memory required by a loaded model.

## Why local fallback is constrained

The published `qwen3:4b` Q4_K_M artifact is approximately 2.5 GB. That is model file
size, not total runtime RAM. Context buffers and runtime allocations need additional
memory. [Ollama model information](https://ollama.com/library/qwen3:4b).

The project also runs Elasticsearch, Prometheus, Grafana, FastAPI, and optionally
Streamlit. Elasticsearch alone has a configured 512 MiB Java heap, in addition to
other process memory. Combined stack usage has not been measured yet. With only
2.9 GiB available before starting that stack, local inference alongside it is not
established as practical. Existing swap use also indicates memory pressure.

Ollama's context length and parallelism increase memory requirements. Compose sets
`OLLAMA_NUM_PARALLEL=1` and `OLLAMA_MAX_LOADED_MODELS=1`; the client uses a 4096-token
context and serializes calls within one application instance.
[Ollama memory and concurrency documentation](https://docs.ollama.com/faq).

## Implemented limits

- Before local inference, the client checks `/api/ps` and available system RAM.
  A cold model requires 4096 MiB available; an already loaded matching model requires
  1024 MiB. These are conservative application thresholds, not measured model minima.
- Insufficient memory raises a clear provider error before sending an inference
  request. If Groq has also failed, fallback reports that Ollama is unavailable.
- Ollama calls have a 60-second deadline including queueing and memory checks, a
  2048-token output cap, disabled thinking, and a one-minute model keep-alive.
  The HTTP deadline does not guarantee immediate server-side cancellation.
- Groq requests have a 30-second deadline with SDK retries disabled. Schema repair
  and graph steps can make an investigation take longer than a single request.
- The RAM check measures the application host; it does not reserve memory, enforce
  container limits, or protect other Ollama clients. For a remote Ollama server,
  set `OLLAMA_MIN_AVAILABLE_MEMORY_MB=0` and manage capacity on that server.

## Demo implications and remaining measurements

Use Groq for this laptop's demo. Automatic fallback remains configured, but needs
sufficient memory and an available Ollama server with `qwen3:4b` already downloaded.
A larger machine or a remote Ollama server is needed to validate local inference
without the current memory constraint. Resolve the port conflict before starting
this project's Ollama container; changing `OLLAMA_BASE_URL` alone does not change
Compose's published port.

Full-stack RAM use, cold-load time, investigation latency, and whether runs fit the
Streamlit client's 300-second timeout remain for final live validation. No local
model benchmark or successful live fallback is claimed by this assessment.
