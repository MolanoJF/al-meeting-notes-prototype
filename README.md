# AL Meeting Notes Automation

**A working prototype for Ackroyd Lowrie × Molior.**

Every AL meeting currently needs someone to write up what was decided, track who owns what action and by when, file a document in the right project folder, and share action items with attendees. This automates that, end to end — no one types up notes again.

This repo contains a real, deployed service. Two different ways to trigger it are demonstrated here — not slideware, not mockups. Both produce the same branded AL Word document automatically.

📊 **Diagrams:** [`diagrams/Workflow A — Granola-Native Pipeline.pdf`](diagrams/Workflow%20A%20%E2%80%94%20Granola-Native%20Pipeline.pdf) · [`diagrams/Workflow B — Notion-Native Pipeline.pdf`](diagrams/Workflow%20B%20%E2%80%94%20Notion-Native%20Pipeline.pdf)

🎬 **Presenting this?** See [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) for the full run-of-show.

---

## What it does

Two different triggers — a Granola recording, or a Notion meeting page — both flow into the same pipeline:

1. **Claude reads the transcript** and extracts what matters: a summary, the key decisions made, action items (who owns what, by when), risks worth flagging, and the next meeting date.
2. **A branded Word document is built automatically** — AL logo, AL fonts, AL formatting. No template to fill in by hand.
3. **The finished document lands in Drive** (Egnyte in production), named and filed automatically. For Workflow B, the same structured summary is also written back into the Notion page itself.

Nobody copies text across documents. Nobody formats anything. Nobody has to remember to do it.

---

## The two workflows

| | Workflow A — Granola | Workflow B — Notion |
|---|---|---|
| **Trigger** | Render polls Granola's API every 5 min | Notion fires a webhook the instant a meeting is marked ready |
| **Input** | Granola's auto-recorded transcript | Notion AI Meeting Notes — auto-recorded transcript + first-pass summary |
| **Claude's job** | Extract structure from a raw transcript, with project context injected from Supabase | Lighter — Notion's already done some of the structuring; Claude formats it to AL standard |
| **Where the record lives** | Egnyte only | Notion (source of truth) + Egnyte (client-facing docs) |
| **Best fit if…** | AL stays with its current toolset | AL commits to Notion as the project hub |

Full architecture, every step, in the [diagrams](diagrams/).

---

## See it live

| | |
|---|---|
| **Service** | `https://al-meeting-notes.onrender.com` |
| **Workflow A demo** | `GET /demo/granola` — runs the fixture transcript through the full pipeline |
| **Workflow B demo** | `GET /demo/notion` — runs the seeded Notion page through the full pipeline |
| **Workflow B live** | Flip `Status` → `Ready` on a page in the "AL Meetings (Prototype)" Notion database — the webhook does the rest, no manual trigger needed |

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `POST` | `/format` | Format a transcript (shared, both workflows) |
| `GET` | `/demo/granola` | Trigger Workflow A with fixture transcript |
| `POST` | `/webhook/notion` | Workflow B — receives Notion integration webhook (events + verification handshake) |
| `GET` | `/demo/notion?page_id=...` | Workflow B — manual trigger fallback, defaults to the seeded demo page |

---

## Local setup

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # fill in your keys
uvicorn main:app --reload
```

## Deploy to Render

Connect this repo in the Render dashboard. `render.yaml` handles the config.
Set all env vars in the Render dashboard (Environment tab) — they are marked `sync: false` intentionally.

## Env vars

See `.env.example` for the full list. Minimum to run `/demo/granola`:
- `ANTHROPIC_API_KEY`

Minimum to run `/webhook/notion`:
- `ANTHROPIC_API_KEY`
- `NOTION_API_KEY`
- `NOTION_MEETINGS_DB_ID`

Google Drive upload is optional — service degrades gracefully if `GOOGLE_DRIVE_FOLDER_ID` is not set.

Google Drive auth uses OAuth user credentials (same grant as the `gws` CLI) — `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN` — not a service account.

## Notion setup (Workflow B)

The "AL Meetings (Prototype)" database lives under the Ackroyd Lowrie client page in Notion.

**Note:** Notion's no-code "Automations" builder (Trigger → Send webhook) requires a Business plan. We don't have that, so we use **Integration Webhooks** instead — a separate, developer-facing feature configured in the integration's own settings, available regardless of workspace plan.

1. **Create a Notion integration token** at notion.so/my-integrations → "New integration" → internal → copy the secret → set as `NOTION_API_KEY` in Render. Then open the AL Meetings database in Notion → "..." menu → Connections → add the integration.
2. **Subscribe to webhooks**: in the integration's settings → Webhooks tab → add subscription → URL: `https://<your-render-url>/webhook/notion`. Notion sends a one-time `{"verification_token": "..."}` POST — `/webhook/notion` logs it (check Render logs), copy the token back into the Webhooks tab's Verify dialog to activate.
3. Once verified, subscribe to page/data source update events for the AL Meetings database.

**Fallback if webhook verification isn't done yet or flakes during the demo:** hit `GET /demo/notion` directly — it processes the seeded page exactly the same way, just triggered manually instead of by a live Notion event. Same output, same code path, zero risk during the presentation.

## Production swaps

| Prototype | Production |
|---|---|
| Fixture transcript (`fixtures/`) | Granola Business API |
| Manual Notion page + transcript | Notion AI Meeting Notes (Business plan) |
| Google Drive (`drive.py`) | Egnyte API (swap module, same interface) |
| `print()` email stub | SendGrid / Gmail SMTP |

## Structure

```
main.py              # FastAPI app — all endpoints
skill.py             # Claude formatting skill (shared)
word_gen.py          # python-docx AL branded document
drive.py             # Google Drive upload
notion_utils.py      # Notion API helpers (Workflow B)
fixtures/
  sample_transcript.json   # AL-flavored mock transcript
diagrams/
  Workflow A — Granola-Native Pipeline.pdf
  Workflow B — Notion-Native Pipeline.pdf
assets/
  al_logo.jpg         # extracted from AL's reference document, used in generated docs
render.yaml          # Render deployment config
DEMO_SCRIPT.md        # presentation run-of-show
```
