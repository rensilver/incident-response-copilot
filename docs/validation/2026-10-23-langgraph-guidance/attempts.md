# Retained initial attempts

These are initial inspection and evidence-tool failures from this task. They
were corrected in the evidence collector; no application code was changed.

1. An inline `.venv/bin/python` inspection exited 1 while calling
   `inspect.getfile(get_env_var)`: `TypeError: module, class, method, function,
   traceback, frame, or code object was expected, got _lru_cache_wrapper`.
   The final collector uses `inspect.unwrap` before source inspection.
2. `.venv/bin/ruff check --config backend/pyproject.toml
   docs/validation/2026-10-23-langgraph-guidance` passed. The following
   `.venv/bin/black --config backend/pyproject.toml --check
   docs/validation/2026-10-23-langgraph-guidance` exited 1: one file would be
   reformatted. The chained mypy command did not run. Black then reformatted
   `inspect_installed.py` successfully.
3. `.venv/bin/mypy --config-file backend/pyproject.toml --strict
   docs/validation/2026-10-23-langgraph-guidance/inspect_installed.py` exited 1
   with four errors: `object` was incompatible with `inspect.unwrap` and
   `inspect.signature` (lines 65/67), the channel required a type annotation
   (87), and `CompiledStateGraph` did not declare `__parameters__` (115).
   The collector now types callables and the channel explicitly and accesses
   runtime generic metadata through `vars`. An intermediate `getattr` version
   passed mypy but failed Ruff B009 (constant attribute name); the final version
   needs no suppression. The full B009 output is in `verification.log`.
4. Live browsing of `https://reference.langchain.com/python/langgraph/graphs/`
   and its `#langgraph.graph.state.StateGraph` anchor failed with
   `Unsupported content-type: text/markdown`. The `/graphs/StateGraph` path
   was inaccessible. The `/types/#langgraph.types.RetryPolicy` page had the
   same content-type failure. The official overview, usage, concurrent-update
   error, and tracing guides were readable. Installed signatures and source
   inspection provide the version-specific API evidence instead.
5. `git add docs/validation/2026-10-23-langgraph-guidance` exited 128:
   `fatal: Unable to create '.git/index.lock': Read-only file system`.
   Repository metadata requires host access for the owner-authorized staging
   and commit; evidence files remain writable in the workspace.

Final check commands and outcomes are in [verification.log](verification.log).
