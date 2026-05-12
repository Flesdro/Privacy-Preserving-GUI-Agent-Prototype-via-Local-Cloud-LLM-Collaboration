# Real Android UI Trace Experiment

This folder records experiments generated from real Android UIAutomator dumps collected from a physical OnePlus phone.

The original XML dumps are stored locally under `data/*window.xml` and are intentionally ignored by Git because they may contain real device text, network names, alarm times, or other private UI content.

## Source Dumps

| Local XML dump | Page | Task |
| --- | --- | --- |
| `data/wifi_window.xml` | WLAN settings | Refresh available WiFi networks |
| `data/bluetooth_window.xml` | Bluetooth settings | Refresh available Bluetooth devices |
| `data/alarm_window.xml` | Clock alarms | Add an alarm |
| `data/calculator_window.xml` | Calculator | Tap number 7 |
| `data/display_window.xml` | Display and brightness settings | Open dark mode settings |

## Generated Files

| Path | Description |
| --- | --- |
| `tasks/` | One converted task JSON file per real UI dump |
| `all_real_android_tasks.json` | Combined 5-task benchmark generated from the task files |
| `results/all_modes_audit.json` | Full audit output from running all three agent modes |

## Conversion Commands

```bash
python3 -m lc_private_gui.android_xml data/wifi_window.xml experiments/real_android_traces/tasks/wifi_refresh_task.json --task-id real_wifi_refresh --instruction "Refresh available WiFi networks" --expected-action click --expected-text "刷新"
python3 -m lc_private_gui.android_xml data/bluetooth_window.xml experiments/real_android_traces/tasks/bluetooth_refresh_task.json --task-id real_bluetooth_refresh --instruction "Refresh available Bluetooth devices" --expected-action click --expected-text "刷新"
python3 -m lc_private_gui.android_xml data/alarm_window.xml experiments/real_android_traces/tasks/alarm_add_task.json --task-id real_alarm_add --instruction "Add an alarm" --expected-action click --expected-text "添加闹钟"
python3 -m lc_private_gui.android_xml data/calculator_window.xml experiments/real_android_traces/tasks/calculator_tap_7_task.json --task-id real_calculator_tap_7 --instruction "Tap number 7" --expected-action click --expected-text "7"
python3 -m lc_private_gui.android_xml data/display_window.xml experiments/real_android_traces/tasks/display_dark_mode_task.json --task-id real_display_dark_mode --instruction "Open dark mode settings" --expected-action click --expected-text "rb_dark_button"
```

## Run Command

```bash
python3 -m lc_private_gui --tasks experiments/real_android_traces/all_real_android_tasks.json --mode all --log experiments/real_android_traces/results/all_modes_audit.json
```

## Latest Result

| Mode | Tasks | Success rate | Avg UI exposure | Avg sensitive exposure |
| --- | ---: | ---: | ---: | ---: |
| collaborative | 5 | 100.00% | 15.47% | 2.00% |
| cloud_only | 5 | 100.00% | 100.00% | 60.00% |
| local_only | 5 | 40.00% | 0.00% | 0.00% |

## Notes

- The collaborative mode completed all real UI trace tasks while uploading far fewer UI elements than the cloud-only baseline.
- The local-only baseline exposes no UI to the cloud, but it fails on several real UI traces because the current local policy is intentionally coarse.
- These experiments still operate on static UI dumps. They do not click or modify the physical phone.
