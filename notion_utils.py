"""
Notion API helpers for the INTERACTIONS DB pipeline.

Trigger: new (or updated) entry in the INTERACTIONS DB where the Notes field
         contains a Notion meeting recording URL.

Flow:
  1. read_interaction_entry(page_id)   — read INTERACTIONS entry, extract metadata
  2. fetch_meeting_page(page_id)       — fetch the recording page, return blocks
  3. extract_meeting_summary(blocks)   — parse blocks into sections
  4. mark_as_ingested(page_id, url)    — set Ingested ✓ and Drive URL on entry
"""

import os
import re

from notion_client import Client

INTERACTIONS_DB_ID = "71a88748f95e4bd89e4bf8d6eec1b7c2"

# Matches notion.so and notion.com page URLs; captures the 32-char hex page ID.
_NOTION_URL_RE = re.compile(
    r"https://(?:www\.)?notion\.(?:so|com)/(?:[a-zA-Z0-9%-]+-)?([a-f0-9]{32})"
)


def _client() -> Client:
    return Client(auth=os.environ["NOTION_API_KEY"])


def _norm(uid: str) -> str:
    return uid.replace("-", "")


# ---------------------------------------------------------------------------
# Read INTERACTIONS entry
# ---------------------------------------------------------------------------

def read_interaction_entry(page_id: str) -> dict:
    """
    Read a page from the INTERACTIONS DB.

    Returns:
        title           str  — entry title (Interaction property)
        date            str  — ISO date string or ""
        interaction_type str — e.g. "Meeting", "Call"
        notes           str  — raw text of the Notes field
        meeting_page_id str | None — 32-char hex ID parsed from a Notion URL in Notes
        ingested        bool — whether already processed
    """
    notion = _client()
    page = notion.pages.retrieve(page_id)

    parent = page.get("parent", {})
    parent_db = _norm(parent.get("database_id", ""))
    if parent_db != _norm(INTERACTIONS_DB_ID):
        raise ValueError(
            f"Page {page_id} is not in the INTERACTIONS DB (parent: {parent})"
        )

    props = page.get("properties", {})

    # Title
    title = ""
    for rt in (props.get("Interaction") or {}).get("title", []):
        title += rt.get("plain_text", "")

    # Date
    date = ""
    date_prop = props.get("Date", {})
    if date_prop.get("date"):
        date = date_prop["date"].get("start", "")

    # Type
    interaction_type = ""
    type_prop = props.get("Type", {})
    if type_prop.get("select"):
        interaction_type = type_prop["select"].get("name", "")

    # Notes (rich_text)
    notes = ""
    for rt in (props.get("Notes") or {}).get("rich_text", []):
        notes += rt.get("plain_text", "")

    # Ingested flag
    ingested = (props.get("Ingested") or {}).get("checkbox", False)

    # Parse meeting recording URL out of Notes
    meeting_page_id = None
    m = _NOTION_URL_RE.search(notes)
    if m:
        meeting_page_id = m.group(1)

    return {
        "title": title,
        "date": date,
        "interaction_type": interaction_type,
        "notes": notes,
        "meeting_page_id": meeting_page_id,
        "ingested": ingested,
    }


# ---------------------------------------------------------------------------
# Fetch meeting recording page
# ---------------------------------------------------------------------------

def _blocks_flat(notion: Client, block_id: str, depth: int = 0) -> list:
    """Recursively fetch all child blocks (plain — no meeting_notes special-casing)."""
    if depth > 4:
        return []
    blocks = []
    cursor = None
    while True:
        kw = {"block_id": block_id}
        if cursor:
            kw["start_cursor"] = cursor
        resp = notion.blocks.children.list(**kw)
        for block in resp.get("results", []):
            blocks.append(block)
            if block.get("has_children"):
                blocks.extend(_blocks_flat(notion, block["id"], depth + 1))
        if not resp.get("has_more"):
            break
        cursor = resp["next_cursor"]
    return blocks


def _summary_blocks_from_meeting_notes(notion: Client, meeting_notes_block_id: str) -> list:
    """
    Return only the AI summary child blocks of a meeting_notes block.

    Notion meeting recording pages have three children under the meeting_notes
    block: (1) AI summary, (2) notes, (3) transcript. We only want (1).
    """
    resp = notion.blocks.children.list(block_id=meeting_notes_block_id)
    children = resp.get("results", [])
    if not children:
        return []
    summary_block = children[0]          # first child = AI summary section
    blocks = [summary_block]
    if summary_block.get("has_children"):
        blocks.extend(_blocks_flat(notion, summary_block["id"]))
    return blocks


def fetch_meeting_page(page_id: str) -> dict:
    """
    Fetch a Notion meeting recording page.
    Only the AI-generated summary section is extracted — not notes or transcript.

    Returns:
        title  str  — page title
        blocks list — summary blocks only
    """
    notion = _client()
    page = notion.pages.retrieve(page_id)

    props = page.get("properties", {})
    title = ""
    for _key, prop in props.items():
        if prop.get("type") == "title":
            for rt in prop.get("title", []):
                title += rt.get("plain_text", "")
            break

    # Walk top-level blocks; for meeting_notes blocks, only descend into summary
    top = notion.blocks.children.list(block_id=page_id)
    all_blocks: list = []
    for block in top.get("results", []):
        btype = block.get("type", "")
        all_blocks.append(block)
        if btype == "meeting_notes" and block.get("has_children"):
            all_blocks.extend(_summary_blocks_from_meeting_notes(notion, block["id"]))
        elif block.get("has_children"):
            all_blocks.extend(_blocks_flat(notion, block["id"]))

    return {"title": title, "blocks": all_blocks}


