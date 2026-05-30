# LC-PrivateGUI Prototype

> **▶ 2-minute demo video:** https://YOUR-2-MINUTE-DEMO-VIDEO-LINK
> *(PrivacyPay banking agent — replace this placeholder with your uploaded video link.)*

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

### v0.6.0 - Ollama local-only backend

- Added an optional Ollama-backed local LLM adapter for `local_only` experiments.
- Added `--local-backend ollama` to run local-only decisions through a model served at `OLLAMA_BASE_URL`.
- Added local model configuration through `OLLAMA_BASE_URL` and `OLLAMA_MODEL`.
- Default local model configuration targets `qwen2.5:latest` on `http://localhost:11434`.
- Ollama local-only result on the 5-task real Android trace benchmark: 60.00% relaxed success, 60.00% strict success, 0.00% average UI exposure, and 0.00% average sensitive exposure.
- This result is higher than the heuristic local-only baseline, but still below the OpenAI-backed modes, showing the privacy-utility tradeoff.

Example:

```bash
python3 -m lc_private_gui \
  --tasks experiments/real_android_traces/all_real_android_tasks.json \
  --mode local_only \
  --local-backend ollama \
  --log experiments/real_android_traces/results/local_only_ollama_audit.json
```

### v0.7.0 - Safe single-step Android live runner

- Added `lc_private_gui.android_live` for one live Android observe-decide-act step.
- Added ADB UIAutomator dumping, normalized task conversion, decision recording, and before/after evidence capture.
- Added a Calculator-only safe click executor using `adb shell input tap X Y`.
- Kept live execution dry-run by default; real device input requires `--execute`.
- Added an Android package allowlist, defaulting to `com.coloros.calculator`.

Dry-run example:

```bash
python3 -m lc_private_gui.android_live \
  --instruction "Tap number 7" \
  --expected-text "7" \
  --mode collaborative
```

Real execution example:

```bash
python3 -m lc_private_gui.android_live \
  --instruction "Tap number 7" \
  --expected-text "7" \
  --mode collaborative \
  --execute
```

Each run writes evidence under:

```text
experiments/live_android_runs/
```

### v0.8.0 - ReAct multi-step agent with episodic memory

- Added ReAct reasoning pattern: the cloud and local LLM backends now output an
  explicit `thought` before every action through `lc_private_gui/react.py`,
  making multi-step reasoning visible in each step record.
- Added `MultiStepRunner` (`lc_private_gui/runner.py`): a bounded
  observe-think-act loop (default `max_steps=5`) that replaces the single-step
  `android_live` runner and writes per-step records plus a trajectory summary.
- Added `EpisodicMemory` (`lc_private_gui/memory.py`): completed trajectories are
  stored locally as JSON episodes under `data/episodes/` and retrieved via
  dependency-free TF-IDF cosine similarity over task descriptions.
- Retrieved similar episodes are injected into the ReAct prompt as few-shot
  examples, forming a lightweight RAG pipeline over past agent experiences.
- The episodic store stays on-device and is never uploaded; retrieved episodes
  still have sensitive element text masked in the cloud prompt payload.
- Added `--max-steps` CLI flag to `android_live`, with live re-observation of the
  UI between steps when `--execute` is set.
- Expanded the synthetic task set from 12 to 36 tasks, adding Browser, Music,
  File manager, Weather, Camera, Social media, Phone/Dialer, and extra Settings
  scenarios, each with private distractors (emails, addresses, call logs, files,
  DMs) placed in separate layout blocks. Reproduce with `scripts/expand_tasks.py`.
- Heuristic-backend audit on the 36-task set: collaborative mode reaches 100.00%
  strict success with 15.09% average UI exposure and 6.25% average sensitive
  exposure, versus 100.00% UI exposure for cloud-only and 0.00% for local-only.
- Per-step thought chains, decisions, and exposure metrics are recorded under
  `experiments/multistep_runs/<run_id>/step_NN.json`.

### v0.9.0 - PrivacyPay: privacy-preserving banking agent (core slice)

Reframed the general GUI agent into a concrete vertical — **PrivacyPay**, a
banking / personal-finance agent — and implemented the core slice (finance task
suite + safety gate + input execution). Design recorded in `PRIVACYPAY_PLAN.md`.

- Added a finance task suite (`data/finance_tasks.json`, generator
  `scripts/build_finance_tasks.py`): 11 banking tasks across pay-bill,
  transfer-to-payee, and check-balance flows, each with PII distractors
  (account numbers, balances, transaction history, payee lists) in separate
  layout blocks.
- Heuristic-backend audit on the finance suite: collaborative mode reaches
  100.00% strict success with 9.60% average UI exposure and 4.55% average
  sensitive exposure, versus 100.00%/100.00% for cloud-only and 0.00%/0.00%
  (90.91% success) for the weaker local-only baseline.
