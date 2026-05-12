from __future__ import annotations

from typing import Protocol

from .llm import HeuristicCloudLLM, HeuristicLocalLLM
from .models import Decision, StepResult, Task, UIBlock
from .partitioner import LayoutAwarePartitioner


class CloudLLM(Protocol):
    def confirm_subtask(self, task: str, history: list[Decision], candidates: list[str]) -> str:
        ...

    def decide(self, task: str, history: list[Decision], uploaded_blocks: list[UIBlock]) -> Decision | None:
        ...


class CollaborativeAgent:
    def __init__(
        self,
        partitioner: LayoutAwarePartitioner | None = None,
        local_llm: HeuristicLocalLLM | None = None,
        cloud_llm: CloudLLM | None = None,
        max_rounds: int = 3,
    ) -> None:
        self.partitioner = partitioner or LayoutAwarePartitioner()
        self.local_llm = local_llm or HeuristicLocalLLM()
        self.cloud_llm = cloud_llm or HeuristicCloudLLM()
        self.max_rounds = max_rounds

    def run(self, task: Task) -> StepResult:
        history: list[Decision] = []
        blocks = self.partitioner.partition(task.ui_state)
        candidates = [
            self.local_llm.generate_subtask(task.instruction, history, block) for block in blocks
        ]
        subtask = self.cloud_llm.confirm_subtask(task.instruction, history, candidates)
        ranked = self.local_llm.rank_blocks(task.instruction, subtask, blocks)

        uploaded: list[UIBlock] = []
        decision: Decision | None = None
        for round_index, ranked_block in enumerate(ranked[: self.max_rounds], start=1):
            uploaded.append(ranked_block.block)
            decision = self.cloud_llm.decide(task.instruction, history, uploaded)
            if decision and decision.is_valid:
                break
        else:
            round_index = min(len(ranked), self.max_rounds)

        if decision is None:
            decision = Decision("finish", reason="no valid action found")

        return _result(task, "collaborative", decision, uploaded, round_index, subtask)


class CloudOnlyAgent:
    def __init__(self, cloud_llm: CloudLLM | None = None) -> None:
        self.cloud_llm = cloud_llm or HeuristicCloudLLM()

    def run(self, task: Task) -> StepResult:
        full_block = UIBlock("full_ui", task.ui_state.root_id, task.ui_state.elements)
        subtask = f"Use full UI to complete: {task.instruction}"
        decision = self.cloud_llm.decide(task.instruction, [], [full_block]) or Decision("finish")
        return _result(task, "cloud_only", decision, [full_block], 1, subtask)


class LocalOnlyAgent:
    def __init__(
        self,
        partitioner: LayoutAwarePartitioner | None = None,
        local_llm: HeuristicLocalLLM | None = None,
    ) -> None:
        self.partitioner = partitioner or LayoutAwarePartitioner()
        self.local_llm = local_llm or HeuristicLocalLLM()

    def run(self, task: Task) -> StepResult:
        blocks = self.partitioner.partition(task.ui_state)
        candidates = [
            self.local_llm.generate_subtask(task.instruction, [], block) for block in blocks
        ]
        subtask = next((candidate for candidate in candidates if "unrelated" not in candidate), candidates[0])
        ranked = self.local_llm.rank_blocks(task.instruction, subtask, blocks)
        top = ranked[0].block
        element = next((e for e in top.elements if e.clickable or e.editable), None)
        decision = Decision(
            "input" if element and element.editable else "click",
            element.id if element else None,
            reason="local-only coarse action",
        )
        return _result(task, "local_only", decision, [], 1, subtask)


def _result(
    task: Task,
    mode: str,
    decision: Decision,
    uploaded_blocks: list[UIBlock],
    rounds: int,
    subtask: str,
) -> StepResult:
    uploaded_ids = [element.id for block in uploaded_blocks for element in block.elements]
    uploaded_sensitive = [
        element.id for block in uploaded_blocks for element in block.elements if element.sensitive
    ]
    all_sensitive = [element for element in task.ui_state.elements if element.sensitive]
    expected = task.expected_action
    success = decision.action == expected["action"] and decision.element_id == expected.get("element_id")
    return StepResult(
        task_id=task.id,
        mode=mode,
        success=success,
        decision=decision,
        uploaded_element_ids=uploaded_ids,
        uploaded_sensitive_ids=uploaded_sensitive,
        total_elements=len(task.ui_state.elements),
        total_sensitive=len(all_sensitive),
        rounds=rounds,
        confirmed_subtask=subtask,
    )
