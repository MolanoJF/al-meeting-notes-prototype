# AL Meeting Notes Automation

Prototype for Ackroyd Lowrie × Molior — automated meeting notes pipeline.

Two workflows, one shared formatting skill:

| Workflow | Trigger | Input | Claude's role |
|---|---|---|---|
| **A — Granola** | Render polls API every 5 min | Granola transcript | Context-aware formatting |
| **B — Notion** | Instant webhook (Notion automation) | Notion AI Meeting Notes (transcript + summary) | Formatting only |

Both workflows produce a branded AL Word document saved to Google Drive (Egnyte in production).

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `POST` | `/format` | Format a transcript (shared, both workflows) |
| `GET` | `/demo/granola` | Trigger Workflow A with fixture transcript |
| `POST` | `/webhook/notion` | Workflow B — receives Notion automation webhook |

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
