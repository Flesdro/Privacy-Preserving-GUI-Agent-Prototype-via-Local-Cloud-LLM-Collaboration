# LC-PrivateGUI Upgrade Plan

## Overview

This document records the full design and implementation plan for upgrading the prototype
from a single-step decision system (v0.7) to a multi-step ReAct agent with episodic memory
and RAG-based experience retrieval.

The upgrade targets the following rubric dimensions:

| Dimension | Weight | Gap before upgrade | After upgrade |
|-----------|--------|--------------------|---------------|
| Agentic behavior | 25% | Single-step only, no memory | Multi-step ReAct loop + episodic memory |
| Implementation quality | 20% | Runs once and exits | Bounded loop, trajectory logging |
| Evaluation and testing | 10% | 5 real traces + 12 synthetic | 5 real traces + 35+ synthetic |
| System design | 20% | 4 components | 6 components (+ memory layer + runner) |

---

## Current State (v0.7)

```
android_live.py
  └── agent.run(task)        # single step
        ├── partitioner.partition(ui_state)
        ├── local_llm.generate_subtask()
        ├── cloud_llm.confirm_subtask()
        ├── local_llm.rank_blocks()
        └── cloud_llm.decide()   # returns Decision, no thought field
```

Problems:
- `history: list[Decision]` is initialized empty every run and never persisted.
- The agent produces one action and exits.
- The cloud LLM prompt returns `{action, element_id, text, reason}` with no reasoning trace.
- No experience is stored or retrieved across runs.

---

## Target Architecture (v0.8)

```
android_live.py (thin CLI entry)
  └── MultiStepRunner.run(task)
        ├── memory.retrieve(instruction, k=2)    ← RAG: fetch similar past episodes
        ├── loop step 1..max_steps:
        │   ├── observe UI  (ADB dump or static XML)
        │   ├── ReActAgent.run(task, thought_history, similar_episodes)
        │   │   ├── partitioner.partition(ui_state)
        │   │   ├── local_llm.generate_subtask()
        │   │   ├── cloud_llm.confirm_subtask()
        │   │   ├── local_llm.rank_blocks()
        │   │   └── cloud_llm.react_decide()     ← NEW: returns (thought, Decision)
        │   ├── thought_history.append(thought, decision)
        │   ├── save step record to run_dir/step_NN.json
        │   ├── if decision.action == "finish": break
        │   └── executor(decision)  [ADB tap or dry-run]
        └── memory.store(episode)                ← persist full trajectory
```

New components: `react.py`, `memory.py`, `runner.py`
Modified components: `models.py`, `llm.py`, `android_live.py`

---

## New Dataclasses (`models.py`)

```python
@dataclass
class ThoughtAction:
    thought: str        # LLM's reasoning trace for this step
    decision: Decision  # the chosen action

@dataclass
class ThoughtStep:
    step: int
    thought: str
    decision: Decision
    observation: str            # brief textual summary of what changed
    exposure_rate: float
    sensitive_exposure_rate: float

@dataclass
class Trajectory:
    task_id: str
    instruction: str
    mode: str
    steps: list[ThoughtStep]
    outcome: str                # "success" | "max_steps" | "blocked"
    total_steps: int
    avg_exposure_rate: float
    avg_sensitive_exposure_rate: float
    similar_episodes_used: int

@dataclass
class EpisodeStep:
    step: int
    thought: str
    action: str
    element_id: str | None
    text: str | None
    reason: str
    observation: str
    exposure_rate: float
    sensitive_exposure_rate: float

@dataclass
class Episode:
    episode_id: str
    task_description: str
    app: str
    mode: str
    steps: list[EpisodeStep]
    outcome: str
    total_steps: int
    avg_exposure_rate: float
    avg_sensitive_exposure_rate: float
    timestamp: str
```

---

## Component 1: ReAct Prompt Layer (`react.py`)

### What it does

Wraps the existing cloud LLM prompt so that the model outputs an explicit reasoning step
(the `thought` field) before choosing an action. This makes the agent's reasoning visible
and directly demonstrates "multi-step reasoning" from the rubric.

### ReAct output format (cloud LLM)

Before (v0.7):
```json
{
  "action": "click",
  "element_id": "btn_7",
  "reason": "tap target digit"
}
```

After (v0.8):
```json
{
  "thought": "I see the Calculator app. The task is to compute 7+3. Block_1 contains digit buttons. I should tap 7 first.",
  "action": "click",
  "element_id": "btn_7",
  "reason": "tap target digit"
}
```

### Prompt injection: few-shot from memory

When similar past episodes exist in memory, they are injected into the prompt:

```json
{
  "task": "Tap number 7 on the calculator then press equals",
  "step": 1,
  "thought_action_history": [],
  "uploaded_blocks": [...],
  "similar_past_experiences": [
    {
      "task": "Calculate 3+4 on calculator",
      "outcome": "success",
      "total_steps": 3,
      "step_summary": [
        {"step": 1, "thought": "I see digit buttons...", "action": "click", "element_id": "btn_3"},
        {"step": 2, "thought": "3 shown in display, tap +", "action": "click", "element_id": "btn_plus"},
        {"step": 3, "thought": "Now tap 4", "action": "click", "element_id": "btn_4"}
      ]
    }
  ],
  "instruction": "Think step by step (thought field), then choose the next action. Return JSON: {thought, action, element_id, text, reason}."
}
```

### Key functions

```python
def build_react_system_prompt(role: str = "cloud") -> str
    # Returns the system prompt explaining ReAct format

def build_react_prompt(
    task: str,
    thought_history: list[ThoughtAction],
    uploaded_blocks: list[UIBlock],
    similar_episodes: list[dict] | None = None,
    *,
    mask_sensitive: bool = True,
) -> dict[str, Any]
    # Builds the full user prompt payload

def parse_react_response(data: dict[str, Any]) -> ThoughtAction
    # Parses {thought, action, element_id, text, reason} into ThoughtAction
```

---

## Component 2: Episodic Memory + TF-IDF RAG (`memory.py`)

### Storage

Each completed run is saved as a JSON file under `data/episodes/`:

```
data/episodes/
  20250516_143022.json
  20250516_151200.json
  ...
```

Files are loaded at startup into a list and re-saved incrementally (no database needed).

### Retrieval algorithm

TF-IDF cosine similarity over task descriptions, zero extra dependencies:

```python
def _tfidf_similarity(query: str, doc: str) -> float:
    query_tf = term_frequency(tokenize(query))
    doc_tf   = term_frequency(tokenize(doc))
    common   = set(query_tf) & set(doc_tf)
    dot      = sum(query_tf[t] * doc_tf[t] for t in common)
    return dot / (magnitude(query_tf) * magnitude(doc_tf))
```

Top-k episodes are converted to a compact prompt dict and injected into the ReAct prompt.

### Key classes

```python
class EpisodicMemory:
    def __init__(self, memory_dir: Path | None = None)
    def store(self, episode: Episode) -> None
    def retrieve(self, query: str, k: int = 2) -> list[dict]
    # Internal helpers: _load, _to_prompt_dict, _tfidf_similarity
```

### Privacy note

The episodic store saves trajectories locally on the device, never to the cloud.
Sensitive element text is masked in the cloud-side prompt even when episodes are
retrieved and injected.

---

## Component 3: Multi-Step Runner (`runner.py`)

### Loop logic

```
for step in 1..max_steps:
    1. Observe: dump current UI (ADB) or use static XML
    2. Retrieve: memory.retrieve(instruction, k=2)
    3. Reason:  agent.run(task, thought_history, similar_episodes)
                → returns (thought, decision, exposure_rate, ...)
    4. Record:  append ThoughtStep; write step_NN.json
    5. Check:   if decision.action == "finish" → outcome = "success"; break
    6. Execute: executor(decision) [ADB tap or dry-run]
               if blocked → outcome = "blocked"; break
memory.store(episode)
return Trajectory
```

### Termination conditions

| Condition | Outcome |
|-----------|---------|
| `decision.action == "finish"` | `"success"` |
| `step == max_steps` | `"max_steps"` |
| Executor returns `status: blocked` | `"blocked"` |

### Output artifacts per run

```
experiments/multistep_runs/20250516_143022/
  step_01.json     ← thought + decision + exposure metrics
  step_02.json
  ...
  trajectory.json  ← full run summary
```

### Key class

```python
class MultiStepRunner:
    def __init__(
        self,
        agent,
        memory: EpisodicMemory | None = None,
        max_steps: int = 5,
        run_root: Path = DEFAULT_RUN_ROOT,
    )
    def run(self, task: Task, *, executor=None, dry_run: bool = True) -> Trajectory
```

---

## Modified Component: `llm.py`

### `OpenAICompatibleCloudLLM` — new method `react_decide()`

The existing `decide()` is kept unchanged for backward compatibility.
A new `react_decide()` method sends the ReAct prompt and returns `ThoughtAction`.

```python
def react_decide(
    self,
    task: str,
    thought_history: list[ThoughtAction],
    uploaded_blocks: list[UIBlock],
    similar_episodes: list[dict] | None = None,
) -> ThoughtAction
```

