# AL Meeting Notes Automation

**A Notion-native pipeline that turns a Notion AI meeting recording into a branded AL Word document — automatically.**

When a new meeting recording page appears in the AL Meetings database, the service wakes up, reads the Notion AI summary, runs it through Claude, builds a formatted DOCX using AL's branded template, uploads it to Google Drive, and writes the Drive link back into Notion. No one touches a template. No one copies text.

Live service: `https://al-meeting-notes.onrender.com`

---

## How it works

```
Notion AI records meeting
         │
         ▼
Notion Automation fires webhook → POST /webhook/notion
         │
         ▼
1.  Read Status — skip if already Processing or Done
2.  Mark Status = Processing
3.  Fetch the Notion AI meeting page (title + attendees + AI summary blocks)
4.  Render blocks to plain text the LLM can read
5.  Claude extracts metadata: project, meeting type, date, attendees, next meeting
6.  Claude structures sections: headings → numbered items, action items flagged with owner
7.  Assemble the full document data object
8.  Generate DOCX from AL branded template (assets/template.docx)
9.  Upload DOCX to Google Drive → get webViewLink
10. Mark Status = Done, write Drive URL to Document property
```

If anything in steps 3–10 fails: Status is set to `Error` and the error message is written to the `Notes` property on the Notion page.

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `GET` | `/webhook/notion` | Notion webhook verification handshake (returns 200 OK) |
| `POST` | `/webhook/notion` | Main webhook receiver — processes one meeting page |
| `GET` | `/manual?page_id=<id>` | Manually trigger the pipeline for a specific page |
| `GET` | `/manual?page_id=<id>&db_id=<id>` | Manual trigger with explicit database ID for tenant key lookup |

The `/manual` endpoint is the fallback for any page that slips through without a webhook event — it runs the exact same pipeline as the webhook path.

---

## File structure

```
main.py                  # FastAPI app — all endpoints + the 10-step pipeline
llm_pipeline.py          # Claude calls: extract_metadata() and structure_sections()
notion_utils.py          # Notion API helpers (fetch, render, status updates)
drive.py                 # Google Drive upload via OAuth user credentials
scripts/
  generate_docx.py       # Fill AL branded template with meeting data → .docx
assets/
  template.docx          # AL branded Word template (3 tables: header, content, actions)
  al_logo.jpg            # AL logo (embedded in generated documents)
render.yaml              # Render deployment config
requirements.txt
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `NOTION_TENANTS` | Yes | JSON map of database IDs → tenant credentials (see below) |
| `GOOGLE_DRIVE_FOLDER_ID` | No | Drive folder to upload docs into — service skips upload if unset |
| `GOOGLE_OAUTH_CLIENT_ID` | No* | OAuth client ID for Drive |
| `GOOGLE_OAUTH_CLIENT_SECRET` | No* | OAuth client secret for Drive |
| `GOOGLE_OAUTH_REFRESH_TOKEN` | No* | Long-lived refresh token for Drive |

*Required only if `GOOGLE_DRIVE_FOLDER_ID` is set.

### NOTION_TENANTS format

Each key is a database ID **with dashes removed**. Each value is the Notion integration secret for that database and an optional display name:

```json
{
  "387b251472b3801d965cf4ca3be355a0": {
    "api_key": "secret_xxxxxxxxxxxx",
    "name": "Ackroyd Lowrie"
  }
}
```

Multiple tenants (multiple Notion workspaces or databases) can be added to the same JSON object. When a webhook fires, the service reads the page's parent database ID and looks it up in this map to get the right API key.

---

## Deploying to Render

Connect this repo in the Render dashboard. `render.yaml` handles the configuration.

Set all environment variables in the Render dashboard under **Environment** — they are intentionally marked `sync: false` (not stored in the repo). The service starts with:

```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## Onboarding a new user / tenant

Follow these steps each time a new Notion workspace or database needs to be connected.

### Step 1 — Notion database setup

The database that holds meeting recording pages needs four properties:

