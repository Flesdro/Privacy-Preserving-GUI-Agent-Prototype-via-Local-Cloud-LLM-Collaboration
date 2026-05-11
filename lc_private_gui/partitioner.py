from __future__ import annotations

from collections import defaultdict

from .models import GUIState, UIBlock, UIElement


class LayoutAwarePartitioner:
    """Groups important UI elements by shared XML/accessibility ancestors."""

    def __init__(self, min_blocks: int = 3) -> None:
        self.min_blocks = min_blocks

    def partition(self, state: GUIState) -> list[UIBlock]:
        elements = state.by_id()
        important = [element for element in state.elements if element.is_important]
        if not important:
            return [UIBlock(id="block_0", ancestor_id=state.root_id, elements=state.elements)]

        paths = {element.id: self._ancestor_path(element, elements, state.root_id) for element in important}
        max_depth = max(len(path) for path in paths.values())

        selected_groups: dict[str, list[UIElement]] | None = None
        for depth in range(max_depth):
            groups: dict[str, list[UIElement]] = defaultdict(list)
            for element in important:
                path = paths[element.id]
                ancestor = path[min(depth, len(path) - 1)]
                groups[ancestor].append(element)
            if len(groups) >= self.min_blocks:
                selected_groups = groups
                break

        if selected_groups is None:
            selected_groups = defaultdict(list)
            for element in important:
                selected_groups[state.root_id].append(element)

        return [
            UIBlock(id=f"block_{index}", ancestor_id=ancestor_id, elements=block_elements)
            for index, (ancestor_id, block_elements) in enumerate(selected_groups.items())
        ]

    def _ancestor_path(
        self, element: UIElement, elements: dict[str, UIElement], root_id: str
    ) -> list[str]:
        path: list[str] = []
        current_parent = element.parent
        while current_parent:
            path.append(current_parent)
            parent = elements.get(current_parent)
            current_parent = parent.parent if parent else None
        if not path or path[-1] != root_id:
            path.append(root_id)
        return list(reversed(path))

