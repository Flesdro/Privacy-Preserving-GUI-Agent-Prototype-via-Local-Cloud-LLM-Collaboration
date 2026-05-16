"""Multi-step ReAct agent loop runner.

MultiStepRunner orchestrates the observe → think → act cycle for up to
max_steps iterations.  After every step it records a structured log entry,
and at the end of the run it stores the complete trajectory in the episodic
memory so future runs can retrieve it via RAG.

Usage (programmatic):
    runner = MultiStepRunner(agent, memory=EpisodicMemory(), max_steps=5)
    trajectory = runner.run(task, executor=my_executor, dry_run=True)

Usage (from android_live CLI): delegated automatically when --max-steps > 1.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable

from .memory import EpisodicMemory, episode_from_trajectory
from .models import Decision, Task, ThoughtAction, ThoughtStep, Trajectory


DEFAULT_MAX_STEPS = 5
DEFAULT_RUN_ROOT = (
    Path(__file__).resolve().parents[1] / "experiments" / "multistep_runs"
)


class MultiStepRunner:
    """Bounded observe-think-act loop with episodic memory integration."""

    def __init__(
        self,
        agent: Any,
        memory: EpisodicMemory | None = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        run_root: Path = DEFAULT_RUN_ROOT,
    ) -> None:
        self.agent = agent
        self.memory = memory if memory is not None else EpisodicMemory()
        self.max_steps = max_steps
        self.run_root = run_root

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(
        self,
        task: Task,
        *,
        executor: Callable[[Decision, Task], dict[str, Any]] | None = None,
        dry_run: bool = True,
        observe: Callable[[], Task] | None = None,
    ) -> Trajectory:
        """Run the multi-step loop and return a Trajectory.

        Parameters
        ----------
        task:
            Initial task (instruction + UI state).
        executor:
            Optional callable that physically executes a Decision (e.g. ADB
            tap).  Receives (decision, current_task) and returns a dict with
            at least a ``status`` key.  Ignored when dry_run=True.
        dry_run:
            When True the executor is never called (safe default).
        observe:
            Optional callable that returns an updated Task by re-dumping the
            live UI after each action.  When None the task's UI state is
            unchanged between steps (static evaluation mode).
        """
        run_dir = self._new_run_dir()
        similar_episodes = self.memory.retrieve(task.instruction, k=2)

        thought_history: list[ThoughtAction] = []
        step_records: list[dict[str, Any]] = []
        thought_steps: list[ThoughtStep] = []
        current_task = task
        outcome = "max_steps"

        for step_num in range(1, self.max_steps + 1):
            # --- Reason + decide -------------------------------------------
            result = self.agent.run(
                current_task,
                thought_history=thought_history,
                similar_episodes=similar_episodes,
            )
            decision: Decision = result.decision
            thought: str = result.thought

            thought_history.append(ThoughtAction(thought=thought, decision=decision))

            # --- Build step record -----------------------------------------
            observation = _observation_text(step_num, decision)
            ts = ThoughtStep(
                step=step_num,
                thought=thought,
                decision=decision,
                observation=observation,
                exposure_rate=result.exposure_rate,
                sensitive_exposure_rate=result.sensitive_exposure_rate,
            )
            thought_steps.append(ts)

            step_dict: dict[str, Any] = {
                "step": step_num,
                "thought": thought,
                "action": decision.action,
                "element_id": decision.element_id,
                "text": decision.text,
                "reason": decision.reason,
                "observation": observation,
                "exposure_rate": result.exposure_rate,
                "sensitive_exposure_rate": result.sensitive_exposure_rate,
                "uploaded_element_ids": result.uploaded_element_ids,
                "uploaded_sensitive_ids": result.uploaded_sensitive_ids,
                "confirmed_subtask": result.confirmed_subtask,
            }
            step_records.append(step_dict)
            _write_json(run_dir / f"step_{step_num:02d}.json", step_dict)

            # --- Termination check -----------------------------------------
            if decision.action == "finish":
                outcome = "success"
                break

            # --- Execute (optional) ----------------------------------------
            if executor is not None and not dry_run:
                exec_result = executor(decision, current_task)
                step_dict["execution"] = exec_result
                _write_json(run_dir / f"step_{step_num:02d}.json", step_dict)
                if exec_result.get("status") == "blocked":
                    outcome = "blocked"
                    break

            # --- Observe next UI state (optional) --------------------------
            if observe is not None:
                try:
                    current_task = observe()
                except Exception as exc:
                    step_dict["observe_error"] = str(exc)
                    outcome = "observe_error"
                    break

        # --- Build Trajectory ----------------------------------------------
        total = len(thought_steps)
        avg_exp = sum(s.exposure_rate for s in thought_steps) / total if total else 0.0
        avg_sens = (
            sum(s.sensitive_exposure_rate for s in thought_steps) / total
            if total
            else 0.0
        )
        trajectory = Trajectory(
            task_id=task.id,
            instruction=task.instruction,
            mode=type(self.agent).__name__,
            steps=thought_steps,
            outcome=outcome,
            total_steps=total,
            avg_exposure_rate=avg_exp,
            avg_sensitive_exposure_rate=avg_sens,
            similar_episodes_used=len(similar_episodes),
        )

        # --- Save trajectory summary ---------------------------------------
        traj_dict: dict[str, Any] = {
            "run_id": run_dir.name,
            "task_id": task.id,
            "instruction": task.instruction,
            "mode": trajectory.mode,
            "outcome": outcome,
            "total_steps": total,
            "max_steps": self.max_steps,
            "dry_run": dry_run,
            "avg_exposure_rate": round(avg_exp, 4),
            "avg_sensitive_exposure_rate": round(avg_sens, 4),
            "similar_episodes_used": len(similar_episodes),
            "steps": step_records,
        }
        _write_json(run_dir / "trajectory.json", traj_dict)

        # --- Store episode in memory ----------------------------------------
        episode = episode_from_trajectory(
            run_id=run_dir.name,
            task_description=task.instruction,
            app=task.ui_state.app,
            mode=trajectory.mode,
            steps=step_records,
            outcome=outcome,
        )
        self.memory.store(episode)

        print(f"[runner] run_id={run_dir.name} outcome={outcome} steps={total}/{self.max_steps}")
        print(f"[runner] avg_exposure={avg_exp:.2%}  avg_sensitive={avg_sens:.2%}")
        print(f"[runner] trajectory → {run_dir / 'trajectory.json'}")

        return trajectory

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _new_run_dir(self) -> Path:
        self.run_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.run_root / timestamp
        suffix = 1
        while run_dir.exists():
            run_dir = self.run_root / f"{timestamp}_{suffix}"
            suffix += 1
        run_dir.mkdir(parents=True)
        return run_dir


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _observation_text(step: int, decision: Decision) -> str:
    if decision.action == "finish":
        return f"step {step}: agent decided the task is complete"
    if decision.element_id:
        return f"step {step}: {decision.action} on element '{decision.element_id}'"
    return f"step {step}: {decision.action} (no element)"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
