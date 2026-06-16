# Demo Script — AL Meeting Notes Automation

Run-of-show for presenting this to Ackroyd Lowrie. Two parts: explain the architecture from this repo, then run the live demo. Total time: ~12-15 minutes including questions.

---

## Before the call — 5 minutes prior

This is the part that prevents an awkward silence mid-demo. Do this every time, not just the first time.

1. **Wake the Render service up.** Free tier spins down after ~15 min idle — a cold start takes 30-50 seconds, which is dead air you don't want live. Hit this in a browser tab and wait for it to return:
   `https://al-meeting-notes.onrender.com/health`
   Expect: `{"status":"ok","service":"al-meeting-notes"}`

2. **Confirm the Notion demo page is clean.** Open the "Fee Proposal — Sprint 0 Kickoff" page in the "AL Meetings (Prototype)" database. It should show:
   - Just the transcript, no "AL Formatted Summary" section below it
   - `Status: Draft`
   If it's not clean (e.g., you tested it earlier today), reset it: delete the appended summary blocks, set Status back to Draft.

3. **Open these tabs, in this order, before you start talking:**
   - Tab 1: GitHub repo README (rendered) — `https://github.com/MolanoJF/al-meeting-notes-prototype`
   - Tab 2: Workflow A diagram PDF (open from the repo's `diagrams/` folder, or have it downloaded)
   - Tab 3: Workflow B diagram PDF
   - Tab 4: Render dashboard → this service → **Logs** tab
   - Tab 5: Notion → AL Meetings (Prototype) database, the demo page open
   - Tab 6: Google Drive → "AL Prototype — Meeting Notes" folder

4. **Have the Render logs tab visibly scrolling/live** before you start — don't fumble finding it mid-sentence.

---

## Part 1 — Explain the architecture (~5 min)

Present from the GitHub repo itself — this is deliberate. It signals "this is real code, not a deck."

**Open with the problem** (from the README's "What it does" section):
> "After every meeting, someone writes up what was decided, tracks who owns what, files it in the right folder, emails the actions. That's all manual today. This automates the whole thing — and I want to show you two different ways to trigger it, because the right one depends on a decision AL hasn't made yet: whether you're moving project management into Notion."

**Walk Workflow A diagram** (Granola):
- Point at the trigger: Granola already records the meeting automatically
- Point at Claude's box: this is where the unstructured transcript becomes structured — summary, decisions, action items with owners and dates
- Point at the output: branded Word doc, filed automatically
- Say the cost line: "Render's a few pounds a month, Claude's a fraction of a cent per meeting. This is not an infrastructure investment, it's a workflow change."

**Walk Workflow B diagram** (Notion):
- Key difference: Notion's own AI Meeting Notes feature already records and transcribes — so the trigger is instant, not a 5-minute poll
- Claude's job here is lighter — formatting, not extraction, since Notion's already done some structuring
- The output writes back into Notion itself, plus a Word doc for client-facing meetings

**State the actual tradeoff plainly** (this is the one thing they need to decide):
> "Workflow A keeps you on your current tools. Workflow B is simpler and instant, but only makes sense if you're committing to Notion as the project hub — which is the same conversation as the CMap migration. I'm not pushing either one today — I want to show you both working, so the decision is about your tools, not about whether the automation works."

---

## Part 2 — Live demo

### Demo 1: Workflow A (Granola path) — ~3 min

**Say:** "This fixture stands in for a real Granola transcript — we don't have Granola's Business plan yet for live API access, so I'm using a real meeting transcript from our own Sprint 0 kickoff to prove the pipeline."

1. Open a new tab, navigate to: `https://al-meeting-notes.onrender.com/demo/granola`
2. While it loads (a few seconds), narrate: "This is hitting the live service right now — reading the transcript, calling Claude to extract the structure, building the Word doc, uploading it."
3. The JSON response appears — point out: `summary`, `key_decisions`, `action_items` with WHO/WHAT/BY WHEN, `drive_url`
4. Switch to the Drive tab, refresh, open the new document
5. Scroll through it: "AL logo, AL fonts, structured sections, action items table. Nobody touched this document. It didn't exist sixty seconds ago."

### Demo 2: Workflow B (Notion path) — ~4 min

**Say:** "This one's the real thing, not a simulation — we don't have Notion's Business plan for auto-recording either, so I manually pasted this transcript into Notion exactly as Notion's AI Meeting Notes would have. But everything from here is live: a real webhook, firing in real time."

1. Switch to the Notion tab — show the clean demo page (transcript only, `Status: Draft`)
2. Change `Status` to `Ready` — **say it out loud as you do it**: "I'm just changing one field."
3. Immediately switch to the Render Logs tab: "Watch — this should appear in the next few seconds." Point at the incoming webhook payload as it lands.
4. Narrate the log lines as they appear: the page ID being read, Claude formatting, the Drive upload
5. Switch back to Notion, refresh the page: the formatted summary is now appended below the transcript, and `Status` has flipped to `Processed`
6. Switch to Drive: a second branded document has appeared

**If the webhook doesn't fire within ~15 seconds** (don't panic, don't apologize at length): say "Let me trigger this directly — same pipeline, just a manual nudge instead of waiting on the webhook," and open `https://al-meeting-notes.onrender.com/demo/notion` in a tab. Same result, zero visible difference to them. This is exactly why that endpoint exists — use it without drama.

---

## Closing — comparison and decision (~2 min)

Pull up the side-by-side table from the README or the diagrams. Say:

> "Both produce the exact same output. The only real difference is where the meeting record lives and how it's triggered. If you're committing to Notion as the project hub — which lines up with the CMap conversation — Workflow B is simpler and instant. If you want to stay on your current toolset for now, Workflow A works just as well, just with a five-minute delay instead of instant."

Then stop talking and let them ask questions. Don't pre-empt objections you haven't heard yet.

---

## What this requires of you, operationally

- **You are the one driving** — don't hand control to anyone else mid-demo, the tab choreography matters
- **Don't explain the code.** If asked "how is this built," the one-line answer is: "A small hosted service, Claude for the language understanding step, everything else is deterministic formatting." Don't go deeper unless they ask twice.
- **If Status doesn't flip Ready→Processed within ~20 seconds**, use the manual fallback (`/demo/notion`) without announcing it as a failure — just narrate it as "triggering it directly"
- **Reset the Notion demo page after the call** if you'll reuse it for another demo — see "Before the call" step 2

## If something actually breaks

- **Render returns 500 / error JSON**: switch immediately to the other workflow's demo — you have two independent paths, use that redundancy
- **Drive link missing (`drive_url: null`)**: not visible as an error to the audience — the JSON/Notion write-back still shows the extracted content. Don't draw attention to it; check env vars after the call
- **Notion webhook silent**: use `/demo/notion`, see above — this is the expected, planned-for path, not a scramble
