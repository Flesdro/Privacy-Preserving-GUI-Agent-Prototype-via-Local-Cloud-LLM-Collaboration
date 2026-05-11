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
        if "alarm" in task_l and ("alarm" in block_l or "time" in block_l or "add" in block_l):
            return "Create or configure an alarm."
        if "contact" in task_l and ("phone" in block_l or "contact" in block_l or "name" in block_l):
            return "Edit the contact details requested by the user."
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
        if "phone" in task and "phone" in block_text:
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
        if "alarm" in task_l:
            target = _first(elements, clickable=True, keywords=["add", "alarm", "time"])
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
