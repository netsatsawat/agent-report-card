# agent-report-card

> A performance review for your AI agent: the checks that matter before it
> touches production. One CLI, one YAML test file, one markdown report.

An agent that resolved 85% of requests in testing can still fail in production.
Traditional monitoring shows green while customer satisfaction drops. This tool is
the code version of that argument: define your test set once, run it against your
RAG bot or agent, get a report a stakeholder can read.

**Status: scaffold.** Target usage:

```
agent-report-card run --tests board_questions.yaml --endpoint http://localhost:8000
→ accuracy 84% · hallucination 6% · 3 failures → report.md
```

## Design principles

- **Small and opinionated.** Not a framework, a report card. The ~20 checks that
  matter, not 200 configurable metrics. (Ragas, promptfoo, and DeepEval exist and
  are good; this is deliberately the minimal, decision-oriented layer.)
- **Local-model friendly.** The LLM-as-judge can be a local model. It pairs with
  [sovereign-rag](https://github.com/netsatsawat/sovereign-rag) so evaluation respects the same data boundary
  as the system under test.
- **Reports for humans.** Output is a markdown report with the failing cases
  quoted, not a JSON blob.

## Roadmap

- **v0.1**: RAG QA mode: accuracy / hallucination / citation checks against a
  YAML test set; exact-match + LLM-judge scoring; markdown report.
- **v0.2**: agent-trace mode: per-step scoring of multi-step agent runs, surfacing
  the compound-failure profile (see [agent-failure-lab](https://github.com/netsatsawat/agent-failure-lab)).
- **v0.3**: CI mode: baseline diffing, fail-the-build on regression.

---

Written by [Satsawat Natakarnkitkul](https://satsawat.ai), author of *Why Your
AI Agent Will Fail*. Companion article: "Why Your AI Agent Needs a Performance
Review (Literally)" at [satsawat.ai](https://satsawat.ai) · Newsletter:
[AI in Practice](https://satsawat.ai/#newsletter)

License: MIT
