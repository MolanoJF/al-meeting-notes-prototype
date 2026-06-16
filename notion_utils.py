"""
Notion API helpers for Workflow B.
Reads meeting pages and writes formatted summaries back.
"""

import os

from notion_client import Client


def _client() -> Client:
    return Client(auth=os.environ["NOTION_API_KEY"])


def read_notion_page(page_id: str) -> dict:
    notion = _client()
    page = notion.pages.retrieve(page_id)
    blocks = notion.blocks.children.list(page_id)

    props = page.get("properties", {})

    title = ""
    if props.get("Name"):
        title_items = props["Name"].get("title", [])
        title = title_items[0]["text"]["content"] if title_items else "Untitled"

    date = ""
    if props.get("Date") and props["Date"].get("date"):
        date = props["Date"]["date"].get("start", "")

    attendees = []
    if props.get("Attendees"):
        attendees = [a["name"] for a in props["Attendees"].get("multi_select", [])]

    meeting_type = "internal"
    if props.get("Meeting type") and props["Meeting type"].get("select"):
        raw = props["Meeting type"]["select"].get("name", "internal")
        meeting_type = "client-facing" if "client" in raw.lower() else "internal"

    return {
        "title": title,
        "date": date,
        "attendees": attendees,
        "meeting_type": meeting_type,
        "blocks": blocks,
    }


def extract_transcript(blocks: dict) -> str:
    texts = []
    for block in blocks.get("results", []):
        btype = block.get("type", "")
        if btype in ("paragraph", "quote", "callout", "bulleted_list_item", "numbered_list_item"):
            rich = block.get(btype, {}).get("rich_text", [])
            line = "".join(r.get("plain_text", "") for r in rich)
            if line.strip():
                texts.append(line)
    return "\n".join(texts)


def write_summary_to_notion(page_id: str, formatted: dict):
    notion = _client()

    decisions_text = "\n".join(f"• {d}" for d in formatted.get("key_decisions", []))
    actions_lines = [
        f"• {a['who']} — {a['what']} (by {a['by_when']})"
        for a in formatted.get("action_items", [])
    ]
    actions_text = "\n".join(actions_lines)
    risks = formatted.get("risks_flagged", [])
    risks_text = "\n".join(f"• {r}" for r in risks) if risks else ""

    children = [
        {"type": "divider", "divider": {}},
        {
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "AL Formatted Summary"}}]
            },
        },
        _text_block("Summary", formatted.get("summary", "")),
        _text_block("Key Decisions", decisions_text),
        _text_block("Action Items", actions_text),
    ]

    if risks_text:
        children.append(_text_block("Open Questions / Risks", risks_text))

    next_mtg = formatted.get("next_meeting")
    if next_mtg:
        children.append(_text_block("Next Meeting", next_mtg))

    notion.blocks.children.append(page_id, children=children)


def _text_block(heading: str, body: str) -> dict:
    return {
        "type": "callout",
        "callout": {
            "rich_text": [
                {"type": "text", "text": {"content": f"{heading}\n{body}"}},
            ],
            "icon": {"type": "emoji", "emoji": "📋"},
            "color": "gray_background",
        },
    }
