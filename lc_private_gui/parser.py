from __future__ import annotations

import json
from pathlib import Path

from .models import GUIState, Task, UIElement


def load_tasks(path: Path) -> list[Task]:
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks: list[Task] = []
    for item in data["tasks"]:
        state_data = item["ui_state"]
        elements = [UIElement(**element) for element in state_data["elements"]]
        ui_state = GUIState(
            id=state_data["id"],
            app=state_data["app"],
            root_id=state_data.get("root_id", "root"),
            elements=elements,
        )
        tasks.append(
            Task(
                id=item["id"],
                instruction=item["instruction"],
                ui_state=ui_state,
                expected_action=item["expected_action"],
            )
        )
    return tasks

