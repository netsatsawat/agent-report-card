# Running the gate inside Kestra

[`quality-gate.yml`](quality-gate.yml) runs a suite as a [Kestra](https://kestra.io) task and
stops a release when a gate fails.

```bash
# Kestra picks the flow up from the UI, or:
curl -X POST http://localhost:8080/api/v1/flows \
  -H "Content-Type: application/yaml" --data-binary @quality-gate.yml
```

## The problem this solves

Kestra's retry strategies are constant, exponential and random, and **none of them can be made
conditional on a task's exit code**. To the orchestrator a script task either failed or it did
not. This tool draws a distinction underneath that:

| Exit | Meaning | Should Kestra retry? |
|---|---|---|
| 0 | every gate passed | — |
| 1 | a gate failed; the suite ran fine, the bot is not good enough | **No** |
| 2 | the tool could not run; nothing was measured | **Yes** |

Wire the task up naively and `retry` applies to both. Exit 1 is deterministic, so three attempts
reproduce it three times, spend three lots of compute, and leave a real regression looking like a
flaky test. Exit 2 is the opposite: the endpoint may simply be slow to come up, which is exactly
what backoff is for.

## The shape

`gate.py` translates at the boundary, so the two failures stop being the same event:

- **exit 2** is re-raised as a task failure. It is the only outcome the retry policy can see, and
  the only one worth retrying.
- **exit 0 and exit 1** both leave the task successful, because in both cases the suite ran to
  completion. The verdict leaves as a Kestra output rather than a crash.
- A second task, `block_release`, fails the execution when `passed` is false. It carries **no
  retry block on purpose**: it decides about a result that has already been measured, so
  re-running it could only produce the same answer more slowly.

## The tri-state gate

`gates[].ok` in `report.scores.json` has three states, and the third one is easy to get wrong:

```json
{"name": "max_hallucination", "ok": null,
 "text": "could not evaluate: grounding needs the judge; drop --judge none to evaluate it"}
```

`null` means the gate could not be evaluated at all — `max_hallucination` does this whenever the
judge is off, because grounding needs a judge. Treating `null` as a failure blocks every run
without a judge. Treating it as a pass reports coverage the run never had. It is neither, so the
flow carries it out separately as `unevaluated_gates` and names it in the failure message.

## What it emits

Verified against the published 0.2.0 wheel and the bundled fixture bot:

```
::{"outputs": {"verdict": "PASS WITH WARNINGS", "passed": true, "accuracy": 1.0,
   "failures": 0, "failed_gates": [], "unevaluated_gates": ["max_hallucination"],
   "judge": "none (deterministic only)", "tool_version": "0.2.0"}}::
```

Consume it downstream with `{{ outputs.evaluate.vars.accuracy }}`, and the report itself with
`{{ outputs.evaluate.outputFiles['report.md'] }}`.

## Pointing it at a real bot

Two changes. Set `endpoint` to the service — `host.docker.internal` only reaches a bot running on
the host from inside the task container. Then replace the inline `tests.yaml` with your own
suite; `inputFiles` accepts a path or `{{ read('tests.yaml') }}` if you would rather keep the
suite in version control beside the flow.

Turning the judge on (`judge: ollama/qwen3:8b` or any supported spec) is what makes
`max_hallucination` evaluable. Run `agent-report-card judge-check` first — a judge that has not
sat its own exam should not be gating your releases.
