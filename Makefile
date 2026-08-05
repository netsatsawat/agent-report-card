PY := .venv/bin/python
ARC := .venv/bin/agent-report-card

.PHONY: venv test demo gallery calibrate checks-md verify

venv:
	python3.11 -m venv .venv && .venv/bin/pip install -e .

test:
	$(PY) -m unittest discover tests

demo:
	$(ARC) demo --judge none

# regenerate every committed gallery report plus its terminal log
# (the two judged runs need Ollama with the default judge model)
gallery:
	$(PY) scripts/make_gallery.py

calibrate:
	$(ARC) judge-check

checks-md:
	$(ARC) checks --md > CHECKS.md

verify: test
	$(PY) scripts/verify_readme_claims.py
