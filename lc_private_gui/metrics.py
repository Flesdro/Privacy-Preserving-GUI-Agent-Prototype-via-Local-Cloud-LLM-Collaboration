from __future__ import annotations

from dataclasses import asdict

from .models import StepResult


def summarize(results: list[StepResult]) -> dict[str, float]:
    if not results:
        return {}
    return {
        "tasks": len(results),
        "success_rate": sum(result.success for result in results) / len(results),
        "avg_exposure_rate": sum(result.exposure_rate for result in results) / len(results),
        "avg_sensitive_exposure_rate": sum(result.sensitive_exposure_rate for result in results)
        / len(results),
        "avg_rounds": sum(result.rounds for result in results) / len(results),
    }


def to_jsonable(result: StepResult) -> dict:
    data = asdict(result)
    data["exposure_rate"] = result.exposure_rate
    data["sensitive_exposure_rate"] = result.sensitive_exposure_rate
    return data

