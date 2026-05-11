from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


SENSITIVE_KEYS = {
    "email",
    "phone",
    "contact",
    "location",
    "address",
    "account",
    "name",
    "calendar",
    "event",
    "message",
}


@dataclass(frozen=True)
class UIElement:
    id: str
    parent: str | None
    role: str
    text: str = ""
    description: str = ""
    resource_id: str = ""
    bounds: list[int] = field(default_factory=list)
    clickable: bool = False
    editable: bool = False
    sensitive: bool = False

    @property
    def semantic_text(self) -> str:
        return " ".join(
            part for part in [self.role, self.text, self.description, self.resource_id] if part
        ).strip()

    @property
    def is_important(self) -> bool:
        return self.clickable or self.editable or bool(self.text or self.description)

    def to_prompt_dict(self, mask_sensitive: bool = False) -> dict[str, Any]:
        text = self.text
        description = self.description
        if mask_sensitive and self.sensitive:
            text = "[MASKED_SENSITIVE]"
            description = "[MASKED_SENSITIVE]" if description else ""
        return {
            "id": self.id,
            "role": self.role,
            "text": text,
            "description": description,
            "resource_id": self.resource_id,
            "clickable": self.clickable,
            "editable": self.editable,
        }


@dataclass(frozen=True)
class UIBlock:
    id: str
    ancestor_id: str
    elements: list[UIElement]

    @property
    def text(self) -> str:
        return " ".join(element.semantic_text for element in self.elements)

    def to_prompt_payload(self, mask_sensitive: bool = True) -> dict[str, Any]:
        return {
            "block_id": self.id,
            "ancestor_id": self.ancestor_id,
            "elements": [element.to_prompt_dict(mask_sensitive) for element in self.elements],
        }


@dataclass(frozen=True)
class GUIState:
    id: str
    app: str
    elements: list[UIElement]
    root_id: str = "root"

    def by_id(self) -> dict[str, UIElement]:
        return {element.id: element for element in self.elements}


@dataclass(frozen=True)
class Task:
    id: str
    instruction: str
    ui_state: GUIState
    expected_action: dict[str, str]


@dataclass(frozen=True)
class Decision:
    action: str
    element_id: str | None = None
    text: str | None = None
    reason: str = ""

    @property
    def is_valid(self) -> bool:
        return self.action in {"click", "input", "scroll", "back", "finish"} and (
            self.action in {"scroll", "back", "finish"} or self.element_id is not None
        )


@dataclass
class StepResult:
    task_id: str
    mode: str
    success: bool
    decision: Decision
    uploaded_element_ids: list[str]
    uploaded_sensitive_ids: list[str]
    total_elements: int
    total_sensitive: int
    rounds: int
    confirmed_subtask: str

    @property
    def exposure_rate(self) -> float:
        if self.total_elements == 0:
            return 0.0
        return len(set(self.uploaded_element_ids)) / self.total_elements

    @property
    def sensitive_exposure_rate(self) -> float:
        if self.total_sensitive == 0:
            return 0.0
        return len(set(self.uploaded_sensitive_ids)) / self.total_sensitive

