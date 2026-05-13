# Real Android Trace Result Summary

This summary compares the main agent modes on five real Android UI traces collected from a physical OnePlus phone.

The traces are static UIAutomator dumps. The experiments select actions from UI trees only; they do not click or modify the phone.

## Benchmark

| Task ID | Source page | Instruction |
| --- | --- | --- |
| `real_wifi_refresh` | WLAN settings | Refresh available WiFi networks |
| `real_bluetooth_refresh` | Bluetooth settings | Refresh available Bluetooth devices |
| `real_alarm_add` | Clock alarms | Add an alarm |
| `real_calculator_tap_7` | Calculator | Tap number 7 |
| `real_display_dark_mode` | Display settings | Open dark mode settings |

## Main Results

| Mode | Backend | Relaxed success | Strict success | Avg UI exposure | Avg sensitive exposure |
| --- | --- | ---: | ---: | ---: | ---: |
| collaborative | heuristic local selector + OpenAI cloud | 100.00% | 80.00% | 15.47% | 2.00% |
| cloud_only | OpenAI cloud | 100.00% | 80.00% | 100.00% | 60.00% |
| local_only | Ollama `qwen2.5:latest` | 60.00% | 60.00% | 0.00% | 0.00% |
| local_only | heuristic local policy | 40.00% | 40.00% | 0.00% | 0.00% |

## Interpretation

The OpenAI cloud-only baseline achieves the same relaxed success rate as collaborative mode, but it uploads the full UI tree for every task. This causes 100.00% average UI exposure and 60.00% average sensitive exposure.

The collaborative mode keeps the same relaxed success rate while uploading only selected UI blocks. On this benchmark it reduces average UI exposure from 100.00% to 15.47%, and average sensitive exposure from 60.00% to 2.00%.

The Ollama local-only baseline sends nothing to the cloud, so both exposure metrics are 0.00%. Its success rate is lower at 60.00%, which shows the utility cost of relying only on a local model in the current prototype.

## Strict vs Relaxed Success

Strict success requires exact `element_id` equality with the annotated expected action. Relaxed success also accepts a selected ancestor or descendant of the expected control.

This matters for Android UI trees because a row, switch, radio button, and label can all represent the same tap target. In the OpenAI runs, `real_display_dark_mode` selected a clickable ancestor container of the expected dark-mode radio button. That is a reasonable Android action, so relaxed matching counts it as successful while strict matching does not.

## Result Files

| File | Description |
| --- | --- |
| `collaborative_openai_relaxed_audit.json` | OpenAI-backed collaborative audit log |
| `cloud_only_openai_audit.json` | OpenAI-backed cloud-only audit log |
| `local_only_ollama_audit.json` | Ollama-backed local-only audit log |
| `all_modes_audit.json` | Heuristic baseline audit log |