# ---------------------------------------------------------------------------
# Parse blocks → sections
# ---------------------------------------------------------------------------

_HEADING_TYPES = {"heading_1", "heading_2", "heading_3"}
_CONTENT_TYPES = {
    "paragraph", "bulleted_list_item", "numbered_list_item",
    "quote", "callout",
}
_ACTION_KEYWORDS = {"action item", "action", "follow-up", "follow up", "next step"}


def _rt_to_str(rich_text: list) -> str:
    return "".join(r.get("plain_text", "") for r in rich_text).strip()


def extract_meeting_summary(blocks: list) -> dict:
    """
    Parse a flat list of Notion blocks into structured sections.

    Returns:
        sections     list[dict]  — [{"heading": str, "lines": [str], "is_actions": bool}]
        action_items list[dict]  — [{"who": str, "what": str, "by_when": str}]
        raw_summary  str         — full text of first/largest section (fallback for title doc)
    """
    sections: list[dict] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    past_action_items = False

    def flush():
        nonlocal current_heading, current_lines, past_action_items
        if current_heading and current_lines:
            is_actions = any(kw in current_heading.lower() for kw in _ACTION_KEYWORDS)
            if is_actions:
                past_action_items = True
            sections.append({
                "heading": current_heading,
                "lines": list(current_lines),
                "is_actions": is_actions,
            })
        current_heading = None
        current_lines = []

    for block in blocks:
        btype = block.get("type", "")

        if btype in _HEADING_TYPES:
            flush()
            # First heading after action items = start of notes/transcript — stop.
            if past_action_items:
                break
            text = _rt_to_str(block.get(btype, {}).get("rich_text", []))
            if text:
                current_heading = text

        elif btype in _CONTENT_TYPES:
            # Skip paragraphs/bullets under an action items heading — transcript
            # bleeds in as paragraph blocks directly after the to_do items.
            if current_heading is not None and any(
                kw in current_heading.lower() for kw in _ACTION_KEYWORDS
            ):
                continue
            text = _rt_to_str(block.get(btype, {}).get("rich_text", []))
            if text and current_heading is not None:
                current_lines.append(text)

        elif btype == "to_do":
            # Once we're past action items, stop — no more to_do blocks expected.
            if past_action_items:
                break
            text = _rt_to_str(block.get("to_do", {}).get("rich_text", []))
            if text:
                if current_heading is None:
                    current_heading = "Action Items"
                current_lines.append(text)

    flush()

    # Build action items from sections flagged as_actions
    action_items: list[dict] = []
    for sec in sections:
        if not sec["is_actions"]:
            continue
        for line in sec["lines"]:
            # Common Notion format: "Person to do something"
            # Split on " to " (first occurrence) to get who/what
            parts = re.split(r"\s+to\s+", line, maxsplit=1)
            if len(parts) == 2:
                action_items.append({"who": parts[0].strip(), "what": parts[1].strip(), "by_when": "TBD"})
            else:
                action_items.append({"who": "", "what": line, "by_when": "TBD"})

    # Fallback summary: join all non-action section lines
    raw_summary = "\n\n".join(
        f"{sec['heading']}\n" + "\n".join(sec["lines"])
        for sec in sections
        if not sec["is_actions"]
    )

    return {
        "sections": sections,
        "action_items": action_items,
        "raw_summary": raw_summary,
    }


# ---------------------------------------------------------------------------
# Write-back
# ---------------------------------------------------------------------------

def mark_as_ingested(page_id: str, drive_url: str | None = None):
    """Set Ingested = ✓ (and optionally Drive URL) on an INTERACTIONS entry."""
    notion = _client()
    properties: dict = {"Ingested": {"checkbox": True}}
    if drive_url:
        properties["Drive URL"] = {"url": drive_url}
    notion.pages.update(page_id, properties=properties)


def update_interaction_fields(page_id: str, fields: dict):
    """
    Write enriched CRM fields back to an INTERACTIONS entry.

    fields keys (all optional):
        date      str  — YYYY-MM-DD
        type      str  — must match a Type select option
        stage     str  — must match a Stage at Time select option
        crm_note  str  — text for the Notes field
    """
    notion = _client()
    properties: dict = {}

    if fields.get("date"):
        properties["Date"] = {"date": {"start": fields["date"]}}

    if fields.get("type"):
        properties["Type"] = {"select": {"name": fields["type"]}}

    if fields.get("stage"):
        properties["Stage at Time"] = {"select": {"name": fields["stage"]}}

    if fields.get("crm_note"):
        properties["Notes"] = {
            "rich_text": [{"type": "text", "text": {"content": fields["crm_note"]}}]
        }

    if properties:
        notion.pages.update(page_id, properties=properties)
