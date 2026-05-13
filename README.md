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

### v0.3.0 - Real Android UI trace experiment

- Added Android UIAutomator XML conversion support through `lc_private_gui/android_xml.py`.
- Added `experiments/real_android_traces/` for real-device experiment records.
- Converted five UI dumps from a physical OnePlus phone into task traces: WLAN, Bluetooth, Clock Alarm, Calculator, and Display settings.
- Recorded real-trace audit results in `experiments/real_android_traces/results/all_modes_audit.json`.
- Latest real-trace result: collaborative mode completed 5/5 tasks with 15.47% average UI exposure and 2.00% average sensitive exposure, compared with 100.00% UI exposure for cloud-only.
- Kept real XML dumps ignored by Git because they may contain private device text such as network names, alarm times, or device names.
- Clarified that local/cloud LLMs are still deterministic heuristic adapters, not real model API calls.

### v0.4.0 - OpenAI-compatible cloud interface

- Added an optional OpenAI-compatible cloud LLM adapter.
- Kept the default backend as deterministic heuristic simulation for offline reproducibility.
- Added `--cloud-backend openai-compatible` for real cloud-side subtask confirmation and action selection.
- Required cloud configuration through environment variables: `CLOUD_LLM_API_KEY`, `CLOUD_LLM_BASE_URL`, and `CLOUD_LLM_MODEL`.
- The real cloud backend only receives uploaded UI blocks, with sensitive element text masked in the prompt payload.
- Estimated one full 5-task real Android trace experiment at about 4.8k collaborative prompt tokens plus about 0.8k output tokens; cloud-only is about 16.4k prompt tokens plus about 0.4k output tokens.

Example:

```bash
export CLOUD_LLM_API_KEY="..."
export CLOUD_LLM_BASE_URL="https://api.example.com/v1"
export CLOUD_LLM_MODEL="your-model-name"

python3 -m lc_private_gui \
  --tasks experiments/real_android_traces/all_real_android_tasks.json \
  --mode collaborative \
  --cloud-backend openai-compatible
```

You can also copy `.env.example` to `.env` for local credential storage. The `.env` file is ignored by Git.

### v0.5.0 - OpenAI real-trace comparison

- Added hierarchy-aware relaxed success matching for real Android UI trees.
- Audit logs now report both relaxed `success` and exact `strict_success`.
- Ran OpenAI-backed collaborative mode on the 5-task real Android trace benchmark.
- Ran OpenAI-backed cloud-only mode on the same benchmark for privacy comparison.
- OpenAI collaborative result: 100.00% relaxed success, 80.00% strict success, 15.47% average UI exposure, and 2.00% average sensitive exposure.
- OpenAI cloud-only result: 100.00% relaxed success, 80.00% strict success, 100.00% average UI exposure, and 60.00% average sensitive exposure.
- The only strict mismatch was `real_display_dark_mode`, where the model selected a clickable ancestor container of the expected dark-mode control.

## Files

- `lc_private_gui/models.py`: core dataclasses for UI elements, blocks, tasks, decisions, and results
- `lc_private_gui/partitioner.py`: layout-aware block partitioning using ancestor paths
- `lc_private_gui/llm.py`: offline heuristic local/cloud LLM adapters
- `lc_private_gui/agent.py`: collaborative, cloud-only, and local-only agents
- `lc_private_gui/cli.py`: command-line runner and summary output
- `lc_private_gui/android_xml.py`: Android UIAutomator XML to task JSON converter
- `data/sample_tasks.json`: 12 synthetic GUI traces with sensitive elements
- `experiments/real_android_traces/`: converted real Android UI traces and audit results

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
