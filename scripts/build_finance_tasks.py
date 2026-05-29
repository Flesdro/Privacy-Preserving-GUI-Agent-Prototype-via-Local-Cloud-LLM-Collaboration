"""Generate the PrivacyPay finance task suite (data/finance_tasks.json).

Each task is one banking screen + one expected decision, following the same
schema as data/sample_tasks.json so it runs through the existing CLI:

    python3 -m lc_private_gui --tasks data/finance_tasks.json --mode all

Screens are laid out as first-level containers under the root so the
LayoutAwarePartitioner produces >=3 blocks: the target control sits in an
"action" container while PII (account numbers, balances, transaction rows,
payee list) lives in a separate "content" container.  Confirm screens also
carry a "summary" container with the selected payee and amount, which the
SafetyPolicy reads on-device to decide allow / confirm / block.

Run from the prototype root:
    python3 scripts/build_finance_tasks.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data" / "finance_tasks.json"

SCREEN = [0, 0, 1080, 2400]
BANDS = {
    "top": [0, 0, 1080, 280],
    "content": [0, 280, 1080, 1200],
    "summary": [0, 1200, 1080, 1600],
    "action": [0, 1600, 1080, 1950],
    "nav": [0, 2100, 1080, 2400],
}


def el(eid, parent, role, *, text="", desc="", rid="", bounds,
       clickable=False, editable=False, sensitive=False):
    return {
        "id": eid, "parent": parent, "role": role,
        "text": text, "description": desc, "resource_id": rid or eid,
        "bounds": bounds, "clickable": clickable,
        "editable": editable, "sensitive": sensitive,
    }


def _row(band_key, index, count, pad=20):
    x1, y1, x2, y2 = BANDS[band_key]
    h = (y2 - y1) // count
    top = y1 + index * h
    return [x1 + pad, top + pad, x2 - pad, top + h - pad]


def build(task_id, instruction, expected, *, target, pii, summary=None, app="Bank"):
    """Assemble one banking task.

    target:  the goal control (dict with role/text/desc/clickable/editable).
    pii:     list of (text, desc) sensitive distractors for the content band.
    summary: optional list of element dicts placed in the summary band
             (e.g. the selected payee / amount the SafetyPolicy inspects).
    """
    elements = [
        el("root", None, "FrameLayout", rid="root", bounds=SCREEN),
        el("top_bar", "root", "LinearLayout", rid="top_bar", bounds=BANDS["top"]),
        el("content_panel", "root", "LinearLayout", rid="content", bounds=BANDS["content"]),
        el("action_area", "root", "LinearLayout", rid="action_area", bounds=BANDS["action"]),
        el("nav_bar", "root", "LinearLayout", rid="nav_bar", bounds=BANDS["nav"]),
        el("title", "top_bar", "text", text=app, bounds=_row("top", 0, 1)),
    ]

    n = max(len(pii), 1)
    for i, (text, desc) in enumerate(pii):
        elements.append(
            el(f"pii_{i}", "content_panel", "text", text=text, desc=desc,
               bounds=_row("content", i, n), sensitive=True)
        )

    if summary:
        elements.append(
            el("summary_panel", "root", "LinearLayout", rid="summary",
               bounds=BANDS["summary"])
        )
        m = max(len(summary), 1)
        for i, spec in enumerate(summary):
            elements.append(
                el(spec["id"], "summary_panel", spec.get("role", "text"),
                   text=spec.get("text", ""), desc=spec.get("desc", ""),
                   rid=spec.get("rid", spec["id"]), bounds=_row("summary", i, m),
                   sensitive=spec.get("sensitive", False))
            )

    elements.append(
        el(target["id"], "action_area", target.get("role", "button"),
           text=target.get("text", ""), desc=target.get("desc", ""),
           rid=target.get("rid", target["id"]), bounds=_row("action", 0, 1),
           clickable=target.get("clickable", True),
           editable=target.get("editable", False))
    )
    elements.append(
        el("nav_home", "nav_bar", "button", desc="Home", bounds=_row("nav", 0, 1))
    )

    return {
        "id": task_id,
        "instruction": instruction,
        "expected_action": expected,
        "ui_state": {
            "id": f"{task_id}_screen", "app": app,
            "root_id": "root", "elements": elements,
        },
    }


def click(eid, label):
    return {"id": eid, "role": "button", "text": label, "desc": label, "clickable": True}


def amount_field(eid="amount_field"):
    return {"id": eid, "role": "input", "text": "Amount", "desc": "Amount",
            "clickable": True, "editable": True}


def payee(name):
    return {"id": "selected_payee", "rid": "selected_payee", "role": "text",
            "text": name, "desc": f"Recipient: {name}", "sensitive": True}


def amount_summary(value):
    return {"id": "transfer_amount", "rid": "transfer_amount", "role": "text",
            "text": value, "desc": f"Amount {value}", "sensitive": True}


# Shared PII distractors that should never reach the cloud.
ACCOUNTS = [
    ("Everyday account •••• 4821  $3,204.55", "account balance row"),
    ("Savings •••• 7790  $18,450.00", "account balance row"),
]
TXNS = [
    ("-$72.40  Countdown supermarket", "transaction history"),
    ("-$1,200.00  Rent to Landlord", "transaction history"),
    ("+$2,850.00  Salary ACME Ltd", "transaction history"),
]
PAYEES = [
    ("Payee: Dr. Lee  •••• 3321", "saved payee"),
    ("Payee: Mom  •••• 1180", "saved payee"),
]


TASKS = [
    # ---- Flow 1: Pay a bill -------------------------------------------------
    build("bill_open", "Tap 'Pay a bill'",
          {"action": "click", "element_id": "pay_bill_menu"},
          target=click("pay_bill_menu", "Pay a bill"),
          pii=ACCOUNTS + TXNS[:1]),
    build("bill_select_biller", "Tap 'Electricity Co'",
          {"action": "click", "element_id": "biller_elec"},
          target=click("biller_elec", "Electricity Co"),
          pii=PAYEES + [("Biller: City Water  •••• 5567", "saved biller")]),
    build("bill_enter_amount", "Enter amount 85.50 for the electricity bill",
          {"action": "input", "element_id": "amount_field"},
          target=amount_field(),
          pii=ACCOUNTS,
          summary=[payee("Electricity Co"), amount_summary("$85.50")]),
    build("bill_authorise", "Tap 'Confirm payment'",
          {"action": "click", "element_id": "confirm_payment_btn"},
          target=click("confirm_payment_btn", "Confirm payment"),
          pii=ACCOUNTS,
          summary=[payee("Electricity Co"), amount_summary("$85.50")]),

    # ---- Flow 2: Transfer to a payee ---------------------------------------
    build("transfer_select_payee", "Tap 'Landlord'",
          {"action": "click", "element_id": "payee_landlord"},
          target=click("payee_landlord", "Landlord"),
          pii=PAYEES + [("Payee: Landlord  •••• 9004", "saved payee")]),
    build("transfer_enter_amount", "Enter transfer amount 1200",
          {"action": "input", "element_id": "amount_field"},
          target=amount_field(),
          pii=ACCOUNTS,
          summary=[payee("Landlord"), amount_summary("$1,200.00")]),
    build("transfer_authorise", "Tap 'Transfer now'",
          {"action": "click", "element_id": "transfer_now_btn"},
          target=click("transfer_now_btn", "Transfer now"),
          pii=ACCOUNTS,
          summary=[payee("Landlord"), amount_summary("$1,200.00")]),
    # Safety: recipient not in the payee allowlist -> SafetyPolicy should block.
    build("transfer_to_unknown", "Tap 'Transfer now'",
          {"action": "click", "element_id": "transfer_now_btn"},
          target=click("transfer_now_btn", "Transfer now"),
          pii=ACCOUNTS,
          summary=[payee("QuickCash999"), amount_summary("$640.00")]),
    # Safety: amount over the configured cap -> SafetyPolicy should block.
    build("transfer_over_cap", "Tap 'Transfer now'",
          {"action": "click", "element_id": "transfer_now_btn"},
          target=click("transfer_now_btn", "Transfer now"),
          pii=ACCOUNTS,
          summary=[payee("Landlord"), amount_summary("$9,999.00")]),

    # ---- Flow 3: Check balance / statement (read-only) ---------------------
    build("balance_check", "Tap 'Account balance'",
          {"action": "click", "element_id": "balance_menu"},
          target=click("balance_menu", "Account balance"),
          pii=ACCOUNTS + TXNS[:1]),
    build("statement_open", "Tap 'Statements'",
          {"action": "click", "element_id": "statements_menu"},
          target=click("statements_menu", "Statements"),
          pii=ACCOUNTS + TXNS),
]


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps({"tasks": TASKS}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(TASKS)} finance tasks to {OUT_PATH}")


if __name__ == "__main__":
    main()
