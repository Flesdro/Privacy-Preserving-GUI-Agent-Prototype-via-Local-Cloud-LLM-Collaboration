"""Episodic memory store with TF-IDF retrieval for experience RAG.

Completed agent trajectories are saved as JSON files under data/episodes/.
On each new run, the EpisodicMemory retrieves the top-k most similar past
episodes by TF-IDF cosine similarity over task descriptions, and returns
them as compact dicts ready to be injected into the ReAct prompt.

No external dependencies are required — tokenisation and similarity are
implemented with the standard library only.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import Episode, EpisodeStep


DEFAULT_MEMORY_DIR = Path(__file__).resolve().parents[1] / "data" / "episodes"


class EpisodicMemory:
    """Local episodic memory store with TF-IDF-based retrieval."""

    def __init__(self, memory_dir: Path | None = None) -> None:
        self.memory_dir = memory_dir or DEFAULT_MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._episodes: list[Episode] = []
        self._load_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store(self, episode: Episode) -> None:
        """Persist an episode to disk and add it to the in-memory index."""
        path = self.memory_dir / f"{episode.episode_id}.json"
        path.write_text(
            json.dumps(asdict(episode), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._episodes.append(episode)

    def retrieve(self, query: str, k: int = 2) -> list[dict[str, Any]]:
        """Return up to k most similar episodes as prompt-ready dicts.

        Episodes with zero similarity to the query are excluded.
        """
        if not self._episodes:
            return []
        scored = [
            (_tfidf_similarity(query, ep.task_description), ep)
            for ep in self._episodes
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [ep for score, ep in scored[:k] if score > 0.0]
        return [_to_prompt_dict(ep) for ep in top]

    def all_episodes(self) -> list[Episode]:
        return list(self._episodes)

    def __len__(self) -> int:
        return len(self._episodes)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        for path in sorted(self.memory_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                raw_steps = data.pop("steps", [])
                steps = [EpisodeStep(**s) for s in raw_steps]
                self._episodes.append(Episode(steps=steps, **data))
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Episode → prompt dict
# ---------------------------------------------------------------------------

def _to_prompt_dict(ep: Episode) -> dict[str, Any]:
    return {
        "task": ep.task_description,
        "app": ep.app,
        "outcome": ep.outcome,
        "total_steps": ep.total_steps,
        "avg_exposure_rate": round(ep.avg_exposure_rate, 3),
        "step_summary": [
            {
                "step": s.step,
                "thought": s.thought,
                "action": s.action,
                "element_id": s.element_id,
            }
            for s in ep.steps
        ],
    }


# ---------------------------------------------------------------------------
# TF-IDF cosine similarity (zero dependencies)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", text) if len(t) > 1]


def _term_freq(terms: list[str]) -> dict[str, float]:
    total = len(terms)
    if total == 0:
        return {}
    freq: dict[str, float] = {}
    for t in terms:
        freq[t] = freq.get(t, 0.0) + 1.0
    return {t: c / total for t, c in freq.items()}


def _tfidf_similarity(query: str, doc: str) -> float:
    query_tf = _term_freq(_tokenize(query))
    doc_tf = _term_freq(_tokenize(doc))
    common = set(query_tf) & set(doc_tf)
    if not common:
        return 0.0
    dot = sum(query_tf[t] * doc_tf[t] for t in common)
    mag_q = math.sqrt(sum(v * v for v in query_tf.values()))
    mag_d = math.sqrt(sum(v * v for v in doc_tf.values()))
    if mag_q == 0.0 or mag_d == 0.0:
        return 0.0
    return dot / (mag_q * mag_d)


# ---------------------------------------------------------------------------
# Helper: build an Episode from a completed MultiStepRunner trajectory
# ---------------------------------------------------------------------------

def episode_from_trajectory(
    run_id: str,
    task_description: str,
    app: str,
    mode: str,
    steps: list[dict[str, Any]],
    outcome: str,
) -> Episode:
    """Convenience factory used by MultiStepRunner."""
    episode_steps = [
        EpisodeStep(
            step=s["step"],
            thought=s.get("thought", ""),
            action=s["action"],
            element_id=s.get("element_id"),
            text=s.get("text"),
            reason=s.get("reason", ""),
            observation=s.get("observation", ""),
            exposure_rate=s.get("exposure_rate", 0.0),
            sensitive_exposure_rate=s.get("sensitive_exposure_rate", 0.0),
        )
        for s in steps
    ]
    total = len(episode_steps)
    avg_exp = sum(s.exposure_rate for s in episode_steps) / total if total else 0.0
    avg_sens = sum(s.sensitive_exposure_rate for s in episode_steps) / total if total else 0.0
    return Episode(
        episode_id=run_id,
        task_description=task_description,
        app=app,
        mode=mode,
        steps=episode_steps,
        outcome=outcome,
        total_steps=total,
        avg_exposure_rate=avg_exp,
        avg_sensitive_exposure_rate=avg_sens,
        timestamp=datetime.now().isoformat(),
    )
