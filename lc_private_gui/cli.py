from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .agent import CloudOnlyAgent, CollaborativeAgent, LocalOnlyAgent
from .llm import OllamaLocalLLM, OpenAICompatibleCloudLLM
from .metrics import summarize, to_jsonable
from .parser import load_tasks


AGENTS = {
    "collaborative": CollaborativeAgent,
    "cloud_only": CloudOnlyAgent,
    "local_only": LocalOnlyAgent,
}


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


def main() -> None:
    _load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    parser = argparse.ArgumentParser(description="Run the LC-PrivateGUI prototype.")
    parser.add_argument(
        "--tasks",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "sample_tasks.json",
        help="Path to task trace JSON.",
    )
    parser.add_argument(
        "--mode",
        choices=["collaborative", "cloud_only", "local_only", "all"],
        default="all",
        help="Agent mode to run.",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "logs" / "last_run.json",
        help="Output JSON audit log path.",
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
    args = parser.parse_args()

    tasks = load_tasks(args.tasks)
    modes = list(AGENTS) if args.mode == "all" else [args.mode]
    audit: dict[str, list[dict]] = {}
    cloud_llm = OpenAICompatibleCloudLLM() if args.cloud_backend == "openai-compatible" else None
    local_llm = OllamaLocalLLM() if args.local_backend == "ollama" else None

    for mode in modes:
        if mode in {"collaborative", "cloud_only"}:
            agent = AGENTS[mode](cloud_llm=cloud_llm)
        elif mode == "local_only":
            agent = AGENTS[mode](local_llm=local_llm)
        else:
            agent = AGENTS[mode]()
        results = [agent.run(task) for task in tasks]
        audit[mode] = [to_jsonable(result) for result in results]
        summary = summarize(results)
        print(f"\n[{mode}]")
        print(f"tasks: {summary['tasks']}")
        print(f"success_rate: {summary['success_rate']:.2%}")
        print(f"strict_success_rate: {summary['strict_success_rate']:.2%}")
        print(f"avg_ui_exposure: {summary['avg_exposure_rate']:.2%}")
        print(f"avg_sensitive_exposure: {summary['avg_sensitive_exposure_rate']:.2%}")
        print(f"avg_rounds: {summary['avg_rounds']:.2f}")
        for result in results:
            print(
                f"- {result.task_id}: success={result.success} "
                f"strict={result.strict_success} match={result.success_match_type} "
                f"decision={result.decision.action}:{result.decision.element_id} "
                f"uploaded={len(set(result.uploaded_element_ids))}/{result.total_elements} "
                f"sensitive={len(set(result.uploaded_sensitive_ids))}/{result.total_sensitive}"
            )

    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nAudit log written to {args.log}")


if __name__ == "__main__":
    main()
