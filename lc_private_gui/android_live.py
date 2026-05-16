from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from .agent import CloudOnlyAgent, CollaborativeAgent, LocalOnlyAgent
from .android_xml import convert_xml_to_task
from .llm import OllamaLocalLLM, OpenAICompatibleCloudLLM
from .memory import EpisodicMemory
from .models import Decision, Task, UIElement
from .parser import load_tasks
from .runner import MultiStepRunner


DEFAULT_ALLOWED_PACKAGES = {"com.coloros.calculator"}
DEFAULT_RUN_ROOT = Path(__file__).resolve().parents[1] / "experiments" / "live_android_runs"
REMOTE_DUMP_PATH = "/sdcard/window.xml"


def main() -> None:
    _load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    parser = argparse.ArgumentParser(
        description="Run a safe multi-step ReAct Android agent (observe-think-act loop)."
    )
    parser.add_argument("--instruction", required=True, help="High-level task instruction.")
    parser.add_argument(
        "--expected-text",
        required=True,
        help="Text used to identify the expected target element in the initial UI.",
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
        "--max-steps",
        type=int,
        default=5,
        help="Maximum number of observe-think-act steps (default 5).",
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
    dry_run = not args.execute

    # --- Dump initial UI and build the first Task --------------------------
    initial_xml_path = args.out_dir / "_initial_window.xml"
    initial_xml_path.parent.mkdir(parents=True, exist_ok=True)
    initial_xml = dump_current_ui_xml(device=args.device)
    initial_xml_path.write_text(initial_xml, encoding="utf-8")

    task_data = convert_xml_to_task(
        initial_xml_path,
        task_id="live_task",
        instruction=args.instruction,
        expected_action=args.expected_action,
        expected_text=args.expected_text,
    )
    task_json_path = args.out_dir / "_initial_task.json"
    task_json_path.write_text(json.dumps(task_data, ensure_ascii=False, indent=2), encoding="utf-8")
    task = load_tasks(task_json_path)[0]

    # --- Build agent and runner --------------------------------------------
    agent = _build_agent(args.mode, args.cloud_backend, args.local_backend)
    memory = EpisodicMemory()
    runner = MultiStepRunner(agent, memory=memory, max_steps=args.max_steps, run_root=args.out_dir)

    # --- Executor closure --------------------------------------------------
    def _executor(decision: Decision, current_task: Task) -> dict[str, Any]:
        return execute_decision(
            decision,
            current_task,
            allowed_packages=allowed_packages,
            dry_run=dry_run,
            device=args.device,
        )

    # --- Observe closure (re-dumps UI after each action) ------------------
    def _observe() -> Task:
        xml_text = dump_current_ui_xml(device=args.device)
        tmp = args.out_dir / "_observe_tmp.xml"
        tmp.write_text(xml_text, encoding="utf-8")
        data = convert_xml_to_task(
            tmp,
            task_id="live_task",
            instruction=args.instruction,
            expected_action=args.expected_action,
            expected_text=args.expected_text,
        )
        tmp_json = args.out_dir / "_observe_tmp.json"
        tmp_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return load_tasks(tmp_json)[0]

    # --- Run ---------------------------------------------------------------
    trajectory = runner.run(
        task,
        executor=_executor,
        dry_run=dry_run,
        observe=_observe if args.execute else None,
    )

    print(f"\nDone. outcome={trajectory.outcome}  steps={trajectory.total_steps}/{args.max_steps}")
    print(f"avg_exposure={trajectory.avg_exposure_rate:.2%}  "
          f"avg_sensitive={trajectory.avg_sensitive_exposure_rate:.2%}")
    print(f"episodes_in_memory={len(memory)}")


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
