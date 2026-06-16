import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from drive import upload_to_drive
from notion_utils import extract_transcript, read_notion_page, write_summary_to_notion
from skill import format_meeting_notes
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
# Shared formatting endpoint — both workflows call this
# ---------------------------------------------------------------------------

@app.post("/format")
async def format_notes(request: Request):
    body = await request.json()
    required = ["transcript", "attendees", "project", "date"]
    missing = [k for k in required if not body.get(k)]
    if missing:
        raise HTTPException(400, f"Missing fields: {missing}")

    result = format_meeting_notes(
        transcript=body["transcript"],
        attendees=body["attendees"],
        project=body["project"],
        date=body["date"],
        meeting_type=body.get("meeting_type", "internal"),
    )
    return result


# ---------------------------------------------------------------------------
# Workflow A — Granola (demo: fixture transcript)
# ---------------------------------------------------------------------------

@app.get("/demo/granola")
def demo_granola():
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

    drive_url = None
    if fixture.get("meeting_type") == "client-facing":
        doc_path = generate_word_doc(formatted, fixture)
        drive_url = upload_to_drive(doc_path, fixture["title"], fixture["date"])

    return {
        "workflow": "A — Granola",
        "source": "fixture",
        "meeting": fixture["title"],
        "formatted": formatted,
        "drive_url": drive_url,
    }


# ---------------------------------------------------------------------------
# Workflow B — Notion webhook
# ---------------------------------------------------------------------------

@app.post("/webhook/notion")
async def webhook_notion(request: Request):
    body = await request.json()

    # Notion sends the page ID either at top level or nested under data
    page_id = body.get("page_id") or (body.get("data") or {}).get("id")
    if not page_id:
        raise HTTPException(400, "Missing page_id in webhook payload")

    page_data = read_notion_page(page_id)
    transcript = extract_transcript(page_data["blocks"])

    if not transcript.strip():
        return JSONResponse({"status": "skipped", "reason": "no transcript content found"})

    formatted = format_meeting_notes(
        transcript=transcript,
        attendees=page_data["attendees"],
        project=page_data["title"],
        date=page_data["date"],
        meeting_type=page_data["meeting_type"],
    )

    write_summary_to_notion(page_id, formatted)

    drive_url = None
    if page_data["meeting_type"] == "client-facing":
        doc_path = generate_word_doc(formatted, page_data)
        drive_url = upload_to_drive(doc_path, page_data["title"], page_data["date"])

    return {
        "workflow": "B — Notion",
        "status": "processed",
        "meeting": page_data["title"],
        "drive_url": drive_url,
    }
