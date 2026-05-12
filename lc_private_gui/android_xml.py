from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from xml.etree import ElementTree


SENSITIVE_TEXT_HINTS = {
    "account",
    "address",
    "bank",
    "balance",
    "contact",
    "email",
    "home",
    "location",
    "message",
    "phone",
    "ssid",
    "wifi",
    "wlan",
    "网络",
    "地址",
    "账号",
}


def convert_xml_to_task(
    xml_path: Path,
    *,
    task_id: str,
    instruction: str,
    expected_action: str,
    expected_text: str,
) -> dict:
    tree = ElementTree.parse(xml_path)
    root_node = tree.getroot().find("node")
    if root_node is None:
        raise ValueError("UIAutomator XML does not contain a root node.")

    elements = []
    expected_element_id: str | None = None

    def visit(node: ElementTree.Element, parent_id: str | None, path: str) -> None:
        nonlocal expected_element_id

        element_id = f"node_{path}"
        text = node.attrib.get("text", "")
        description = node.attrib.get("content-desc", "")
        resource_id = node.attrib.get("resource-id", "")
        class_name = node.attrib.get("class", "")
        clickable = _bool(node.attrib.get("clickable")) or _bool(node.attrib.get("checkable"))
        editable = class_name.endswith("EditText") or resource_id.endswith("edit_text")
        sensitive = _looks_sensitive(text, description, resource_id)

        element = {
            "id": element_id,
            "parent": parent_id,
            "role": _role(class_name),
            "text": text,
            "description": description,
            "resource_id": resource_id,
            "bounds": _bounds(node.attrib.get("bounds", "")),
            "clickable": clickable,
            "editable": editable,
            "sensitive": sensitive,
        }
        elements.append(element)

        semantic = " ".join([text, description, resource_id]).lower()
        if expected_element_id is None and expected_text.lower() in semantic:
            if expected_action in {"click", "input"} and (clickable or editable):
                expected_element_id = element_id

        for index, child in enumerate(node.findall("node")):
            visit(child, element_id, f"{path}_{index}")

    visit(root_node, None, "0")

    if expected_element_id is None:
        raise ValueError(f"Could not find an actionable element matching: {expected_text!r}")

    package = root_node.attrib.get("package", "android")
    return {
        "tasks": [
            {
                "id": task_id,
                "instruction": instruction,
                "expected_action": {
                    "action": expected_action,
                    "element_id": expected_element_id,
                },
                "ui_state": {
                    "id": task_id,
                    "app": package,
                    "root_id": "node_0",
                    "elements": elements,
                },
            }
        ]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Android UIAutomator XML to task JSON.")
    parser.add_argument("xml", type=Path, help="Path to UIAutomator XML dump.")
    parser.add_argument("output", type=Path, help="Output task JSON path.")
    parser.add_argument("--task-id", default="android_wifi_refresh")
    parser.add_argument("--instruction", default="Refresh available WiFi networks")
    parser.add_argument("--expected-action", choices=["click", "input"], default="click")
    parser.add_argument("--expected-text", default="刷新")
    args = parser.parse_args()

    data = convert_xml_to_task(
        args.xml,
        task_id=args.task_id,
        instruction=args.instruction,
        expected_action=args.expected_action,
        expected_text=args.expected_text,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")


def _bool(value: str | None) -> bool:
    return value == "true"


def _role(class_name: str) -> str:
    return class_name.rsplit(".", 1)[-1] if class_name else "node"


def _bounds(value: str) -> list[int]:
    numbers = [int(item) for item in re.findall(r"\d+", value)]
    return numbers if len(numbers) == 4 else []


def _looks_sensitive(text: str, description: str, resource_id: str) -> bool:
    haystack = " ".join([text, description, resource_id]).lower()
    return any(hint in haystack for hint in SENSITIVE_TEXT_HINTS)


if __name__ == "__main__":
    main()
