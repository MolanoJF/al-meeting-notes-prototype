# AL Meeting Notes Automation

Prototype for Ackroyd Lowrie × Molior — automated meeting notes pipeline.

Two workflows, one shared formatting skill:

| Workflow | Trigger | Input | Claude's role |
|---|---|---|---|
| **A — Granola** | Render polls API every 5 min | Granola transcript | Context-aware formatting |
| **B — Notion** | Integration webhook (or manual trigger) | Notion AI Meeting Notes (transcript + summary) | Formatting only |

Both workflows produce a branded AL Word document saved to Google Drive (Egnyte in production).

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `POST` | `/format` | Format a transcript (shared, both workflows) |
| `GET` | `/demo/granola` | Trigger Workflow A with fixture transcript |
| `POST` | `/webhook/notion` | Workflow B — receives Notion integration webhook (events + verification handshake) |
| `GET` | `/demo/notion?page_id=...` | Workflow B — manual trigger fallback, defaults to the seeded demo page |

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
render.yaml          # Render deployment config
```
