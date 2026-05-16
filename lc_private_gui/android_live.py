from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from .agent import CloudOnlyAgent, CollaborativeAgent, LocalOnlyAgent
from .android_xml import convert_xml_to_task
from .llm import OllamaLocalLLM, OpenAICompatibleCloudLLM
from .metrics import to_jsonable
from .models import Decision, Task, UIElement
from .parser import load_tasks


DEFAULT_ALLOWED_PACKAGES = {"com.coloros.calculator"}
DEFAULT_RUN_ROOT = Path(__file__).resolve().parents[1] / "experiments" / "live_android_runs"
REMOTE_DUMP_PATH = "/sdcard/window.xml"


def main() -> None:
    _load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    parser = argparse.ArgumentParser(description="Run one safe live Android observe-decide-act step.")
    parser.add_argument("--instruction", required=True, help="User instruction for the live UI state.")
    parser.add_argument(
        "--expected-text",
        required=True,
        help="Text or description used to identify the expected target in the current UI.",
    )
    parser.add_argument("--expected-action", choices=["click"], default="click")
    parser.add_argument(
        "--mode",
        choices=["collaborative", "cloud_only", "local_only"],
        default="collaborative",
    )
    parser.add_argument(
        "--cloud-backend",
        choices=["heuristic", "openai-compatible"],
        default="heuristic",
        help="Cloud decision backend. The openai-compatible backend uses CLOUD_LLM_* env vars.",
    )
    parser.add_argument(
        "--local-backend",
        choices=["heuristic", "ollama"],
        default="heuristic",
        help="Local-only decision backend. The ollama backend uses OLLAMA_* env vars.",
    )
    parser.add_argument(
        "--allowed-package",
        action="append",
        default=[],
        help="Allowed Android package name. May be passed multiple times.",
    )
    parser.add_argument("--device", help="ADB device serial passed to adb -s.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_RUN_ROOT)
    execution_group = parser.add_mutually_exclusive_group()
    execution_group.add_argument(
        "--execute",
        action="store_true",
        help="Actually send adb input. Without this flag the command is dry-run only.",
    )
    execution_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicit dry-run flag for readability. This is also the default.",
    )
    args = parser.parse_args()

    allowed_packages = set(args.allowed_package) or DEFAULT_ALLOWED_PACKAGES
    run_dir = _new_run_dir(args.out_dir)
    dry_run = not args.execute

    before_xml = run_dir / "before_window.xml"
    after_xml = run_dir / "after_window.xml"
    before_task_json = run_dir / "before_task.json"
    decision_json = run_dir / "decision.json"
    summary_json = run_dir / "run_summary.json"

    before_xml.write_text(dump_current_ui_xml(device=args.device), encoding="utf-8")
    task_data = convert_xml_to_task(
        before_xml,
        task_id=run_dir.name,
        instruction=args.instruction,
        expected_action=args.expected_action,
        expected_text=args.expected_text,
    )
    before_task_json.write_text(json.dumps(task_data, ensure_ascii=False, indent=2), encoding="utf-8")
    task = load_tasks(before_task_json)[0]

    result = _build_agent(args.mode, args.cloud_backend, args.local_backend).run(task)
    decision_payload = {
        "decision": asdict(result.decision),
        "result": to_jsonable(result),
    }
    decision_json.write_text(json.dumps(decision_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    execution = execute_decision(
        result.decision,
        task,
        allowed_packages=allowed_packages,
        dry_run=dry_run,
        device=args.device,
    )

    after_xml.write_text(dump_current_ui_xml(device=args.device), encoding="utf-8")
    summary = {
        "run_id": run_dir.name,
        "instruction": args.instruction,
        "mode": args.mode,
        "dry_run": dry_run,
        "execute_flag": args.execute,
        "allowed_packages": sorted(allowed_packages),
        "before_package": task.ui_state.app,
        "decision": asdict(result.decision),
        "execution": execution,
        "artifacts": {
            "before_window_xml": str(before_xml),
            "before_task_json": str(before_task_json),
            "decision_json": str(decision_json),
            "after_window_xml": str(after_xml),
            "run_summary_json": str(summary_json),
        },
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Run written to {run_dir}")
    print(f"package={task.ui_state.app} decision={result.decision.action}:{result.decision.element_id}")
    if execution["status"] == "dry_run":
        print(f"dry-run tap would be at ({execution['tap_x']}, {execution['tap_y']})")
    elif execution["status"] == "executed":
        print(f"executed tap at ({execution['tap_x']}, {execution['tap_y']})")
    else:
        print(f"not executed: {execution['reason']}")


def dump_current_ui_xml(*, device: str | None = None) -> str:
    _run_adb(["shell", "uiautomator", "dump", REMOTE_DUMP_PATH], device=device)
    return _run_adb(["exec-out", "cat", REMOTE_DUMP_PATH], device=device).stdout


def execute_decision(
    decision: Decision,
    task: Task,
    *,
    allowed_packages: set[str],
    dry_run: bool,
    device: str | None = None,
) -> dict[str, Any]:
    if task.ui_state.app not in allowed_packages:
        return {
            "status": "blocked",
            "reason": f"package {task.ui_state.app!r} is not in the allowlist",
        }
    if decision.action != "click":
        return {
            "status": "blocked",
            "reason": f"only click is supported, got {decision.action!r}",
        }
    if decision.element_id is None:
        return {"status": "blocked", "reason": "click decision did not include an element_id"}

    elements = task.ui_state.by_id()
    element = elements.get(decision.element_id)
    if element is None:
        return {
            "status": "blocked",
            "reason": f"element_id {decision.element_id!r} was not found in the UI state",
        }

    tap = tap_point(element)
    if tap is None:
        return {
            "status": "blocked",
            "reason": f"element {decision.element_id!r} has invalid bounds",
            "bounds": element.bounds,
        }
    tap_x, tap_y = tap
    payload: dict[str, Any] = {
        "status": "dry_run" if dry_run else "executed",
        "element_id": decision.element_id,
        "bounds": element.bounds,
        "tap_x": tap_x,
        "tap_y": tap_y,
        "adb_command": ["adb", "shell", "input", "tap", str(tap_x), str(tap_y)],
    }
    if dry_run:
        return payload

    completed = _run_adb(["shell", "input", "tap", str(tap_x), str(tap_y)], device=device)
    payload["returncode"] = completed.returncode
    return payload


def tap_point(element: UIElement) -> tuple[int, int] | None:
    if len(element.bounds) != 4:
        return None
    x1, y1, x2, y2 = element.bounds
    if x2 <= x1 or y2 <= y1:
        return None
    return ((x1 + x2) // 2, (y1 + y2) // 2)


def _build_agent(mode: str, cloud_backend: str, local_backend: str):
    cloud_llm = OpenAICompatibleCloudLLM() if cloud_backend == "openai-compatible" else None
    local_llm = OllamaLocalLLM() if local_backend == "ollama" else None
    if mode == "collaborative":
        return CollaborativeAgent(cloud_llm=cloud_llm)
    if mode == "cloud_only":
        return CloudOnlyAgent(cloud_llm=cloud_llm)
    return LocalOnlyAgent(local_llm=local_llm)


def _run_adb(args: list[str], *, device: str | None = None) -> subprocess.CompletedProcess[str]:
    command = ["adb"]
    if device:
        command.extend(["-s", device])
    command.extend(args)
    return subprocess.run(command, check=True, text=True, capture_output=True)


def _new_run_dir(root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = root / timestamp
    suffix = 1
    while run_dir.exists():
        run_dir = root / f"{timestamp}_{suffix}"
        suffix += 1
    run_dir.mkdir(parents=True)
    return run_dir


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


if __name__ == "__main__":
    main()
