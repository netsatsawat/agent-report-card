PY := .venv/bin/python
ARC := .venv/bin/agent-report-card

.PHONY: venv test demo demo-report judged-report calibrate checks-md verify

venv:
	python3.11 -m venv .venv && .venv/bin/pip install -e .

test:
	$(PY) -m unittest discover tests

demo:
	$(ARC) demo --judge none

# regenerate the committed deterministic golden report
demo-report:
	@tmp=$$(mktemp -d) && cd $$tmp && \
	$(CURDIR)/$(ARC) demo --judge none >/dev/null && \
	cp report.md $(CURDIR)/reports/demo_report.md && \
	echo "reports/demo_report.md regenerated"

# regenerate the committed judged sample report (needs Ollama)
judged-report:
	@tmp=$$(mktemp -d) && cd $$tmp && \
	$(CURDIR)/$(ARC) demo >/dev/null && \
	cp report.md $(CURDIR)/reports/demo_report_judged.md && \
	echo "reports/demo_report_judged.md regenerated"

calibrate:
	$(ARC) judge-check

checks-md:
	$(ARC) checks --md > CHECKS.md

verify: test
	$(PY) scripts/verify_readme_claims.py
