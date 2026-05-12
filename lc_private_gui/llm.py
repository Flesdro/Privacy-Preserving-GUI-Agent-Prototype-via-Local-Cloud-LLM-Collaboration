from __future__ import annotations

from dataclasses import dataclass

from .models import Decision, UIBlock


@dataclass(frozen=True)
class RankedBlock:
    block: UIBlock
    score: float


class HeuristicLocalLLM:
    """Offline local LLM stand-in for reproducible demos."""

    def generate_subtask(self, task: str, history: list[Decision], block: UIBlock) -> str:
        task_l = task.lower()
        block_l = block.text.lower()
        if "search" in task_l and ("search" in block_l or "url" in block_l):
            return "Use the search field to enter the requested query."
        if any(word in task_l for word in ["refresh", "reload"]) and any(
            word in block_l for word in ["refresh", "reload", "刷新"]
        ):
            return "Refresh the visible list."
        if "scan" in task_l and any(
            word in block_l for word in ["scan", "扫描", "扫一扫"]
        ):
            return "Scan using the visible scan control."
        if "alarm" in task_l and ("alarm" in block_l or "time" in block_l or "add" in block_l):
            return "Create or configure an alarm."
        if "contact" in task_l and ("phone" in block_l or "contact" in block_l or "name" in block_l):
            return "Edit the contact details requested by the user."
        if any(word in task_l for word in ["email", "mail"]) and any(
            word in block_l for word in ["compose", "email", "mail", "recipient", "send"]
        ):
            return "Create or send the requested email."
        if any(word in task_l for word in ["message", "text"]) and any(
            word in block_l for word in ["message", "chat", "send", "compose"]
        ):
            return "Send or edit the requested message."
        if any(word in task_l for word in ["map", "navigate", "route", "directions"]) and any(
            word in block_l for word in ["map", "search", "destination", "directions"]
        ):
            return "Use the map search or directions control."
        if any(word in task_l for word in ["buy", "order", "checkout", "cart"]) and any(
            word in block_l for word in ["buy", "order", "checkout", "cart"]
        ):
            return "Continue the shopping checkout flow."
        if any(word in task_l for word in ["pay", "transfer", "amount"]) and any(
            word in block_l for word in ["pay", "transfer", "amount", "send money"]
        ):
            return "Enter or confirm the payment details."
        if any(word in task_l for word in ["wifi", "bluetooth", "settings"]) and any(
            word in block_l for word in ["wifi", "bluetooth", "settings", "toggle"]
        ):
            return "Open or change the requested setting."
        if any(word in task_l for word in ["note", "todo", "task"]) and any(
            word in block_l for word in ["note", "todo", "task", "add"]
        ):
            return "Create or update the requested note or task."
        if "calendar" in task_l or "event" in task_l:
            if "event" in block_l or "calendar" in block_l or "add" in block_l:
                return "Create or edit a calendar event."
        if any(word in block_l for word in task_l.split()):
            return "Interact with this block because it overlaps with the user task."
        return "This block may be unrelated to the current task."

    def rank_blocks(self, task: str, subtask: str, blocks: list[UIBlock]) -> list[RankedBlock]:
        query_terms = set(_terms(task + " " + subtask))
        task_l = task.lower()
        ranked: list[RankedBlock] = []
        for block in blocks:
            block_terms = set(_terms(block.text))
            overlap = len(query_terms & block_terms)
            affordance_bonus = sum(1 for e in block.elements if e.clickable or e.editable) * 0.15
            sensitive_penalty = sum(1 for e in block.elements if e.sensitive) * 0.25
            intent_bonus = self._intent_bonus(task_l, block.text.lower())
            score = overlap + affordance_bonus + intent_bonus - sensitive_penalty
            ranked.append(RankedBlock(block=block, score=max(score, 0.01)))
        total = sum(item.score for item in ranked)
        normalized = [RankedBlock(item.block, item.score / total) for item in ranked]
        return sorted(normalized, key=lambda item: item.score, reverse=True)

    def _intent_bonus(self, task: str, block_text: str) -> float:
        if ("create" in task or "add" in task) and any(word in block_text for word in ["add", "new", "create"]):
            return 3.0
        if "search" in task and any(word in block_text for word in ["search", "url"]):
            return 3.0
        if any(word in task for word in ["refresh", "reload"]) and any(
            word in block_text for word in ["refresh", "reload", "刷新"]
        ):
            return 4.0
        if "scan" in task and any(
            word in block_text for word in ["scan", "扫描", "扫一扫"]
        ):
            return 4.0
        if "phone" in task and "phone" in block_text:
            return 3.0
        if any(word in task for word in ["email", "mail"]) and any(
            word in block_text for word in ["compose", "email", "recipient", "send"]
        ):
            return 3.0
        if any(word in task for word in ["message", "text"]) and any(
            word in block_text for word in ["message", "chat", "send"]
        ):
            return 3.0
        if any(word in task for word in ["map", "navigate", "route", "directions"]) and any(
            word in block_text for word in ["map", "search", "destination", "directions"]
        ):
            return 3.0
        if any(word in task for word in ["buy", "order", "checkout", "cart"]) and any(
            word in block_text for word in ["buy", "order", "checkout", "cart"]
        ):
            return 3.0
        if any(word in task for word in ["pay", "transfer", "amount"]) and any(
            word in block_text for word in ["pay", "transfer", "amount", "send money"]
        ):
            return 3.0
        if any(word in task for word in ["wifi", "bluetooth", "settings"]) and any(
            word in block_text for word in ["wifi", "bluetooth", "settings", "toggle"]
        ):
            return 3.0
        if any(word in task for word in ["note", "todo", "task"]) and any(
            word in block_text for word in ["note", "todo", "task", "add"]
        ):
            return 3.0
        return 0.0


