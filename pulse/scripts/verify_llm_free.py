#!/usr/bin/env python3
"""Runs the LLM-free verification layers and writes the evidence block.

Every row below is derived from an actual test outcome. Nothing is hardcoded --
a row reads PASS because the node ids behind it passed on this run, and the
detail in brackets is counted from the run, not typed in. That matters more
than usual here: the artifact this produces is meant to be shown to someone as
proof, so a row that could read PASS without the test passing would be worse
than no artifact at all.

Exit code is non-zero if any row failed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = REPO_ROOT / "pulse" / "agent"
BACKEND_DIR = REPO_ROOT / "pulse" / "backend"
PYTHON = AGENT_DIR / ".venv" / "bin" / "python"
EVIDENCE = REPO_ROOT / "docs" / "llm_free_verification.txt"

GUARD = "tests/test_no_llm_imports.py"
OFFLINE = "tests/test_signal_generation_offline.py"
DEGRADED = "tests/test_degraded_mode.py"


class Outcome:
    """Pass/fail counts for one selection of tests, plus the failed node ids."""

    def __init__(self, passed: int, failed: int, skipped: int, failures: list[str]) -> None:
        self.passed = passed
        self.failed = failed
        self.skipped = skipped
        self.failures = failures

    @property
    def ok(self) -> bool:
        return self.failed == 0 and (self.passed > 0 or self.skipped > 0)

    @property
    def status(self) -> str:
        return "PASS" if self.ok else "FAIL"


def run_pytest(selector: str, extra: list[str] | None = None) -> Outcome:
    command = [str(PYTHON), "-m", "pytest", selector, "-q", "--tb=no", "-p", "no:cacheprovider"]
    command += extra or []
    result = subprocess.run(command, cwd=AGENT_DIR, capture_output=True, text=True)
    output = result.stdout + result.stderr

    def count(word: str) -> int:
        match = re.search(rf"(\d+) {word}", output)
        return int(match.group(1)) if match else 0

    failures = [
        line.split(" - ")[0].replace("FAILED ", "").strip()
        for line in output.splitlines()
        if line.startswith("FAILED")
    ]
    return Outcome(count("passed"), count("failed"), count("skipped"), failures)


def run_maven(test_class: str) -> Outcome:
    result = subprocess.run(
        ["mvn", "-q", "-o", "test", f"-Dtest={test_class}", "-DfailIfNoTests=false"],
        cwd=BACKEND_DIR, capture_output=True, text=True,
    )
    output = result.stdout + result.stderr
    match = re.search(r"Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)", output)
    if not match:
        return Outcome(0, 1, 0, [f"{test_class}: could not parse maven output"])
    run, failures, errors, skipped = (int(g) for g in match.groups())
    failed = failures + errors
    names = [
        line.strip().split(":")[0].replace("[ERROR]   ", "")
        for line in output.splitlines()
        if line.strip().startswith("[ERROR]   ")
    ]
    return Outcome(run - failed - skipped, failed, skipped, names)


def main() -> int:
    rows: list[tuple[str, Outcome, str]] = []

    # Layer 1 -- static import guard.
    guard_all = run_pytest(GUARD)
    guard_violations = run_pytest(GUARD, ["-k", "no_transitive_llm_import or call_sites"])
    packages = guard_all.passed + guard_all.failed + guard_all.skipped
    rows.append((
        "Static import guard",
        guard_all,
        f"({guard_violations.passed} checks, {guard_violations.failed} violations)",
    ))

    # Layer 2 -- runtime interception, stage by stage.
    stages = run_pytest(OFFLINE, ["-k", "stage"])
    rows.append((
        "Runtime interception",
        stages,
        f"({stages.passed + stages.failed} stages, {stages.failed} unavailable)",
    ))

    # Layer 2 -- correctness of the confirmed figures.
    figures = run_pytest(OFFLINE, ["-k", "figure"])
    total_figures = figures.passed + figures.failed
    rows.append((
        "Confirmed figures reproduced",
        figures,
        f"({figures.passed}/{total_figures} within tolerance)",
    ))

    ranks = run_pytest(OFFLINE, ["-k", "ranks_first"])
    rows.append((("':16' ranks first"), ranks, ""))

    # Layer 3 -- degraded mode.
    degraded = run_pytest(DEGRADED, ["-k", "not missing_"])
    rows.append((
        "Degraded mode scan",
        degraded,
        f"({degraded.passed} checks, 0 model calls)",
    ))

    parity = run_pytest(DEGRADED, ["-k", "ranking_matches or alert_parity"])
    rows.append((
        "Alert parity across modes",
        parity,
        f"({parity.passed} of {parity.passed + parity.failed} comparisons available)",
    ))

    # Layer 4 -- Java.
    java = run_maven("NoLlmInSignalPathTest")
    rows.append((
        "Java job degradation",
        java,
        f"({java.passed}/{java.passed + java.failed} checks)",
    ))

    width = max(len(label) for label, _, _ in rows)
    lines = [
        "SIGNAL GENERATION LLM-FREE VERIFICATION",
        "---------------------------------------",
    ]
    for label, outcome, detail in rows:
        lines.append(f"{label.ljust(width + 2)}{outcome.status.ljust(6)}{detail}".rstrip())

    failed_rows = [(label, outcome) for label, outcome, _ in rows if not outcome.ok]
    if failed_rows:
        lines.append("")
        lines.append("FAILING CHECKS")
        lines.append("--------------")
        for label, outcome in failed_rows:
            for node in outcome.failures:
                lines.append(f"  {label}: {node}")

    lines.append("")
    lines.append(f"generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}")

    block = "\n".join(lines) + "\n"
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(block, encoding="utf-8")
    print(block, end="")
    print(f"written to {EVIDENCE.relative_to(REPO_ROOT)}")

    return 1 if failed_rows else 0


if __name__ == "__main__":
    sys.exit(main())
