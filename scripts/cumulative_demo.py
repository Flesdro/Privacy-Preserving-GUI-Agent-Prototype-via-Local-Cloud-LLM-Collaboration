"""Demonstrate cumulative multi-step exposure (E).

Drives a 3-screen bill-pay flow (select biller -> enter amount -> confirm)
through the MultiStepRunner with an observe() that advances screens, and prints
cumulative unique exposure vs the per-step average for collaborative and
cloud-only modes. Cumulative exposure shows how leakage accumulates across a
flow even when each step uploads little.

Run from the prototype root:
    python3 scripts/cumulative_demo.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lc_private_gui.agent import CloudOnlyAgent, CollaborativeAgent
from lc_private_gui.memory import EpisodicMemory
from lc_private_gui.models import GUIState, Task, UIElement
from lc_private_gui.runner import MultiStepRunner

SCREEN = [0, 0, 1080, 2400]


def el(eid, parent, role, *, text="", desc="", bounds, clickable=False,
       editable=False, sensitive=False):
    return UIElement(id=eid, parent=parent, role=role, text=text, description=desc,
                     resource_id=eid, bounds=bounds, clickable=clickable,
                     editable=editable, sensitive=sensitive)


def screen(screen_id, *, pii, target):
    """Build one banking screen with PII distractors and a target control."""
    elements = [
        el("root", None, "FrameLayout", bounds=SCREEN),
        el("content", "root", "LinearLayout", bounds=[0, 280, 1080, 1400]),
        el("action_area", "root", "LinearLayout", bounds=[0, 1500, 1080, 1900]),
        el("nav_bar", "root", "LinearLayout", bounds=[0, 2100, 1080, 2400]),
        el("nav_home", "nav_bar", "button", desc="Home", bounds=[40, 2140, 360, 2360], clickable=True),
    ]
    for i, (eid, text) in enumerate(pii):
        top = 300 + i * 180
        elements.append(el(eid, "content", "text", text=text, desc=text,
                           bounds=[40, top, 1040, top + 150], sensitive=True))
    elements.append(el(target["id"], "action_area", target.get("role", "button"),
                       text=target["text"], desc=target["text"],
                       bounds=[40, 1540, 1040, 1860],
                       clickable=target.get("clickable", True),
                       editable=target.get("editable", False)))
    return GUIState(id=screen_id, app="Bank", root_id="root", elements=elements)


# Three distinct screens of a single bill-pay flow.
S1 = screen("pay_s1",
            pii=[("p1", "Everyday •••• 4821  $3,204.55"),
                 ("p2", "Savings •••• 7790  $18,450.00")],
            target={"id": "biller_elec", "text": "Electricity Co"})
S2 = screen("pay_s2",
            pii=[("p3", "-$1,200.00 Rent to Landlord"),
                 ("p4", "Payee: Dr. Lee •••• 3321")],
            target={"id": "amount_field", "text": "Amount", "role": "input",
                    "clickable": True, "editable": True})
S3 = screen("pay_s3",
            pii=[("p5", "Recipient: Electricity Co"),
                 ("p6", "Pay from Everyday •••• 4821")],
            target={"id": "confirm_payment_btn", "text": "Confirm payment"})

INSTRUCTION = "Pay the electricity bill of 85.50"


def run(agent_cls):
    tmp = Path(tempfile.mkdtemp())
    runner = MultiStepRunner(
        agent_cls(), memory=EpisodicMemory(memory_dir=tmp / "ep"),
        max_steps=3, run_root=tmp / "runs",
    )
    screens = iter([S2, S3, S3])  # observed after steps 1, 2, 3
    task = Task(id="pay_flow", instruction=INSTRUCTION, ui_state=S1, expected_action={"action": "click"})

    def observe():
        return Task(id="pay_flow", instruction=INSTRUCTION,
                    ui_state=next(screens), expected_action={"action": "click"})

    # dry_run=False so the loop advances screens via observe(); a no-op executor
    # keeps it safe (no real device, no SafetyPolicy needed for this metric demo).
    return runner.run(task, executor=lambda d, t: {"status": "noop"},
                      dry_run=False, observe=observe)


def main():
    print(f"Flow: {INSTRUCTION!r} over 3 screens\n")
    print(f"{'mode':<16} {'per-step avg':>14} {'cumulative':>12} "
          f"{'per-step sens':>14} {'cum sens':>10}")
    print("-" * 70)
    for name, cls in [("collaborative", CollaborativeAgent), ("cloud_only", CloudOnlyAgent)]:
        t = run(cls)
        print(f"{name:<16} {t.avg_exposure_rate:>13.2%} {t.cumulative_exposure_rate:>12.2%} "
              f"{t.avg_sensitive_exposure_rate:>13.2%} {t.cumulative_sensitive_exposure_rate:>10.2%}")


if __name__ == "__main__":
    main()
