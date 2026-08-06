"""The judge's own exam.

`judge-check` runs the 30 hand-labeled pairs against the configured judge
and reports agreement, false-pass rate (the dangerous direction),
false-fail rate, and subtle-numeric recall separately. The result is
cached per model and prompt hash, and every report embeds the cached
numbers or says the judge is not calibrated.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from importlib import resources
from pathlib import Path

import yaml

from . import prompts
from .checks_code import PASS, FAIL
from .checks_judge import JudgeClient

CACHE_DIR = Path(os.path.expanduser("~/.agent-report-card"))


def _cache_path(model: str, base_url: str = "") -> Path:
    """Keyed on the model AND the host that served it.

    Two hosts can serve the same model name with different weights or
    quantization, so a name-only key would let a report certify a judge
    that was never examined.
    """
    safe = re.sub(r"[^\w.-]+", "_", model)
    host = hashlib.sha256(base_url.encode("utf-8")).hexdigest()[:8]
    return CACHE_DIR / f"calibration_{safe}_{host}_{prompts.prompt_hash()}.json"


def load_pairs() -> list[dict]:
    text = (resources.files("agent_report_card") / "_data" /
            "judge_calibration.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)["pairs"]


def cached(model: str, base_url: str = "") -> dict | None:
    path = _cache_path(model, base_url)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        # refuse an entry that does not describe the judge being asked about
        if (data.get("model") != model
                or data.get("prompt_hash") != prompts.prompt_hash()):
            return None
        return data
    return None


def run_exam(judge: JudgeClient, progress=None) -> dict:
    pairs = load_pairs()
    start = time.perf_counter()
    agreement = false_pass = false_fail = 0
    subtle_total = subtle_caught = 0
    n_pass_labeled = sum(1 for p in pairs if p["label"] == "pass")
    n_fail_labeled = len(pairs) - n_pass_labeled
    per_pair = []

    for i, pair in enumerate(pairs, 1):
        kind = pair["kind"]
        if kind == "correct":
            prompt = prompts.CORRECT.format(
                question=pair["question"], expected=pair["reference"],
                answer=pair["candidate"])
        elif kind == "grounded":
            prompt = prompts.GROUNDED.format(
                contexts="\n---\n".join(pair["contexts"]),
                answer=pair["candidate"])
        else:
            prompt = prompts.REFUSAL.format(
                question=pair["question"], answer=pair["candidate"])
        status, reason = judge.verdict(prompt)
        judged = {PASS: "pass", FAIL: "fail"}.get(status, "error")
        label = pair["label"]
        ok = judged == label
        agreement += ok
        if label == "fail" and judged == "pass":
            false_pass += 1
        if label == "pass" and judged == "fail":
            false_fail += 1
        if pair["category"] == "subtle_numeric":
            subtle_total += 1
            subtle_caught += (judged == "fail")
        per_pair.append({"id": pair["id"], "category": pair["category"],
                         "label": label, "judged": judged, "reason": reason})
        if progress:
            progress(i, len(pairs), pair["id"], judged, label)

    result = {
        "model": judge.model,
        "prompt_version": prompts.PROMPT_VERSION,
        "prompt_hash": prompts.prompt_hash(),
        "n": len(pairs),
        "n_pass_labeled": n_pass_labeled,
        "n_fail_labeled": n_fail_labeled,
        "agreement": agreement,
        "false_pass": false_pass,
        "false_fail": false_fail,
        "subtle_total": subtle_total,
        "subtle_caught": subtle_caught,
        "errors": sum(1 for p in per_pair if p["judged"] == "error"),
        "wall_clock_s": round(time.perf_counter() - start, 1),
        "pairs": per_pair,
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    result["base_url"] = judge.base_url
    _cache_path(judge.model, judge.base_url).write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def unreliable(calibration: dict | None) -> bool:
    """Below 80% agreement the verdict line carries the warning."""
    if not calibration:
        return False  # uncalibrated is disclosed, not punished
    return calibration["agreement"] / calibration["n"] < 0.80
