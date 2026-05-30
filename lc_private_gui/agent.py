from __future__ import annotations

from typing import Protocol

from .llm import HeuristicCloudLLM, HeuristicLocalLLM
from .models import Decision, StepResult, Task, ThoughtAction, UIBlock
from .partitioner import LayoutAwarePartitioner


class CloudLLM(Protocol):
    def confirm_subtask(self, task: str, history: list[Decision], candidates: list[str]) -> str:
        ...

    def decide(self, task: str, history: list[Decision], uploaded_blocks: list[UIBlock]) -> Decision | None:
        ...


class LocalLLM(Protocol):
    def generate_subtask(self, task: str, history: list[Decision], block: UIBlock) -> str:
        ...

    def rank_blocks(self, task: str, subtask: str, blocks: list[UIBlock]):
        ...


class LocalDecisionLLM(LocalLLM, Protocol):
    def decide_local(self, task: str, history: list[Decision], blocks: list[UIBlock]) -> Decision | None:
        ...


class CollaborativeAgent:
    def __init__(
        self,
        partitioner: LayoutAwarePartitioner | None = None,
        local_llm: LocalLLM | None = None,
        cloud_llm: CloudLLM | None = None,
        max_rounds: int = 3,
    ) -> None:
        self.partitioner = partitioner or LayoutAwarePartitioner()
        self.local_llm = local_llm or HeuristicLocalLLM()
        self.cloud_llm = cloud_llm or HeuristicCloudLLM()
        self.max_rounds = max_rounds

    def run(
        self,
        task: Task,
        thought_history: list[ThoughtAction] | None = None,
        similar_episodes: list[dict] | None = None,
    ) -> StepResult:
        thought_history = thought_history or []
        history: list[Decision] = [ta.decision for ta in thought_history]

        blocks = self.partitioner.partition(task.ui_state)
        candidates = [
            self.local_llm.generate_subtask(task.instruction, history, block) for block in blocks
        ]

        # Use ReAct-aware subtask confirmation if available
        if thought_history and hasattr(self.cloud_llm, "react_confirm_subtask"):
            subtask = self.cloud_llm.react_confirm_subtask(
                task.instruction, thought_history, candidates
            )
        else:
            subtask = self.cloud_llm.confirm_subtask(task.instruction, history, candidates)

        ranked = self.local_llm.rank_blocks(task.instruction, subtask, blocks)

        uploaded: list[UIBlock] = []
        thought = ""
        decision: Decision | None = None

        for round_index, ranked_block in enumerate(ranked[: self.max_rounds], start=1):
            uploaded.append(ranked_block.block)
            # Use ReAct decide if available (returns ThoughtAction)
            if hasattr(self.cloud_llm, "react_decide"):
                ta = self.cloud_llm.react_decide(
                    task.instruction, thought_history, uploaded, similar_episodes
                )
                thought = ta.thought
                decision = ta.decision
            else:
                decision = self.cloud_llm.decide(task.instruction, history, uploaded)
            if decision and decision.is_valid:
                break
        else:
            round_index = min(len(ranked), self.max_rounds)

        if decision is None:
            decision = Decision("finish", reason="no valid action found")

        uploaded_ids = {block.id for block in uploaded}
        ranking = [
            {
                "block_id": rb.block.id,
                "score": round(rb.score, 4),
                "element_ids": [e.id for e in rb.block.elements],
                "sensitive": any(e.sensitive for e in rb.block.elements),
                "uploaded": rb.block.id in uploaded_ids,
            }
            for rb in ranked
        ]

        return _result(task, "collaborative", decision, uploaded, round_index, subtask, thought, ranking)


class CloudOnlyAgent:
    def __init__(self, cloud_llm: CloudLLM | None = None) -> None:
        self.cloud_llm = cloud_llm or HeuristicCloudLLM()

    def run(
        self,
        task: Task,
        thought_history: list[ThoughtAction] | None = None,
        similar_episodes: list[dict] | None = None,
    ) -> StepResult:
        thought_history = thought_history or []
        full_block = UIBlock("full_ui", task.ui_state.root_id, task.ui_state.elements)
        subtask = f"Use full UI to complete: {task.instruction}"
        thought = ""
        if hasattr(self.cloud_llm, "react_decide"):
            ta = self.cloud_llm.react_decide(
                task.instruction, thought_history, [full_block], similar_episodes
            )
            thought, decision = ta.thought, ta.decision
        else:
            decision = self.cloud_llm.decide(task.instruction, [], [full_block]) or Decision("finish")
        return _result(task, "cloud_only", decision, [full_block], 1, subtask, thought)


