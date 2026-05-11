# LC-PrivateGUI Prototype

This is a runnable prototype for a privacy-preserving GUI agent based on local--cloud LLM collaboration, inspired by the CORE paper.

The prototype is intentionally dependency-free. It uses heuristic local/cloud LLM stand-ins so the collaboration loop can be demonstrated offline:

- local side: full UI access, layout-aware block partitioning, sub-task candidates, block ranking
- cloud side: sees only abstract candidates and uploaded block subsets, then chooses the final action
- audit side: records uploaded UI elements, uploaded sensitive elements, success, and accumulation rounds

## Run

From the repository root:

```bash
python3 -m lc_private_gui --mode all
```

Run only the collaborative agent:

```bash
python3 -m lc_private_gui --mode collaborative
```

The default audit log is written to:

```text
logs/last_run.json
```

## Version Updates

### v0.1.0 - Initial prototype

- Added a runnable offline prototype for local-cloud GUI agent collaboration.
- Added three execution modes: collaborative, cloud-only, and local-only.
- Added sample GUI tasks with sensitive UI elements for privacy exposure analysis.
- Added audit metrics for success rate, uploaded UI exposure, sensitive exposure, and collaboration rounds.
- Added command-line execution through `python3 -m lc_private_gui`.

### v0.2.0 - Expanded offline task set

- Expanded `data/sample_tasks.json` from 3 tasks to 12 mobile GUI tasks.
- Added Email, Messages, Maps, Shopping, Bank, Settings, Notes, and Clock task scenarios.
- Added richer sensitive UI distractors such as inbox subjects, chat history, saved addresses, payment details, account balances, and saved networks.
- Extended the heuristic local/cloud LLM adapters to cover the new task intents.

## Files

- `lc_private_gui/models.py`: core dataclasses for UI elements, blocks, tasks, decisions, and results
- `lc_private_gui/partitioner.py`: layout-aware block partitioning using ancestor paths
- `lc_private_gui/llm.py`: offline heuristic local/cloud LLM adapters
- `lc_private_gui/agent.py`: collaborative, cloud-only, and local-only agents
- `lc_private_gui/cli.py`: command-line runner and summary output
- `data/sample_tasks.json`: three sample GUI traces with sensitive elements

## What This Demonstrates

The collaborative mode should upload fewer UI elements than the cloud-only baseline while still completing the sample tasks. The cloud-only baseline uploads every element. The local-only baseline uploads nothing, but it uses weaker coarse decisions.

This is not a production mobile controller yet. It is a course-scale prototype that makes the privacy exposure mechanism observable and easy to extend.

## Extension Points

Replace the heuristic adapters in `llm.py` with real model calls:

- local LLM: Ollama, llama.cpp, or an on-device model runtime
- cloud LLM: OpenAI-compatible API or another remote model

Replace `data/sample_tasks.json` with:

- Android UIAutomator XML converted to the normalized schema
- desktop accessibility tree dumps
- benchmark traces from DroidTask or AndroidLab

Add a real executor after `Decision`:

- Android: `adb shell input tap`, `adb shell input text`, UIAutomator
- desktop: accessibility APIs, Playwright, or pyautogui