| Property | Type | Purpose |
|---|---|---|
| `Name` (or `Title`) | Title | Page name — auto-set by Notion AI |
| `Status` | Select | Pipeline tracks state here: `Processing`, `Done`, `Error` |
| `Document` | URL | Drive link written back when processing completes |
| `Notes` | Rich text | Error messages written here if the pipeline fails |

Add the select options `Processing`, `Done`, `Error` to the `Status` property.

### Step 2 — Create a Notion integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations) → **New integration**.
2. Scope: Internal. No user information needed.
3. Copy the **Internal Integration Secret** — this is the `api_key` for `NOTION_TENANTS`.
4. Open the AL Meetings database in Notion → click `...` → **Connections** → add the new integration.

### Step 3 — Get the database ID

Open the database in Notion. The URL looks like:

```
https://www.notion.so/<workspace>/<database_id>?v=<view_id>
```

Copy the `<database_id>` segment (32 hex characters with dashes). Remove the dashes — that is the key used in `NOTION_TENANTS`.

### Step 4 — Add to NOTION_TENANTS

In Render → Environment, update `NOTION_TENANTS` to include the new tenant:

```json
{
  "existing_db_id_no_dashes": { "api_key": "secret_existing", "name": "Existing Client" },
  "new_db_id_no_dashes":      { "api_key": "secret_new",      "name": "New Client" }
}
```

Render will redeploy automatically.

### Step 5 — Set up Notion Automation

Notion Automations (no-code, available on free plans via the Automations tab in the database view) fire the webhook when a new page is created by Notion AI.

1. Open the database → **Automations** tab → **+ New automation**.
2. Trigger: **Page added to database**.
3. Action: **Send a webhook** → URL: `https://al-meeting-notes.onrender.com/webhook/notion`.
4. Save and enable the automation.

> **Note:** This uses Notion's built-in no-code Automations, not Integration Webhooks. No verification token is required — the POST goes directly to the service.

### Step 6 — Test it

Either create a real meeting in Notion (let Notion AI process it, wait ~2 min, then check Status) or trigger manually:

```
GET https://al-meeting-notes.onrender.com/manual?page_id=<page_id>&db_id=<db_id>
```

`page_id` is the 32-char hex ID of a specific meeting page (from its URL). `db_id` is the database ID with or without dashes. If `db_id` is omitted, the service falls back to the first matching API key in `NOTION_TENANTS`.

---

## Google Drive setup (optional)

Drive upload is optional — the service degrades gracefully if the Drive credentials are not set (the DOCX is generated but not saved anywhere persistent, and `drive_url` in the response will be `null`).

To enable:

1. Create an OAuth 2.0 Client ID in Google Cloud Console (Desktop app type).
2. Run the OAuth consent flow once locally to obtain a refresh token — use the same Google account that owns the target Drive folder. The `gws` CLI or any standard OAuth desktop flow works.
3. Set `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN` in Render.
4. Set `GOOGLE_DRIVE_FOLDER_ID` to the folder ID from the Drive URL (`https://drive.google.com/drive/folders/<folder_id>`).

---

## Production swaps

| Prototype | Production |
|---|---|
| Google Drive (`drive.py`) | Egnyte API — swap the module, same `upload_to_drive(local_path, filename)` interface |
| Claude Haiku | Can upgrade to a more capable model in `llm_pipeline.py → _MODEL` |

---

## Troubleshooting

**Status stuck on Processing** — the pipeline crashed before it could write Error. Check Render logs for the page ID. Use `/manual?page_id=...` to retry once the underlying issue is fixed — the pipeline checks status at the start and will re-run since the page never reached Done.

**Status = Error, Notes says "Meeting page has no summary blocks"** — Notion AI was still generating when the webhook fired. Wait a minute and hit `/manual?page_id=...` to retry.

**Webhook not firing** — confirm the Automation is enabled and the integration has access to the database. Check Render logs for incoming POST requests to `/webhook/notion`.

**Drive upload failing** — the OAuth refresh token may have expired. Re-run the OAuth consent flow and update `GOOGLE_OAUTH_REFRESH_TOKEN` in Render. Drive errors do not fail the pipeline — Status is still set to Done, just without a Document URL.