### `OllamaLocalLLM` — new method `react_decide_local()`

Same pattern for local model inference. The local model sees unmasked sensitive
elements (it runs on-device). The thought is generated locally and never uploaded.

---

## Modified Component: `android_live.py`

The single-step logic is replaced by a call to `MultiStepRunner`.
New CLI flag `--max-steps` (default 5).

```bash
# Dry-run multi-step
python3 -m lc_private_gui.android_live \
  --instruction "Calculate 7 plus 3 and press equals" \
  --expected-text "10" \
  --mode collaborative \
  --max-steps 5

# Real execution
python3 -m lc_private_gui.android_live \
  --instruction "Calculate 7 plus 3 and press equals" \
  --expected-text "10" \
  --mode collaborative \
  --max-steps 5 \
  --execute
```

---

## Task Set Expansion

### Target: 12 → 35+ synthetic tasks

New scenario groups (single-step, for benchmark breadth):

| Group | Count | Examples |
|-------|-------|---------|
| Browser | 3 | search query, open bookmark, navigate back |
| Music player | 3 | play song, skip track, toggle shuffle |
| File manager | 3 | create folder, rename file, delete item |
| Weather | 3 | search city, switch °C/°F, check forecast |
| Camera | 2 | take photo, switch to video mode |
| Social media | 4 | compose post, like post, follow user, open DM |
| Phone / Dialer | 3 | dial number, save contact, open recents |
| Additional settings | 3 | brightness, font size, language |

### Multi-step task set (for live ADB evaluation)

Real Android multi-step scenarios (extend existing 5 traces):

| Task | Steps | App |
|------|-------|-----|
| Calculate 7+3= | 4 | Calculator |
| Set alarm 7:30 AM | 3 | Clock |
| Toggle WiFi off then on | 2 | Settings |
| Add new contact | 3 | Contacts |
| Set display brightness to 50% | 2 | Settings |

---

## File Map

```
lc_private_gui/
  models.py          MODIFY   add ThoughtAction, ThoughtStep, Trajectory, EpisodeStep, Episode
  react.py           CREATE   ReAct prompt builder + response parser
  memory.py          CREATE   EpisodicMemory (store + TF-IDF retrieve)
  runner.py          CREATE   MultiStepRunner (bounded loop)
  llm.py             MODIFY   add react_decide() / react_decide_local()
  android_live.py    MODIFY   delegate to MultiStepRunner, add --max-steps flag
  agent.py           MODIFY   accept thought_history + similar_episodes in run()
  partitioner.py     NO CHANGE
  parser.py          NO CHANGE
  metrics.py         NO CHANGE
  cli.py             NO CHANGE

data/
  sample_tasks.json  MODIFY   expand from 12 to 35+ tasks
  episodes/          CREATE   episodic memory store (auto-generated at runtime)

experiments/
  multistep_runs/    CREATE   per-run trajectory records (auto-generated at runtime)
  real_android_traces/        NO CHANGE (existing results kept)
```

---

## Implementation Order

| Step | File | Time estimate |
|------|------|--------------|
| 1 | `models.py` — add new dataclasses | 10 min |
| 2 | `react.py` — ReAct prompt layer | 30 min |
| 3 | `memory.py` — episodic store + TF-IDF | 45 min |
| 4 | `runner.py` — MultiStepRunner loop | 60 min |
| 5 | `llm.py` — add react_decide() | 30 min |
| 6 | `agent.py` + `android_live.py` — wire up | 30 min |
| 7 | `data/sample_tasks.json` — expand to 35+ | 60 min |

---

## Version Tag

This upgrade will be tagged as **v0.8.0** in README.md with the following changelog entry:

```
### v0.8.0 - ReAct multi-step agent with episodic memory

- Added ReAct reasoning pattern: the cloud LLM now outputs an explicit thought
  before every action, making multi-step reasoning visible.
- Added MultiStepRunner: a bounded observe-think-act loop (default max_steps=5)
  that replaces the single-step android_live runner.
- Added EpisodicMemory: completed run trajectories are stored locally as JSON
  episodes under data/episodes/ and retrieved via TF-IDF cosine similarity.
- The retrieved similar episodes are injected into the ReAct prompt as few-shot
  examples, forming a lightweight RAG pipeline over past agent experiences.
- Added --max-steps CLI flag to android_live.
- Expanded synthetic task set from 12 to 35+ tasks covering 8 new app categories.
- All per-step thought chains, decisions, and exposure metrics are recorded under
  experiments/multistep_runs/<run_id>/step_NN.json.
```
