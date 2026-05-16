# Agent Roadmap（5.13）

This document outlines the next steps for turning the current decision-level GUI agent prototype into a safer executable Android agent.

## Current Status

The current prototype is an intelligent mobile GUI agent prototype, but it is not yet a full production agent.

It currently supports:

- Android UIAutomator XML dump parsing.
- Static UI trace to task JSON conversion.
- Single-step action decision.
- Collaborative, cloud-only, and local-only modes.
- OpenAI-compatible cloud decisions.
- Ollama-backed local-only decisions.
- Privacy exposure metrics.

It does not yet support:

- Real phone action execution.
- Multi-step observe-act loops.
- Automatic task completion checking.
- Fully model-based local block selection in collaborative mode.

## Step 1: Add a Safe ADB Click Executor

Goal: let the agent execute one low-risk click action on the phone.

Initial supported action:

```text
click
```

Execution command:

```bash
adb shell input tap X Y
```

The tap coordinate should be computed from the selected UI element bounds:

```text
tap_x = (x1 + x2) / 2
tap_y = (y1 + y2) / 2
```

Initial target page:

```text
Calculator
```

Initial task:

```text
Tap number 7
```

Safety constraints:

- Default to dry-run mode.
- Require an explicit `--execute` flag before sending ADB input.
- Only allow low-risk package names at first.
- Start with Calculator only.

Suggested package allowlist:

```text
com.coloros.calculator
```

## Step 2: Add Single-Step Observe-Decide-Act

Upgrade the current static decision flow:

```text
static XML -> decide
```

Into a minimal live agent flow:

```text
adb dump current UI
-> convert XML to task JSON
-> decide action
-> execute tap, if --execute is set
-> dump UI again
-> save before/after traces
```

Suggested command shape:

```bash
python3 -m lc_private_gui.android_live \
  --instruction "Tap number 7" \
  --expected-text "7" \
  --mode collaborative \
  --dry-run
```

Execution should require:

```bash
--execute
```

## Step 3: Record Before/After Evidence

Each live run should save:

```text
before_window.xml
before_task.json
decision.json
after_window.xml
run_summary.json
```

Recommended location:

```text
experiments/live_android_runs/
```

The XML dumps should remain ignored by Git if they contain real device text.

## Step 4: Add a Small Multi-Step Loop

After single-step execution is stable, add a bounded loop:

```text
observe -> decide -> act -> observe -> decide/finish
```

Initial limits:

```text
max_steps = 3
allowed_actions = click only
allowed_packages = calculator only
```

The loop should stop when:

- The model returns `finish`.
- The maximum step count is reached.
- The current package is not allowed.
- The selected element has invalid bounds.

## Step 5: Improve the Local Selector

The collaborative mode currently uses a heuristic local selector for block ranking.

Later upgrade path:

```text
heuristic local selector
-> Ollama local selector
-> compare privacy/utility tradeoff
```

This should happen after the safe executor because live action execution improves the agent completeness more directly.

## Recommended Implementation Order

1. Add ADB click executor for Calculator only.
2. Add a live single-step runner with dry-run default.
3. Save before/after UI dumps and decision records.
4. Run a safe Calculator experiment.
5. Add a bounded multi-step loop.
6. Replace heuristic local selector with Ollama-based ranking.

## Reporting Position

Current prototype:

```text
privacy-aware decision-level mobile GUI agent
```

After Step 1 and Step 2:

```text
safe single-step executable mobile GUI agent
```

After Step 4:

```text
bounded closed-loop mobile GUI agent prototype
```

