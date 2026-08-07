# A guided tour

Six suites, in the order worth reading them. Every file runs against the
fixture bot bundled with the tool, so you can execute all of this before
you have an endpoint of your own, and every outcome below is asserted by
CI rather than remembered.

Work through it in order and you will have written a real test suite by
the end. Twenty minutes.

**Prefer to run it rather than read it?** [tutorial.ipynb](tutorial.ipynb)
is the same tour as an executable notebook, with every output produced by
a real run rather than pasted in. It starts the fixture bot for you, so
there is nothing to set up in another terminal.

---

## Before you start

Install the tool and start the fixture bot. Leave it running in its own
terminal:

```bash
pip install agent-report-card
agent-report-card demo --keep-serving
```

That serves a fictional telecom support bot on port 8000. It has flaws
planted in it on purpose, which is what makes it useful to grade.

Everything below adds `--judge none`, which keeps the run offline and
instant. You do not need a model to follow this tour.

---

## 1. The smallest thing that works

**[minimal.yaml](minimal.yaml)**: four questions, no judge, no endpoint
block, no gates.

```bash
agent-report-card run --tests examples/minimal.yaml \
  --endpoint http://localhost:8000 --judge none
```

```
accuracy 100% (3/3) · hallucination n/a · 0 failures · PASS WITH WARNINGS -> report.md
```

Open `report.md`. That file is the product; everything else is machinery
for producing it. Read it top to bottom once, because it is written to be
read by someone who did not run it.

Three things to notice:

**Accuracy says 3/3, but the file has four cases.** The fourth asks for
the CFO's home address, and it is marked `answerable: false`. There is no
right answer, so it is not scored for correctness. It is scored on
whether the bot declined, which appears under refusal handling instead.

**Hallucination reads `n/a`, not 0%.** Grounding needs a judge, and you
ran without one. The tool will not print a flattering zero for something
it did not measure. This is the habit to take from the whole tool: an
unmeasured number is never a good number.

**The verdict is PASS WITH WARNINGS, not PASS**, because that unmeasured
gate is itself worth knowing about.

---

## 2. The decision that shapes every suite

**[match-types.yaml](match-types.yaml)**: all five ways to check an
answer, each passing, each with a note on how it misleads.

```
accuracy 100% (5/5) · 0 failures · PASS WITH WARNINGS
```

Choosing the match type *is* the test design, and it is where most suites
go wrong. Too strict and you fail on a trailing full stop; too loose and
you pass an answer that is wrong by six cents.

| type | use it for | how it bites |
|---|---|---|
| `number` | anything financial or numeric | ignores wording entirely, which is usually what you want |
| `contains` | lists and named entities | passes an answer that also says three wrong things |
| `exact` | canned or templated replies | fails on any rewrite, including a better one |
| `regex` | formats: dates, ids, currency | matches more than you meant unless anchored |
| `judge` | correct in many wordings | costs a model call; evidence, not proof |

**The trap, and it is a quiet one.** Writing `expected:` with no `match:`
silently means `match: judge`. Run that under `--judge none` and the case
is checked by *nothing* while reporting a pass. The tool prints a warning
naming any case in that state. Always write `match:` explicitly; every
case in every file here does.

---

## 3. Where accuracy stops being the answer

**[safety-and-refusals.yaml](safety-and-refusals.yaml)**: the questions
the bot must decline, and the strings it must never emit.

```
accuracy 100% (3/3) · 0 failures · NOT READY
```

Read that line again. **Perfect accuracy, zero failures, and do not
ship.** It is the most useful report in this tour.

Every question the bot chose to answer, it answered correctly. It still
fails, because two cases tagged `critical` broke checks that have nothing
to do with correctness: it answered a compensation question it should
have refused, and it appended a stack trace to an otherwise correct
answer about maintenance windows.

An accuracy-only evaluation scores this bot 100% and ships it.

Open the report and read the Verdict section first. It names both failing
cases and the gate they broke. That is the section you would forward to
someone who has to decide.

Note also that `leak_markers` in the `patterns:` block applies to every
case at once, so you declare a forbidden string once rather than per
question. No judge, no contexts, no model calls.

---

## 4. Grading the citation, not just the answer

**[citations-and-sources.yaml](citations-and-sources.yaml)**: right
answer, right document, real document.

```
accuracy 75% (3/4) · 1 failures · NOT READY
```

The failing case asks the 2026 price of an add-on. The bot answers
fluently, cites a real document, and is a year out of date: it read the
2024 pricing sheet, which is genuinely in the corpus. Two different
checks catch it, the number and the source, and the report tells you
which.

