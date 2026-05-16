"""ReAct (Reasoning + Acting) prompt builder and response parser.

The cloud LLM is asked to output a ``thought`` field before every action.
This makes the agent's step-by-step reasoning visible and feeds into the
thought_history that is passed to subsequent steps.
"""
from __future__ import annotations

from typing import Any

from .models import Decision, ThoughtAction, UIBlock


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

def build_react_system_prompt(role: str = "cloud") -> str:
    if role == "cloud":
        return (
            "You are the cloud-side reasoning module in a privacy-preserving mobile agent. "
            "You only see uploaded UI blocks selected by the local device — never the full screen. "
            "At each step, first think step by step about the current state and what action to take, "
            "then choose one action. Never invent element ids not present in the uploaded blocks. "
            "Return strict JSON with exactly these keys: thought, action, element_id, text, reason. "
            "Use null for element_id only when action is scroll, back, or finish."
        )
    return (
        "You are the local-only reasoning module running on the user's device. "
        "You can inspect all provided UI blocks. "
        "First think step by step about the current state and what to do next, "
        "then choose one action. Never invent element ids. "
        "Return strict JSON with exactly these keys: thought, action, element_id, text, reason."
    )


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_react_prompt(
    task: str,
    thought_history: list[ThoughtAction],
    uploaded_blocks: list[UIBlock],
    similar_episodes: list[dict] | None = None,
    *,
    mask_sensitive: bool = True,
) -> dict[str, Any]:
    """Build the full user-side prompt payload for a ReAct step."""
    history_payload = [
        {
            "step": i + 1,
            "thought": ta.thought,
            "action": ta.decision.action,
            "element_id": ta.decision.element_id,
            "text": ta.decision.text,
            "reason": ta.decision.reason,
        }
        for i, ta in enumerate(thought_history)
    ]

    payload: dict[str, Any] = {
        "task": task,
        "step": len(thought_history) + 1,
        "thought_action_history": history_payload,
        "uploaded_blocks": [
            block.to_prompt_payload(mask_sensitive=mask_sensitive)
            for block in uploaded_blocks
        ],
        "allowed_actions": ["click", "input", "scroll", "back", "finish"],
        "instruction": (
            "Think step by step (thought field) about the current UI state and task progress, "
            "then choose the next action. "
            'Return JSON: {"thought": "...", "action": "...", "element_id": "...", "text": null_or_string, "reason": "..."}.'
        ),
    }

    if similar_episodes:
        payload["similar_past_experiences"] = similar_episodes

    return payload


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def parse_react_response(data: dict[str, Any]) -> ThoughtAction:
    """Parse a raw LLM JSON dict into a ThoughtAction."""
    thought = data.get("thought", "")
    if not isinstance(thought, str):
        thought = ""

    action = data.get("action", "finish")
    element_id = data.get("element_id")
    text = data.get("text")
    reason = data.get("reason", "react decision")

    if not isinstance(action, str):
        action = "finish"
    if element_id is not None and not isinstance(element_id, str):
        element_id = None
    if text is not None and not isinstance(text, str):
        text = None
    if not isinstance(reason, str):
        reason = "react decision"

    return ThoughtAction(
        thought=thought,
        decision=Decision(
            action=action,
            element_id=element_id,
            text=text,
            reason=reason,
        ),
    )


# ---------------------------------------------------------------------------
# Subtask confirmation prompt (ReAct-aware)
# ---------------------------------------------------------------------------

def build_subtask_prompt(
    task: str,
    thought_history: list[ThoughtAction],
    candidates: list[str],
) -> dict[str, Any]:
    """Prompt for the cloud LLM's subtask confirmation step in ReAct mode."""
    return {
        "task": task,
        "step": len(thought_history) + 1,
        "previous_thoughts": [ta.thought for ta in thought_history],
        "candidate_subtasks": candidates,
        "instruction": (
            "Choose the single most useful candidate subtask given the task and previous steps. "
            'Return only JSON: {"subtask": "..."}.'
        ),
    }
