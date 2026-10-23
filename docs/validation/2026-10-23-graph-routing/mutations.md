# Deliberate mutation checks

These are test-sensitivity checks, not defects found in the original graph.
Each change was applied alone, the corresponding new test command ran through
the evidence runner with a thirty-second bound and host access, and the original
file was restored in a `finally` block. The mutation controller asserted pytest
exited 1, restored exact source contents, and continued to the next case.
No mutation is present in the committed executable code.

## Single-specialist join

In `backend/src/incident_copilot/agents/graph.py`, temporarily replace the separate
metrics/logs edges to correlation with:

```python
builder.add_edge([AgentName.METRICS.value, AgentName.LOGS.value], AgentName.CORRELATION.value)
```

Run:

```bash
.venv/bin/pytest \
  'backend/tests/unit/agents/test_graph.py::test_selected_branches_finish_before_one_correlation_with_all_evidence[metrics]' \
  -q --tb=short
```

[Actual result](mutation-join.log): one failure. The timeline contained only
`metrics_agent`; correlation never ran because the log branch was not selected.

## Simultaneous error updates

In `backend/src/incident_copilot/agents/state.py`, temporarily change the
`InvestigationState.errors` annotation from `Annotated[list[str], operator.add]`
to `list[str]`. Leave node-specific update types unchanged.

```bash
.venv/bin/pytest \
  backend/tests/unit/agents/test_graph.py::test_both_branch_errors_are_merged_with_existing_errors_before_correlation \
  -q --tb=short
```

[Actual result](mutation-errors-reducer.log): one failure with
`InvalidUpdateError` at the `errors` channel when both specialist updates commit.

## Earlier findings retained

In `InvestigationState`, temporarily remove `Annotated[..., operator.add]` from
both `metrics_findings` and `log_findings`, keeping their plain list types.

```bash
.venv/bin/pytest \
  backend/tests/unit/agents/test_graph.py::test_selected_branches_finish_before_one_correlation_with_all_evidence \
  -q --tb=short
```

[Actual result](mutation-findings-reducers.log): all ten cases failed because
new findings replaced prior evidence. The metrics-only and logs-only cases
independently detect removal of their respective finding reducer.

For reproduction, use a clean scratch checkout and restore each change before
running another mutation or final verification. The passing full suite after
restoration is separate evidence from these deliberately failing runs.
