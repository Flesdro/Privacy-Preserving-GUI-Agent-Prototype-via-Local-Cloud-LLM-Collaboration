"""Audit automatic PII detection against the hand-labelled `sensitive` flags.

Treats the hand labels as ground truth and reports precision / recall / F1 of
the regex detector in lc_private_gui/pii.py across the task suites, plus the
elements where they disagree. This validates that sensitivity can be derived
automatically rather than annotated by hand.

Run from the prototype root:
    python3 scripts/pii_audit.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lc_private_gui.models import UIElement
from lc_private_gui.pii import detect, is_sensitive

SUITES = [ROOT / "data" / "sample_tasks.json", ROOT / "data" / "finance_tasks.json"]


def main():
    tp = fp = fn = tn = 0
    false_neg: list[str] = []   # hand-labelled sensitive but detector missed
    false_pos: list[str] = []   # detector flagged but not hand-labelled

    for suite in SUITES:
        data = json.loads(suite.read_text(encoding="utf-8"))
        for task in data["tasks"]:
            for raw in task["ui_state"]["elements"]:
                element = UIElement(**raw)
                labelled = element.sensitive
                detected = is_sensitive(element)
                if labelled and detected:
                    tp += 1
                elif not labelled and detected:
                    fp += 1
                    false_pos.append(f"{task['id']}/{element.id}: "
                                     f"{(element.text or element.description)!r} -> {detect(element.text) or detect(element.description)}")
                elif labelled and not detected:
                    fn += 1
                    false_neg.append(f"{task['id']}/{element.id}: {(element.text or element.description)!r}")
                else:
                    tn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    print("PII auto-detection vs hand labels")
    print(f"  elements: {tp + fp + fn + tn}")
    print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  precision={precision:.2%}  recall={recall:.2%}  F1={f1:.2%}")

    if false_pos:
        print(f"\nFalse positives ({len(false_pos)}) — detector flagged, not hand-labelled:")
        for line in false_pos:
            print(f"  + {line}")
    if false_neg:
        print(f"\nFalse negatives ({len(false_neg)}) — hand-labelled, detector missed:")
        for line in false_neg:
            print(f"  - {line}")


if __name__ == "__main__":
    main()