class LocalOnlyAgent:
    def __init__(
        self,
        partitioner: LayoutAwarePartitioner | None = None,
        local_llm: LocalDecisionLLM | None = None,
    ) -> None:
        self.partitioner = partitioner or LayoutAwarePartitioner()
        self.local_llm = local_llm or HeuristicLocalLLM()

    def run(
        self,
        task: Task,
        thought_history: list[ThoughtAction] | None = None,
        similar_episodes: list[dict] | None = None,
    ) -> StepResult:
        thought_history = thought_history or []
        history: list[Decision] = [ta.decision for ta in thought_history]

        blocks = self.partitioner.partition(task.ui_state)
        candidates = [
            self.local_llm.generate_subtask(task.instruction, history, block) for block in blocks
        ]
        subtask = next((c for c in candidates if "unrelated" not in c), candidates[0])
        ranked = self.local_llm.rank_blocks(task.instruction, subtask, blocks)
        thought = ""

        # ReAct local decide (OllamaLocalLLM)
        if hasattr(self.local_llm, "react_decide_local"):
            ordered_blocks = [item.block for item in ranked]
            ta = self.local_llm.react_decide_local(
                task.instruction, thought_history, ordered_blocks, similar_episodes
            )
            thought, decision = ta.thought, ta.decision
        elif hasattr(self.local_llm, "decide_local"):
            ordered_blocks = [item.block for item in ranked]
            decision = self.local_llm.decide_local(task.instruction, history, ordered_blocks) or Decision(
                "finish",
                reason="local-only model did not return a valid action",
            )
        else:
            top = ranked[0].block
            element = next((e for e in top.elements if e.clickable or e.editable), None)
            decision = Decision(
                "input" if element and element.editable else "click",
                element.id if element else None,
                reason="local-only coarse action",
            )
        return _result(task, "local_only", decision, [], 1, subtask, thought)


def _result(
    task: Task,
    mode: str,
    decision: Decision,
    uploaded_blocks: list[UIBlock],
    rounds: int,
    subtask: str,
    thought: str = "",
    ranking: list[dict] | None = None,
) -> StepResult:
    uploaded_ids = [element.id for block in uploaded_blocks for element in block.elements]
    uploaded_sensitive = [
        element.id for block in uploaded_blocks for element in block.elements if element.sensitive
    ]
    all_sensitive = [element for element in task.ui_state.elements if element.sensitive]
    expected = task.expected_action
    strict_success = decision.action == expected["action"] and decision.element_id == expected.get("element_id")
    relaxed_success, match_type = _relaxed_success(task, decision, expected)
    return StepResult(
        task_id=task.id,
        mode=mode,
        success=relaxed_success,
        strict_success=strict_success,
        relaxed_success=relaxed_success,
        success_match_type=match_type,
        decision=decision,
        uploaded_element_ids=uploaded_ids,
        uploaded_sensitive_ids=uploaded_sensitive,
        total_elements=len(task.ui_state.elements),
        total_sensitive=len(all_sensitive),
        rounds=rounds,
        confirmed_subtask=subtask,
        thought=thought,
        block_ranking=ranking or [],
    )


def _relaxed_success(task: Task, decision: Decision, expected: dict[str, str]) -> tuple[bool, str]:
    if decision.action != expected["action"]:
        return False, "action_mismatch"

    expected_id = expected.get("element_id")
    decided_id = decision.element_id
    if expected_id is None:
        return decided_id is None, "no_element" if decided_id is None else "unexpected_element"
    if decided_id is None:
        return False, "missing_element"
    if decided_id == expected_id:
        return True, "strict"

    elements = task.ui_state.by_id()
    if _is_ancestor(decided_id, expected_id, elements):
        return True, "ancestor"
    if _is_ancestor(expected_id, decided_id, elements):
        return True, "descendant"
    return False, "element_mismatch"


def _is_ancestor(candidate_ancestor_id: str, element_id: str, elements) -> bool:
    current = elements.get(element_id)
    while current and current.parent:
        if current.parent == candidate_ancestor_id:
            return True
        current = elements.get(current.parent)
    return False
