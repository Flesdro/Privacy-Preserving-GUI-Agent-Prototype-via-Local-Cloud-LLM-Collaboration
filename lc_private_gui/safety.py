"""Safety policy gate for PrivacyPay money-moving actions.

The SafetyPolicy is consulted on-device *before* a Decision is executed.  It
runs on the full UI state (like the local model), so it can read the selected
payee and amount even though those fields are never uploaded to the cloud.

It returns one of three verdicts:

    allow                 - safe (e.g. read-only navigation); execute directly
    require_confirmation  - money-moving but within policy; needs human OK
    block                 - violates a hard rule (unknown payee / over cap)

This is the project's explicit safety mechanism: the agent can perceive,
reason, and act, but it cannot move money without passing these checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from .models import Decision, Task, UIElement


# Click targets whose labels mean "commit a financial action".
AUTHORISE_PHRASES = (
    "transfer now",
    "confirm payment",
    "confirm transfer",
    "authorise",
    "authorize",
    "pay now",
    "send money",
    "submit payment",
)

# Resource-ids / roles that identify the amount entry field.
AMOUNT_FIELD_HINTS = ("amount", "transfer_amount", "payment_amount")

# Resource-ids that carry the selected recipient on a confirm screen.
PAYEE_HINTS = ("selected_payee", "payee", "recipient")


@dataclass
class SafetyVerdict:
    verdict: str            # "allow" | "require_confirmation" | "block"
    reason: str
    money_moving: bool = False
    payee: str | None = None
    amount: float | None = None

    @property
    def allowed(self) -> bool:
        """True if the action may proceed (possibly after confirmation)."""
        return self.verdict != "block"

    @property
    def needs_confirmation(self) -> bool:
        return self.verdict == "require_confirmation"

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "reason": self.reason,
            "money_moving": self.money_moving,
            "payee": self.payee,
            "amount": self.amount,
        }


@dataclass
class SafetyPolicy:
    """Rule-based gate for financial actions.

    payee_allowlist: recipients the agent is permitted to send money to.
    amount_cap:      maximum amount the agent may move without being blocked.
    require_confirmation: when True, every money-moving action that passes the
                          hard checks still needs explicit confirmation.
    """

    payee_allowlist: set[str] = field(
        default_factory=lambda: {
            "Landlord",
            "Electricity Co",
            "City Water",
            "Mom",
            "Dr. Lee",
        }
    )
    amount_cap: float = 2000.0
    require_confirmation: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def review(self, decision: Decision, task: Task) -> SafetyVerdict:
        elements = task.ui_state.by_id()
        target = elements.get(decision.element_id) if decision.element_id else None

        money_moving = self._is_money_moving(decision, target)
        if not money_moving:
            return SafetyVerdict("allow", "non-financial action", money_moving=False)

        payee = self._selected_payee(task)
        amount = self._amount(decision, task)

        # --- Hard blocks take priority over confirmation -------------------
        if payee is not None and not self._payee_allowed(payee):
            return SafetyVerdict(
                "block",
                f"recipient {payee!r} is not in the payee allowlist",
                money_moving=True, payee=payee, amount=amount,
            )
        if amount is not None and amount > self.amount_cap:
            return SafetyVerdict(
                "block",
                f"amount {amount:.2f} exceeds the cap of {self.amount_cap:.2f}",
                money_moving=True, payee=payee, amount=amount,
            )

        # --- Otherwise allowed, but a money move needs confirmation --------
        if self.require_confirmation:
            return SafetyVerdict(
                "require_confirmation",
                "money-moving action requires explicit confirmation",
                money_moving=True, payee=payee, amount=amount,
            )
        return SafetyVerdict(
            "allow", "money-moving action within policy",
            money_moving=True, payee=payee, amount=amount,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_money_moving(self, decision: Decision, target: UIElement | None) -> bool:
        if decision.action == "input":
            # Entering a value into an amount field commits money intent.
            if target is not None and self._looks_like_amount_field(target):
                return True
            return _parse_amount(decision.text) is not None
        if decision.action == "click" and target is not None:
            haystack = target.semantic_text.lower()
            return any(phrase in haystack for phrase in AUTHORISE_PHRASES)
        return False

    def _looks_like_amount_field(self, element: UIElement) -> bool:
        haystack = f"{element.resource_id} {element.role} {element.text}".lower()
        return any(hint in haystack for hint in AMOUNT_FIELD_HINTS)

    def _selected_payee(self, task: Task) -> str | None:
        for element in task.ui_state.elements:
            rid = element.resource_id.lower()
            if any(hint in rid for hint in PAYEE_HINTS):
                return _clean_payee(element.text or element.description)
        return None

    def _amount(self, decision: Decision, task: Task) -> float | None:
        # Prefer the amount being entered; fall back to the on-screen summary.
        from_text = _parse_amount(decision.text)
        if from_text is not None:
            return from_text
        for element in task.ui_state.elements:
            rid = element.resource_id.lower()
            if any(hint in rid for hint in ("transfer_amount", "payment_amount", "amount")):
                parsed = _parse_amount(element.text)
                if parsed is not None:
                    return parsed
        return None

    def _payee_allowed(self, payee: str) -> bool:
        norm = payee.strip().lower()
        return any(norm == allowed.strip().lower() for allowed in self.payee_allowlist)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_amount(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _clean_payee(text: str) -> str:
    # Strip a leading "Recipient:" / "To:" label if present.
    cleaned = re.sub(r"^\s*(recipient|to)\s*:\s*", "", text, flags=re.IGNORECASE)
    return cleaned.strip()
