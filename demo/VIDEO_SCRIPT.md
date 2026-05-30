# 2-Minute Demo Video Script — PrivacyPay

Target length **~2:00**. Left column = what you **do on screen**; right column =
what you **say** (read aloud). Total spoken text is ~300 words (~2 min at a calm pace).

**Before recording:**
- `python3 demo/server.py`, open `http://localhost:8000`, zoom so all three
  panels are visible. Scenario = *"Pay the electricity bill"*.
- The header badge should read `cloud: OpenAI … · local: …`. For a smooth,
  every-beat-lands run, set **Engine = Heuristic** (deterministic). Keep the
  badge visible to prove the real backends are wired. *(Optional: do one extra
  take on Engine = Real LLM to show live GPT reasoning in the X-ray.)*

---

### 0:00–0:15 — Hook + problem
**Do:** Show the page; point at the header **backend badge**, then the phone.

> "This is PrivacyPay, a privacy-preserving banking agent. It runs a real cloud
> model and a local on-device model — you can see them in the badge here. The
> problem it solves: a normal GUI agent uploads the *whole* screen to the cloud to
> decide what to tap, and a banking screen is full of your balances and payees.
> Let me show you the leak, and the fix."

### 0:15–0:48 — The leak (cloud-only baseline)
**Do:** **Mode = Cloud-only**, **Load flow**, **Step** ×3. Point at the exposure
bars hitting 100% and the right panel filling up.

> "First, the naive cloud-only agent. As I step through the payment, watch the
> middle panel — every element is uploaded. The exposure meter hits one hundred
> percent, and on the right, 'what the cloud knows about you' fills up with your
> real balances, payees, and transactions. To pay one bill, it handed the cloud
> your entire financial life."

### 0:48–1:28 — The fix (PrivacyPay + on-device ranking)
**Do:** **Mode = PrivacyPay**, **Load flow**, **Step** through. Point first at the
**On-device block ranking** panel, then the masked payload, then the empty
right panel.

> "Now PrivacyPay. Here's the key part: the *on-device* model ranks the screen's
> blocks — you can see the ranking right here. It pushes the sensitive blocks down
> and only the top block is uploaded, with its fields masked. So the cloud receives
> a single control instead of the whole screen. Exposure stays low, the sensitive
> blocks are never sent, and 'what the cloud knows' stays empty. Same task done —
> the cloud never saw your accounts."

### 1:28–1:52 — Safety mechanism
**Do:** Point at the **Authorize** gate on a confirm step. Then Scenario =
**"Transfer to an unknown payee"**, **Load**, **Step** → red **BLOCKED**.

> "There's also a safety layer. Any money-moving action pauses for human approval —
> this authorize gate. And if the agent tries to pay a payee that's not on your
> allowlist, or over your limit, the policy blocks it before any money moves."

### 1:52–2:00 — Close
**Do:** Briefly show the badge / architecture again.

> "Real models, the full local–cloud loop, a fraction of the privacy exposure, with
> safety built in. That's PrivacyPay."

---

## Recording tips
- QuickTime (macOS): **File ▸ New Screen Recording**, capture the browser window.
- Do a silent dry run once so click timing matches your narration.
- The **on-device ranking** panel is the visual proof that the *local* model
  decides what gets uploaded — make sure it's in frame during the PrivacyPay part.
- **Engine = Heuristic** keeps every beat deterministic (sensitive blocks always
  stay un-uploaded; the confirm gate always fires). **Engine = Real LLM** shows
  live GPT reasoning in the X-ray but, with minimal context, may scroll/finish —
  use it for a short "real model" cutaway, not the main walkthrough.
- If 2:00 is tight, trim the safety section to just the BLOCKED shot.
- Keep the cursor on whatever you're describing. Export 1080p; upload to YouTube
  (unlisted) or Google Drive, then paste the link into `README.md` and the report.
