#!/usr/bin/env python3
"""Run the golden questions against insight chat.

Two assertions per question, and the second is the point:

  1. **Intent.** The router classifies it as the golden file says, with the
     slots the golden file states. A wrong intent is a confident answer to a
     question nobody asked.
  2. **Grounding.** Every number in the rendered answer -- prose and evidence
     rows alike -- appears in the source packet. This is the same check
     app/agent/validator.py applies to LLM narrative, applied here to prose we
     wrote ourselves, because a template with a stray literal in it is exactly
     as wrong as a hallucination and much easier to miss.

Runs with the model off by default, which is the mode that must always work:
chat answers all eight intents from templates whether or not a model is
reachable. ``--llm`` routes through the model instead and checks it agrees.

    python eval/run_eval.py                 # rule router, the CI default
    python eval/run_eval.py --llm           # model router
    python eval/run_eval.py -v              # print every answer

Exit code is 0 only if every question passes.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

GOLDEN_PATH = Path(__file__).with_name("golden_questions.yaml")

#: Numbers a question's own phrasing may put into an answer that echoes it, and
#: figures that are structural rather than claims about the data. Empty on
#: purpose: nothing is exempt today, and the constant exists so that adding an
#: exemption is a visible decision rather than a quiet edit to the checker.
ALLOWED_UNGROUNDED: set[float] = set()


def _load_golden() -> dict[str, Any]:
    with open(GOLDEN_PATH) as handle:
        return yaml.safe_load(handle)


def _answer_numbers(answer: dict[str, Any], validator) -> set[float]:
    """Every number the user is shown for one answer.

    The table is excluded: its rows are the warehouse's own, returned by the
    whitelisted row query, and they are not claims the answer makes about the
    finding. Everything else -- prose, evidence labels, evidence values -- is.
    """
    numbers = validator.extract_numbers(answer.get("answer") or "")
    for row in answer.get("evidence") or []:
        numbers |= validator.extract_numbers(str(row.get("value", "")))
        numbers |= validator.extract_numbers(str(row.get("label", "")))
    return numbers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", action="store_true", help="route through the model instead of the rules")
    parser.add_argument("-v", "--verbose", action="store_true", help="print every answer")
    args = parser.parse_args()

    if not args.llm:
        # Set before app.config is imported anywhere: Settings reads this at
        # construction and is lru_cached for the process.
        os.environ["PULSE_LLM_ENABLED"] = "false"

    from app.agent import validator
    from app.chat import service
    from app.detect import signals
    from app.llm import context

    golden = _load_golden()
    tenant, insight_id = golden["tenant"], golden["insight"]

    packet = next(
        (i for i in signals.detect_tenant(tenant) if i["insight_id"] == insight_id), None
    )
    if packet is None:
        print(f"FATAL: {insight_id!r} does not currently fire for tenant {tenant!r}. "
              "The golden set is written against a live insight; if detection no longer "
              "produces it, the golden set is what needs updating.")
        return 2

    insight = service.resolve_insight(insight_id, tenant, packet)
    grounded = validator.collect_input_numbers(insight)

    questions = golden["questions"]
    failures: list[str] = []
    failed_questions: set[str] = set()
    routed_by = {"rules": 0, "model": 0, "model-then-rules": 0}

    for entry in questions:
        question = entry["q"]
        expected = entry["expect_intent"]
        # The model router is refused without a tenant in context -- every model
        # call is metered and an unattributable one is a bug (app/llm/client.py).
        # In the default rules mode this binds nothing that is ever read.
        with context.bind(tenant_id=tenant, insight_id=insight_id):
            result = service.answer(insight, question)
        routed_by[result["routing"]["source"]] = routed_by.get(result["routing"]["source"], 0) + 1

        if result["intent"] != expected:
            failed_questions.add(question)
            failures.append(
                f"INTENT  {question!r}\n"
                f"         expected {expected}, got {result['intent']} "
                f"(confidence {result['confidence']}, via {result['routing']['source']})"
            )

        for slot, want in (entry.get("expect_slots") or {}).items():
            got = result["slots"].get(slot)
            if got != want:
                failed_questions.add(question)
                failures.append(f"SLOT    {question!r}\n         {slot}: expected {want!r}, got {got!r}")

        ungrounded = {
            number
            for number in _answer_numbers(result, validator)
            if number not in ALLOWED_UNGROUNDED
            and not any(abs(number - g) < 1e-6 for g in grounded)
        }
        if ungrounded:
            failed_questions.add(question)
            failures.append(
                f"NUMBER  {question!r}\n"
                f"         answer cites numbers absent from the packet: {sorted(ungrounded)}\n"
                f"         answer: {result['answer'][:300]}"
            )

        if args.verbose:
            print(f"\n--- {question}\n[{result['intent']} {result['confidence']}] {result['answer']}")
            for row in result["evidence"]:
                print(f"    {row['label']}: {row['value']}   <- {row['source_field']}")

    print()
    print(f"{len(questions) - len(failed_questions)}/{len(questions)} questions passed "
          f"({'model' if args.llm else 'rules'} router)")
    print(f"routed by: {', '.join(f'{k}={v}' for k, v in routed_by.items() if v)}")

    if failures:
        print("\n" + "\n\n".join(failures))
        return 1
    print("every answer's numbers trace back to the packet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
