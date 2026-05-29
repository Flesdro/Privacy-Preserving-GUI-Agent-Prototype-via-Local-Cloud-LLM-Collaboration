"""Demonstrate the PrivacyPay SafetyPolicy without a device.

For each finance task, the collaborative agent makes a decision and the
SafetyPolicy reviews it on-device, printing allow / require_confirmation /
block with the reason.  This shows the safety gate independently of ADB.

Run from the prototype root:
    python3 scripts/safety_demo.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lc_private_gui.agent import CollaborativeAgent
from lc_private_gui.parser import load_tasks
from lc_private_gui.safety import SafetyPolicy

FINANCE_TASKS = ROOT / "data" / "finance_tasks.json"

ICON = {"allow": "  ALLOW ", "require_confirmation": "CONFIRM", "block": "  BLOCK "}


def main():
    tasks = load_tasks(FINANCE_TASKS)
    agent = CollaborativeAgent()
    policy = SafetyPolicy()

    print(f"SafetyPolicy: amount_cap={policy.amount_cap:.2f} "
          f"allowlist={sorted(policy.payee_allowlist)}\n")
    header = f"{'task':<22} {'decision':<28} {'verdict':<9} reason"
    print(header)
    print("-" * len(header))

    summary = {"allow": 0, "require_confirmation": 0, "block": 0}
    rows = []
    for task in tasks:
        result = agent.run(task)
        decision = result.decision
        verdict = policy.review(decision, task)
        summary[verdict.verdict] += 1
        dec_str = f"{decision.action}:{decision.element_id}"
        print(f"{task.id:<22} {dec_str:<28} "
              f"{ICON[verdict.verdict]:<9} {verdict.reason}")
        rows.append({
            "task_id": task.id,
            "decision": {"action": decision.action, "element_id": decision.element_id,
                         "text": decision.text},
            "safety": verdict.to_dict(),
        })

    print(f"\nverdicts: {summary['allow']} allow, "
          f"{summary['require_confirmation']} require_confirmation, "
          f"{summary['block']} block")

    out = ROOT / "logs" / "safety_demo.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"detail written to {out}")


if __name__ == "__main__":
    main()
