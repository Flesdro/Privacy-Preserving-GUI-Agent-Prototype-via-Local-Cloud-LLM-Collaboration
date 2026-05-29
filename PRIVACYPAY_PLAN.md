# PrivacyPay Plan (v0.9)

## Overview

This document reframes the general privacy-preserving GUI agent (v0.8) into a
concrete, vertical application: **PrivacyPay**, a privacy-preserving mobile
**banking / personal-finance** GUI agent.

The motivation for narrowing the scope is that the project's core strength —
keeping sensitive on-screen data on-device while a cloud model reasons over a
minimal, masked subset — is most compelling in a domain where the screen is
saturated with high-stakes personal data. Banking screens (balances, account
numbers, transaction history, payees) make the privacy-utility tradeoff sharp,
intuitive, and easy to evaluate.

### One-line positioning

> An on-device-first banking agent that completes money tasks (pay a bill,
> transfer to a payee, check a balance) by reasoning in the cloud over only
> minimal, PII-masked UI blocks — account numbers, balances, and transaction
> history never leave the phone.

---

## Why this domain

| Selection criterion | How PrivacyPay satisfies it |
|---------------------|------------------------------|
| Screen is saturated with PII | Balances, account numbers, transaction rows, payee lists |
| Privacy threat is intuitive and high-stakes | Money + financial identity; immediate legibility |
| Naturally multi-step, goal-directed | "Pay the electricity bill" = open bills → select payee → confirm amount → authorize |
| Needs a safety mechanism | Money-moving actions demand confirmation, allowlists, and limits |
| Maximises code reuse | `bank_transfer` task and sensitive-element modelling already exist |

---

## Assignment mapping (perceive → decide → act, + memory + safety)

| Assignment element | PrivacyPay realisation | Status / source |
|--------------------|------------------------|-----------------|
| Perceive input | Parse banking app UI (account screen, bill list, transfer form) | reuse `parser.py`, `android_xml.py` |
| Make decisions | Local partition → cloud reasons over masked blocks (ReAct) | reuse `agent.py`, `react.py`, `llm.py` |
| Take actions toward a goal | tap / input, executed through a confirmation gate | extend `android_live.py` executor |
| Memory | Episodic memory of payees / recurring bills, retrieved via RAG | reuse `memory.py` |
| Safety mechanisms | Confirmation before money-moving actions; payee allowlist; amount cap; dry-run default | NEW `safety.py` |

---

## Current State (v0.8) and the Gap

v0.8 is a *general* privacy-preserving GUI agent: 36 synthetic tasks across
many app categories, a multi-step ReAct loop, episodic memory + TF-IDF RAG, and
an ADB click executor limited to the Calculator package.

Gaps for the PrivacyPay vertical:

- No finance-specific task suite with realistic banking PII layouts.
- Sensitivity is hand-labelled in the data, not detected automatically.
- The executor supports only `click`, and only the Calculator package — it
  cannot enter an amount or a payee, and has no notion of a "risky" action.
- No safety policy: nothing stops the agent from authorising a transfer.
- Exposure is measured per-step only; there is no cumulative exposure across a
  multi-step financial flow.

---

## Target Components (v0.9)

### A. Finance task suite

- New `data/finance_tasks.json` plus generator `scripts/build_finance_tasks.py`.
- ~10 tasks across three flows:
  - **Pay bill** (open bill → select biller → confirm amount → authorise)
  - **Transfer to payee** (choose payee → enter amount → authorise)
  - **Check balance / statement** (read-only navigation)
- Every screen carries PII distractors — account numbers, balances, transaction
  rows, full payee lists — placed in separate layout blocks so collaborative
  mode can avoid uploading them.

### B. Automatic PII detection (deepen privacy)

- New `lc_private_gui/pii.py`: regex/heuristic detector for account numbers,
  IBAN, card numbers, monetary amounts, emails, phone numbers, and likely
  person names.
- Marks `UIElement.sensitive` automatically at parse / XML-convert time
  (opt-in flag), so sensitivity is derived, not hand-annotated.

### C. Safety policy gate (the headline safety mechanism)

- New `lc_private_gui/safety.py`: a `SafetyPolicy` that inspects a `Decision`
  before execution and returns `allow` / `require_confirmation` / `block`.
- Rules:
  - Money-moving actions (input into an amount field; click "Transfer", "Pay",
    "Send", "Confirm") require explicit confirmation.
  - Payee allowlist — block transfers to unknown recipients.
  - Amount cap — block / escalate transfers above a configured limit.
- Integrated into the executor path and recorded per step in the trajectory.

### D. Executor: add `input`

- Extend `execute_decision` to support `input` via `adb shell input text`,
  gated by the safety policy and the existing dry-run default.

### E. Cumulative exposure metric (deepen privacy)

- Track cumulative *unique* element / sensitive exposure across a whole
  trajectory (not just per-step averages), surfacing the multi-step privacy gap
  between collaborative and cloud-only modes.

### F. Evaluation

- Run the finance suite across collaborative / cloud-only / local-only modes
  (heuristic backend), record results, and write a v0.9 README changelog.
- Optional: OpenAI-backed run for a real-model comparison (needs `CLOUD_LLM_*`).

### Deferred to v1.0

- Reconstruction-attack evaluation: can the cloud reconstruct private financial
  facts (balance, spending) from what it was shown?

---

## File Map

```
lc_private_gui/
  pii.py             CREATE   automatic PII / sensitive-field detector
  safety.py          CREATE   SafetyPolicy gate (confirm / allowlist / cap)
  android_live.py    MODIFY   add input executor; route decisions through SafetyPolicy
  runner.py          MODIFY   record safety verdict + cumulative exposure per run
  metrics.py         MODIFY   cumulative unique exposure aggregation
  parser.py          MODIFY   optional auto-PII annotation hook
  android_xml.py     MODIFY   optional auto-PII annotation hook

data/
  finance_tasks.json CREATE   ~10 banking tasks with PII-rich layouts

scripts/
  build_finance_tasks.py CREATE  generator for the finance suite

README.md            MODIFY   v0.9.0 changelog + PrivacyPay positioning
```

---

## Build Order

`A → C → D → B → E → F`

Rationale: stand up the domain (A), then the headline safety mechanism (C) and
the execution it guards (D); these three form the demonstrable agent core.
Privacy depth (B, E) and evaluation (F) layer on top.

### Scope options under discussion

- **Full (A–F)** — complete milestone, largest change.
- **Core slice (A+C+D)** — finance tasks + safety gate + input execution; the
  demonstrable agent core, with B/E/F added after validation.
- **Safety-only (C)** — build the novel safety mechanism first against a few
  finance tasks, then expand.

---

## Version Tag

To be tagged **v0.9.0** in README.md once implemented.
