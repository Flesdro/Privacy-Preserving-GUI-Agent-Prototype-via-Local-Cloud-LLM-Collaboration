# PrivacyPay Web Demo

A zero-dependency web demo of the PrivacyPay privacy-preserving banking agent.
A mock phone banking UI on the left, a live "privacy X-ray" in the middle, and
exposure meters plus a "what the cloud knows about you" panel on the right.

The decisions, exposure metrics, and safety verdicts are produced by the real
engine (`CollaborativeAgent` / `CloudOnlyAgent` + `SafetyPolicy`); only the
screen-to-screen transitions are scripted, because there is no live device.

## Run

From the prototype root:

```bash
python3 demo/server.py
```

Then open http://localhost:8000 in a browser. (Pass a port to override, e.g.
`python3 demo/server.py 8011`.)

No `pip install` is required — the server uses only the Python standard library.

## Backends (Engine toggle)

The page has an **Engine** toggle:

- **Real LLM** — the cloud decision runs against a real OpenAI-compatible model.
  The server reads `CLOUD_LLM_API_KEY`, `CLOUD_LLM_BASE_URL`, and
  `CLOUD_LLM_MODEL` from the prototype's `.env` (set `DEMO_LOCAL_BACKEND=ollama`
  to also route the local model through Ollama). The header badge shows the
  active model and the X-ray displays the model's real ReAct reasoning. If no
  credentials are configured it falls back to heuristic automatically.
- **Heuristic** — deterministic offline stand-in. Same privacy/safety mechanism,
  but reproducible and instant. Recommended when you need every demo beat (e.g.
  the confirmation gate on the bill-pay flow) to land identically every time.

Note: with the real model in PrivacyPay (collaborative) mode, the cloud sees only
a minimal block, so it occasionally scrolls or finishes instead of completing a
money action — the genuine privacy–utility trade-off. For a guaranteed clean
walk-through of the confirmation gate, use the Heuristic engine or the Cloud-only
mode; the blocked-transfer scenarios stop the action under both engines.

## What it shows

- **Phone (left):** the banking screen the agent perceives. The chosen target
  is outlined; elements sent to the cloud are tagged `▲ sent`.
- **Privacy X-ray (middle):** the exact payload the cloud received this step,
  with sensitive fields shown as `[MASKED_SENSITIVE]`, plus the agent's reasoning
  and the SafetyPolicy verdict (allow / needs confirmation / blocked).
- **Exposure (right):** per-step and cumulative UI exposure, and cumulative
  sensitive exposure.
- **What the cloud knows about you (right):** the sensitive items the cloud
  actually received, accumulated across the flow.

## Demo script (suggested beats)

1. **Scenario "Pay the electricity bill", mode = Cloud-only.** Step through.
   Watch the exposure bars jump to 100% and the "what the cloud knows" panel
   fill with the user's balances, payees, and transactions.
2. **Switch mode to PrivacyPay, same scenario.** Step through again. The cloud
   payload now contains only the target control; exposure stays low; the cloud
   "knows nothing". This is the core contrast.
3. **On the amount / confirm steps**, the SafetyPolicy holds the money-moving
   action as *needs confirmation* — click **Authorize payment** to proceed
   (human-in-the-loop safety).
4. **Scenario "Transfer to an unknown payee"** and **"Transfer $9,999"** — the
   SafetyPolicy blocks the action (payee allowlist / amount cap) before any
   money moves.

## Files

- `server.py` — standard-library HTTP server + JSON API (`/api/scenarios`, `/api/run`)
- `flows.py` — banking scenarios and the real-engine trace builder
- `index.html`, `style.css`, `app.js` — the frontend