- Added the safety mechanism `lc_private_gui/safety.py` (`SafetyPolicy`): a
  rule-based gate that reviews each decision on-device and returns
  `allow` / `require_confirmation` / `block`. Money-moving actions (entering an
  amount, or clicking authorise controls such as "Transfer now"/"Confirm
  payment") require confirmation; transfers to payees outside the allowlist or
  above the amount cap are blocked.
- The policy runs on the full on-device UI state (like the local model), so it
  reads the selected payee and amount even though those fields are never
  uploaded to the cloud.
- Added `scripts/safety_demo.py` to exercise the gate on the finance suite
  without a device (verdicts: 5 allow, 4 require_confirmation, 2 block).
- Extended the `android_live` executor to support the `input` action
  (`adb shell input text`) in addition to `click`, and routed all execution
  through the `SafetyPolicy`.
- Added `--payee`, `--amount-cap`, `--auto-confirm`, and `--no-safety` flags to
  `android_live`. Money-moving actions are held as `needs_confirmation` unless
  `--auto-confirm` is given; `MultiStepRunner` stops on a `blocked` or
  `needs_confirmation` verdict instead of looping.
- Deferred to v0.9.1: automatic PII detection (B), cumulative multi-step
  exposure metric (E), and finance evaluation (F).

Run the finance evaluation and safety demo:

```bash
python3 scripts/build_finance_tasks.py
python3 -m lc_private_gui --tasks data/finance_tasks.json --mode all
python3 scripts/safety_demo.py
```

### v0.9.1 - PrivacyPay privacy depth (auto-PII, cumulative exposure)

Completed the deferred PrivacyPay items: automatic PII detection (B),
cumulative multi-step exposure (E), and evaluation (F).

- Added `lc_private_gui/pii.py`: dependency-free regex + topic-lexicon detector
  for email, phone, account/card/IBAN, monetary amount, address, labelled name,
  and sensitive topics (medical, tax, passport, etc.). The topic lexicon
  deliberately excludes finance-control words (bank, statement, account,
  payment, transfer) so legitimate buttons are not flagged.
- Sensitivity can now be derived instead of hand-labelled: `load_tasks(...,
  auto_pii=True)` and the `--auto-pii` CLI flag annotate elements automatically
  (OR-ed with any existing labels).
- Audited auto-detection against the hand labels across both task suites
  (`scripts/pii_audit.py`): 100.00% precision, 78.79% recall, 88.14% F1 over
  447 elements. The 21 misses are bare names and contextual phrases with no hard
  pattern, motivating an LLM-based detector as future work.
- Added a cumulative multi-step exposure metric to `Trajectory` and
  `MultiStepRunner`: the union of elements ever uploaded over the union ever
  seen (ids namespaced by screen). Recorded in `trajectory.json` as
  `cumulative_exposure_rate` / `cumulative_sensitive_exposure_rate`.
- Added `scripts/cumulative_demo.py`: over a 3-screen bill-pay flow, cloud-only
  accumulates 100.00% element and 100.00% sensitive exposure, while
  collaborative accumulates 12.50% element and 0.00% sensitive exposure.
- Finance suite audit (heuristic backend) holds with `--auto-pii`: collaborative
  100.00% success at 4.55% average sensitive exposure vs 100.00% for cloud-only.
- The finance suite is also runnable against a real cloud model with
  `--cloud-backend openai-compatible` (needs `CLOUD_LLM_*`); recorded numbers
  here use the deterministic heuristic backend for reproducibility.

```bash
python3 scripts/pii_audit.py
python3 scripts/cumulative_demo.py
python3 -m lc_private_gui --tasks data/finance_tasks.json --mode all --auto-pii
```

### v0.10.0 - PrivacyPay web demo

- Added a zero-dependency web demo under `demo/`: a mock phone banking UI with a
  live "privacy X-ray" (what the cloud receives each step, sensitive fields
  masked), per-step and cumulative exposure meters, a SafetyPolicy verdict
  badge, and a "what the cloud knows about you" panel.
- Decisions, exposure metrics, and safety verdicts come from the real engine
  (`CollaborativeAgent` / `CloudOnlyAgent` + `SafetyPolicy`); only screen
  transitions are scripted. The server uses only the Python standard library.
- Three scenarios: pay a bill (ends at a human-in-the-loop confirmation),
  transfer to an unknown payee (blocked by allowlist), and transfer over the cap
  (blocked by amount limit). A mode toggle contrasts PrivacyPay vs cloud-only.
- While building the demo, tightened `SafetyPolicy` payee detection to match the
  selected-recipient field by exact resource id, so payee-list distractors are
  no longer mistaken for the recipient.

```bash
python3 demo/server.py      # then open http://localhost:8000
```

## Files

- `lc_private_gui/models.py`: core dataclasses for UI elements, blocks, tasks, decisions, and results
- `lc_private_gui/partitioner.py`: layout-aware block partitioning using ancestor paths
- `lc_private_gui/llm.py`: offline heuristic local/cloud LLM adapters
- `lc_private_gui/agent.py`: collaborative, cloud-only, and local-only agents
- `lc_private_gui/cli.py`: command-line runner and summary output
- `lc_private_gui/android_xml.py`: Android UIAutomator XML to task JSON converter
- `lc_private_gui/android_live.py`: safe multi-step Android live runner and ADB click executor
- `lc_private_gui/react.py`: ReAct prompt builder and response parser (thought + action)
- `lc_private_gui/memory.py`: episodic memory store with TF-IDF RAG retrieval
- `lc_private_gui/runner.py`: bounded multi-step observe-think-act loop
- `lc_private_gui/safety.py`: SafetyPolicy gate for money-moving actions (PrivacyPay)
- `lc_private_gui/pii.py`: automatic PII / sensitive-field detector
- `data/sample_tasks.json`: 36 synthetic GUI traces with sensitive elements
- `data/finance_tasks.json`: 11 PrivacyPay banking tasks with financial PII
- `scripts/build_finance_tasks.py`: generates the finance task suite
- `scripts/safety_demo.py`: demonstrates the SafetyPolicy gate without a device
- `scripts/pii_audit.py`: audits auto-PII detection against hand labels
- `scripts/cumulative_demo.py`: demonstrates cumulative multi-step exposure
- `demo/`: zero-dependency web demo (mock phone UI + privacy X-ray); see `demo/README.md`
- `data/episodes/`: on-device episodic memory store (auto-generated, git-ignored)
- `experiments/real_android_traces/`: converted real Android UI traces and audit results
- `experiments/multistep_runs/`: per-run trajectory records (auto-generated, git-ignored)
- `scripts/expand_tasks.py`: regenerates the v0.8 synthetic task expansion

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
