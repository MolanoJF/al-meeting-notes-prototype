import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from drive import upload_to_drive
from notion_utils import (
    extract_meeting_summary,
    fetch_meeting_page,
    mark_as_ingested,
    read_interaction_entry,
)
from word_gen import generate_word_doc


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("AL Meeting Notes service starting...")
    yield


app = FastAPI(title="AL Meeting Notes Automation", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "al-meeting-notes"}


# ---------------------------------------------------------------------------
# Core pipeline — triggered by webhook or manual demo
# ---------------------------------------------------------------------------

def process_interaction(interaction_page_id: str) -> dict:
    """
    Full pipeline for one INTERACTIONS DB entry:

    1. Read the entry — skip if already ingested or no meeting URL in Notes.
    2. Fetch the Notion meeting recording page from the URL in Notes.
    3. Parse Notion's AI summary into sections.
    4. Generate AL-branded Word doc.
    5. Upload to Google Drive.
    6. Mark the INTERACTIONS entry as Ingested + store Drive URL.
    """
    entry = read_interaction_entry(interaction_page_id)

    if entry["ingested"]:
        return {"status": "skipped", "reason": "already ingested"}

    meeting_page_id = entry["meeting_page_id"]
    if not meeting_page_id:
        return {
            "status": "skipped",
            "reason": "no Notion meeting URL found in Notes field",
        }

    meeting = fetch_meeting_page(meeting_page_id)

    summary_data = extract_meeting_summary(meeting["blocks"])

    if not summary_data["sections"] and not summary_data["action_items"]:
        return {
            "status": "skipped",
            "reason": "meeting page has no parseable summary yet — Notion may still be processing",
        }

    # Use the meeting recording page title if the INTERACTIONS entry title is blank
    title = entry["title"] or meeting["title"] or "Meeting Notes"

    meeting_meta = {
        "title": title,
        "date": entry["date"],
        "attendees": [],  # INTERACTIONS Person is a relation; names resolved separately
    }

    doc_path  = generate_word_doc(summary_data, meeting_meta)
    drive_url = upload_to_drive(doc_path, title, entry["date"])

    mark_as_ingested(interaction_page_id, drive_url)

    return {
        "status": "ingested",
        "meeting": title,
        "sections": len(summary_data["sections"]),
        "action_items": len(summary_data["action_items"]),
        "drive_url": drive_url,
    }


# ---------------------------------------------------------------------------
# Webhook — Notion fires this on page.created / page.properties_updated
# ---------------------------------------------------------------------------

@app.post("/webhook/notion")
async def webhook_notion(request: Request):
    body = await request.json()
    print(f"[webhook/notion] payload: {body}")

    # One-time verification handshake
    if "verification_token" in body:
        print(f"[webhook/notion] VERIFICATION TOKEN: {body['verification_token']}")
        return JSONResponse({"status": "verification_token_logged"})

    entity     = body.get("entity") or {}
    page_id    = entity.get("id") if entity.get("type") == "page" else None
    event_type = body.get("type", "")

    if not page_id:
        return JSONResponse({"status": "skipped", "reason": "no page entity in payload"})

    # We care about new pages and property updates (Notes URL may be added after creation)
    if event_type not in ("page.created", "page.properties_updated", "page.content_updated"):
        return JSONResponse({"status": "skipped", "reason": f"event type {event_type} not relevant"})

    try:
        return JSONResponse(process_interaction(page_id))
    except Exception as e:
        print(f"[webhook/notion] Skipping {page_id}: {e}")
        return JSONResponse({"status": "skipped", "page_id": page_id, "reason": str(e)})


# ---------------------------------------------------------------------------
# Manual demo trigger
# ---------------------------------------------------------------------------

@app.get("/demo/notion")
def demo_notion(page_id: str):
    """
    Manually trigger the pipeline for a specific INTERACTIONS DB entry.

    Pass the page ID of the INTERACTIONS entry (not the meeting recording page).
    Useful during development or if the webhook missed an event.
    """
    try:
        return process_interaction(page_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Granola fixture demo (kept for reference — does not use INTERACTIONS DB)
# ---------------------------------------------------------------------------

@app.get("/demo/granola")
def demo_granola():
    """
    Runs the old Granola fixture through the formatter.
    Uses skill.py (Claude) — kept for internal reference only.
    """
    from skill import format_meeting_notes

    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_transcript.json")
    with open(fixture_path) as f:
        fixture = json.load(f)

    formatted = format_meeting_notes(
        transcript=fixture["transcript"],
        attendees=fixture["attendees"],
        project=fixture.get("project", "AL — Fee Proposal Module 1"),
        date=fixture["date"],
        meeting_type=fixture.get("meeting_type", "client-facing"),
    )

    # Convert old Claude format → sections format for word_gen
    sections = []
    if formatted.get("summary"):
        sections.append({"heading": "Summary", "lines": [formatted["summary"]], "is_actions": False})
    if formatted.get("key_decisions"):
        sections.append({"heading": "Key Decisions", "lines": formatted["key_decisions"], "is_actions": False})
    if formatted.get("risks_flagged"):
        sections.append({"heading": "Open Questions / Risks", "lines": formatted["risks_flagged"], "is_actions": False})

    action_items = [
        {"who": a.get("who", ""), "what": a.get("what", ""), "by_when": a.get("by_when", "TBD")}
        for a in formatted.get("action_items", [])
    ]
    if action_items:
        sections.append({"heading": "Action Items", "lines": [], "is_actions": True})

    summary_data = {"sections": sections, "action_items": action_items}
    meeting_meta = {
        "title": fixture.get("title", fixture.get("project", "Meeting Notes")),
        "date": fixture["date"],
        "attendees": fixture.get("attendees", []),
    }

    doc_path  = generate_word_doc(summary_data, meeting_meta)
    drive_url = upload_to_drive(doc_path, fixture.get("title", "Meeting"), fixture["date"])

    return {
        "workflow": "Granola (fixture)",
        "meeting": meeting_meta["title"],
        "drive_url": drive_url,
    }