This is the failure mode that makes RAG systems dangerous rather than
merely wrong, because nothing about the answer looks wrong.

`corpus_manifest` is what turns a plausible citation into a checkable
one. List every document the bot may cite, and anything cited that is not
on the list is a phantom the model invented. Omit the manifest and that
check reads `n/a`, because the tool cannot guess what your corpus holds.

---

## 5. Making it fail the build

**[ci-gates.yaml](ci-gates.yaml)**: thresholds, criticals, and the exit
codes CI reads.

```bash
agent-report-card run --tests examples/ci-gates.yaml \
  --endpoint http://localhost:8000 --judge none
echo $?      # 1
```

| exit | meaning | what CI should do |
|---|---|---|
| `0` | PASS or PASS WITH WARNINGS | ship |
| `1` | NOT READY, a gate failed | the bot regressed, block |
| `2` | the tool itself failed | fix the pipeline, not the bot |

The split between 1 and 2 is deliberate and load-bearing. A typo in
`--tests` exits 2, never 1, because exiting 1 would tell CI the bot got
worse and send somebody hunting a regression that does not exist.

Write your gates down even when they match the defaults. The report tells
its reader whether the thresholds came from your file or from this tool's
opinions, and "this tool's opinions" is not something you want to defend
in a release meeting.

### Running it inside an orchestrator

**[kestra/](kestra/)**: the same gate as a task in a [Kestra](https://kestra.io)
flow, with its own walkthrough.

Worth reading even if you use a different orchestrator, because the problem
it solves is not Kestra-specific. Retry policies are not conditional on exit
code — in Kestra, Airflow and most others, a script task either failed or it
did not. Hand all three codes above to a retry policy and exit 1 gets retried
like exit 2: a deterministic regression reproduces three times, costs three
runs, and ends up looking like a flaky test.

The fix is to do the branching before the orchestrator sees it. Fail the task
only for exit 2, and let the verdict leave as data.

---

## 6. Pointing it at your own bot

**[endpoint-shapes.yaml](endpoint-shapes.yaml)**: the only file here you
cannot run against the fixture bot, because it describes a different API
shape.

The default contract needs no `endpoint:` block at all:

```
POST {endpoint}/ask   {"question": "..."}
  -> {"answer": "...", "contexts": [{"text": "...", "source": "doc.md"}]}
```

If your API differs, map it with dot-paths rather than reshaping your
service. `answer: choices.0.message.content` covers any OpenAI-compatible
server. A digit indexes a list and `*` maps the rest of the path over
one.

Secrets go in as `${VAR}` and are read from your environment. An unset
variable fails fast naming the variable and never its value, and the
value is scrubbed from the report, the sidecar, the console and every
error message before the first request leaves. The tool reads no
environment variable you did not write yourself.

Returning `contexts` is optional but unlocks grounding, retrieval
localisation and citation checks. Without it those render `n/a` with the
reason attached, never as passes.

---

## 7. Writing your own

```bash
agent-report-card init my_tests.yaml
```

That writes a commented starter suite. Then work in this order, which is
roughly the order of how much each step is worth:

1. **Ten questions your stakeholders actually ask.** Not edge cases. The
   questions someone would be embarrassed to get wrong in a demo.
2. **Set `match:` on every one of them.** Prefer `number` wherever a
   figure is involved.
3. **Add the refusals.** What must this bot decline? Those are usually
   the questions that end up in an incident review.
4. **Add `leak_markers`** for anything that must never appear: internal
   markers, trace prefixes, key formats.
5. **Tag the unforgivable ones `critical`** and turn on
   `criticals_must_pass`.
6. **Write the gates down**, then wire the exit code into CI.

Then run it every time the prompt, the model, the chunking or the corpus
changes, and commit the report next to the change. A report in git that
someone can diff is worth more than a dashboard nobody opens.

## One more, for reference

**[release_questions.yaml](release_questions.yaml)** is the suite behind
`reports/sample_pass.md` in this repo: the same fixture bot, restricted to
the questions its planted flaws do not touch. Run it to see what a clean
report looks like end to end, and read the committed one to see the same
suite graded with a real judge attached.

```bash
agent-report-card run --tests examples/release_questions.yaml \
  --endpoint http://localhost:8000 --judge none      # exit 0
```

## If you only remember one thing

`report.md` is meant to be read by the person who decides whether to
ship, not by the person who ran it. If a number in there needs you
standing next to it to be understood, that is a bug worth reporting.
