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
other process memory. Combined stack usage had not been measured at the initial inspection. With only
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
without the current memory constraint. The initial port conflict was absent during
the 2026-09-22 validation; all five project containers started successfully.

Cold-load time, local-model investigation latency, and the Streamlit client's
300-second timeout remain unverified. No local model benchmark or successful live
fallback is claimed by this assessment.

## Docker/Groq measurements — 2026-09-22

The cloud-backed stack built and started with no local model loaded. Before startup,
available RAM was 2,841 MiB and swap use was 665 MiB. The first post-start snapshot
showed about 1,436 MiB total container memory, 2,499 MiB host available RAM, and
1,908 MiB swap use.

Twenty-one samples during part of the paced integration run and subsequent idle time
showed 1,437.79–1,449.15 MiB total container memory (about 1.4 GiB), 2,400.2–2,644.8 MiB
available host RAM, and 2,016.2–2,035.9 MiB swap use. This includes FastAPI, Prometheus,
Elasticsearch, Grafana, and idle Ollama; it excludes Streamlit and local inference.
Sampled values are not continuous peak measurements, and other host applications
affect RAM availability and swap.

Three paced Groq API investigations completed in 4.686–6.448 seconds. An earlier
unpaced run hit Groq rate limits; automatic fallback attempted Ollama, but its RAM
guard refused to load a model with only 2,383–2,431 MiB available. The API returned
HTTP 503. Thus this laptop demonstrated cloud operation and safe local-load refusal,
while successful local fallback remains constrained by available memory.

See the [Docker validation record](validation/2026-09-22-docker/README.md) for
per-scenario results, measurement methodology, raw samples, and reproduction commands.

## Fallback failure validation — 2026-09-22

The owner confirmed continued testing on this laptop and recording successful local
inference as blocked. During the later failure-validation run, available RAM was
2,995 MiB before the tests, still below the default 4,096 MiB cold-load guard.
The model was already downloaded in the project volume but remained unloaded.

Disposable app containers verified HTTP 503 behavior for Groq authentication failure
combined with insufficient memory or an unreachable Ollama endpoint, and with
fallback disabled. The isolated memory test raised its floor above physical RAM to
guarantee no inference; the production guard was unchanged. Simulated HTTP tests
covered successful fallback through the real adapters, but no local inference success
or model-memory benchmark is claimed. See the
[failure-validation record](validation/2026-09-22-fallback/README.md).