class HeuristicCloudLLM:
    """Offline cloud LLM stand-in. It only sees candidates and uploaded blocks."""

    def confirm_subtask(self, task: str, history: list[Decision], candidates: list[str]) -> str:
        useful = [candidate for candidate in candidates if "unrelated" not in candidate.lower()]
        if useful:
            return useful[0]
        return f"Make progress on: {task}"

    def decide(self, task: str, history: list[Decision], uploaded_blocks: list[UIBlock]) -> Decision | None:
        task_l = task.lower()
        elements = [element for block in uploaded_blocks for element in block.elements]
        if "search" in task_l:
            target = _first(elements, editable=True, keywords=["search", "url"])
            if target:
                query = _quoted_text(task) or task.split("search", 1)[-1].strip()
                return Decision("input", target.id, text=query, reason="search field is visible")
        if any(word in task_l for word in ["refresh", "reload"]):
            target = _first(elements, clickable=True, keywords=["refresh", "reload", "刷新"])
            if target:
                return Decision("click", target.id, reason="refresh control is visible")
        if "alarm" in task_l:
            keywords = ["add", "new", "create"] if any(word in task_l for word in ["add", "new", "create"]) else [
                "alarm",
                "time",
            ]
            target = _first(elements, clickable=True, keywords=keywords)
            if target:
                return Decision("click", target.id, reason="alarm control is visible")
        if "contact" in task_l:
            keywords = ["phone"] if "phone" in task_l or any(char.isdigit() for char in task) else [
                "name",
                "contact",
            ]
            target = _first(elements, editable=True, keywords=keywords)
            if target:
                return Decision("input", target.id, text=_phone_text(task), reason="contact field is visible")
        if "calendar" in task_l or "event" in task_l:
            target = _first(elements, clickable=True, keywords=["add", "new", "create"])
            if target:
                return Decision("click", target.id, reason="calendar event control is visible")
        if any(word in task_l for word in ["email", "mail"]):
            if "compose" in task_l or "send" in task_l:
                target = _first(elements, clickable=True, keywords=["compose", "new", "send"])
                if target:
                    return Decision("click", target.id, reason="email control is visible")
            target = _first(elements, editable=True, keywords=["recipient", "email", "to"])
            if target:
                return Decision("input", target.id, text=_email_text(task), reason="email field is visible")
        if any(word in task_l for word in ["message", "text"]):
            target = _first(elements, editable=True, keywords=["message", "chat", "compose"])
            if target:
                return Decision("input", target.id, text=_quoted_text(task), reason="message field is visible")
            target = _first(elements, clickable=True, keywords=["send", "compose", "new"])
            if target:
                return Decision("click", target.id, reason="message control is visible")
        if any(word in task_l for word in ["map", "navigate", "route", "directions"]):
            target = _first(elements, editable=True, keywords=["search", "destination", "directions"])
            if target:
                return Decision("input", target.id, text=_quoted_text(task), reason="map destination field is visible")
            target = _first(elements, clickable=True, keywords=["directions", "navigate", "route"])
            if target:
                return Decision("click", target.id, reason="map navigation control is visible")
        if any(word in task_l for word in ["buy", "order", "checkout", "cart"]):
            target = _first(elements, clickable=True, keywords=["checkout", "buy", "order", "cart"])
            if target:
                return Decision("click", target.id, reason="shopping checkout control is visible")
        if any(word in task_l for word in ["pay", "transfer", "amount"]):
            target = _first(elements, editable=True, keywords=["amount", "pay", "transfer"])
            if target:
                return Decision("input", target.id, text=_money_text(task), reason="payment amount field is visible")
            target = _first(elements, clickable=True, keywords=["pay", "transfer", "send money", "confirm"])
            if target:
                return Decision("click", target.id, reason="payment control is visible")
        if any(word in task_l for word in ["wifi", "bluetooth", "settings"]):
            target = _first(elements, clickable=True, keywords=["wifi", "bluetooth", "toggle", "settings"])
            if target:
                return Decision("click", target.id, reason="settings control is visible")
        if any(word in task_l for word in ["note", "todo", "task"]):
            target = _first(elements, editable=True, keywords=["note", "todo", "task", "title"])
            if target:
                return Decision("input", target.id, text=_quoted_text(task), reason="note field is visible")
            target = _first(elements, clickable=True, keywords=["add", "new", "task", "note"])
            if target:
                return Decision("click", target.id, reason="note or task control is visible")
        target = next((element for element in elements if element.clickable or element.editable), None)
        if target:
            return Decision("click" if target.clickable else "input", target.id, reason="fallback visible control")
        return None


def _terms(text: str) -> list[str]:
    return [token.strip(".,:;!?()[]'\"").lower() for token in text.split() if len(token.strip()) > 1]


def _first(elements, *, editable=False, clickable=False, keywords: list[str]):
    for element in elements:
        if editable and not element.editable:
            continue
        if clickable and not element.clickable:
            continue
        haystack = element.semantic_text.lower()
        if any(keyword in haystack for keyword in keywords):
            return element
    return None


def _quoted_text(task: str) -> str | None:
    for quote in ["'", '"']:
        if quote in task:
            parts = task.split(quote)
            if len(parts) >= 3:
                return parts[1]
    return None


def _phone_text(task: str) -> str:
    digits = "".join(char for char in task if char.isdigit() or char in "+- ")
    return digits.strip() or "[UPDATED_VALUE]"


def _email_text(task: str) -> str:
    for token in task.split():
        if "@" in token:
            return token.strip(".,;:()[]'\"")
    return "[EMAIL]"


def _money_text(task: str) -> str:
    amount = "".join(char for char in task if char.isdigit() or char in "$.,")
    return amount.strip(".,") or "[AMOUNT]"
