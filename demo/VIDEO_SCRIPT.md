# 2-Minute Demo Video Script — PrivacyPay

Target length **~2:00**. Left column = what you **do on screen**; right column =
what you **say** (read aloud). Total spoken text is ~290 words (~2 min at a calm pace).

**Before recording:** `python3 demo/server.py`, open `http://localhost:8000`,
zoom the browser so all three panels are visible, and have the Scenario set to
*"Pay the electricity bill"*.

---

### 0:00–0:15 — Hook + problem
**Do:** Show the demo page sitting on the bill-pay scenario; point at the phone.

> "This is PrivacyPay, a privacy-preserving banking agent. The problem it solves:
> a normal GUI agent uploads the *whole* screen to a cloud model to decide what to
> tap — and a banking screen is full of your balances, account numbers, and
> payees. Let me show you what that leaks, and how we fix it."

### 0:15–0:50 — The leak (cloud-only baseline)
**Do:** Set **Mode = Cloud-only**, click **Load flow**, then click **Step** three
times. Point at the exposure bars hitting 100% and the right-hand panel filling up.

> "First, the naive cloud-only agent. I step it through the bill payment. Watch the
> middle panel — every single element is uploaded to the cloud. The exposure meter
> hits one hundred percent, and on the right, 'what the cloud knows about you' fills
> up with your real balances, your saved payees, your transaction history. To pay
> one bill, the agent handed your entire financial life to the cloud."

### 0:50–1:30 — The fix (PrivacyPay)
**Do:** Switch **Mode = PrivacyPay**, click **Load flow**, **Step** through again.
Point at the masked payload and the near-empty right panel.

> "Now the same task with PrivacyPay. The device does the perception and
> partitioning locally, and sends the cloud only the one block it needs — with
> sensitive fields masked. Look: the cloud payload is a single button. Exposure
> stays low, and 'what the cloud knows' is empty. Same goal completed, but the
> cloud never saw your accounts or balances."

### 1:30–1:55 — Safety mechanism
**Do:** On a confirm step, point at the **Authorize** button. Then switch Scenario
to **"Transfer to an unknown payee"**, Load, Step → show the red **BLOCKED**.

> "There's also a safety layer. Any money-moving action pauses for human approval —
> here's the authorize gate. And if the agent tries to transfer to a payee that's
> not on your allowlist, or over your limit, the policy blocks it before any money
> moves."

### 1:55–2:00 — Close
**Do:** Briefly show the architecture diagram (or just say it over the demo).

> "Same capability, a fraction of the privacy exposure, with safety built in.
> That's PrivacyPay."

---

## Recording tips
- Use QuickTime (macOS): **File ▸ New Screen Recording**, capture the browser window.
- Do a silent dry run once so the click timing matches your narration.
- If 2:00 is tight, trim the safety section to just the BLOCKED shot.
- Keep the cursor moving to whatever you're describing — it guides the viewer's eye.
- Export at 1080p; upload to YouTube (unlisted) or Google Drive (link-shareable),
  then paste the link into `README.md` and the report.
