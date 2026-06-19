"""
Claude Code skill: /format-meeting-notes
Formats a raw meeting transcript into structured AL output.
Called by both Workflow A (Granola) and Workflow B (Notion).
"""

import json
import os

import anthropic

SYSTEM_PROMPT = """You are an assistant for Ackroyd Lowrie Architects (AL), a London-based architecture firm.
Your job is to format meeting transcripts into clean, structured meeting notes that match AL's internal standards.

Output ONLY a valid JSON object — no markdown, no preamble. Schema:

{
  "summary": "2-3 sentence overview of the meeting purpose and outcome",
  "key_decisions": ["decision 1", "decision 2", ...],
  "action_items": [
    { "who": "First name", "what": "Clear action description", "by_when": "YYYY-MM-DD or 'TBD'" }
  ],
  "next_meeting": "YYYY-MM-DD or null",
  "risks_flagged": ["any risk or open question worth noting — omit array if none"]
}

Rules:
- Action items must be concrete and assignable. No vague items.
- Key decisions are facts agreed in the meeting, not opinions.
- Risks flagged: only include if genuinely raised in the transcript.
- If the meeting type is internal, tone is direct. If client-facing, tone is professional but warm.
- Do not invent information not present in the transcript."""


def format_meeting_notes(
    transcript: str,
    attendees: list[str],
    project: str,
    date: str,
    meeting_type: str = "internal",
) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_message = f"""Format the following meeting transcript into structured AL meeting notes.

Meeting details:
- Project: {project}
- Date: {date}
- Attendees: {", ".join(attendees)}
- Type: {meeting_type}

Transcript:
{transcript}"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    print(f"[skill] stop_reason={message.stop_reason} content_blocks={len(message.content)}")

    text_blocks = [b.text for b in message.content if getattr(b, "type", None) == "text"]
    raw = "".join(text_blocks).strip()
    print(f"[skill] raw_response (first 500 chars): {raw[:500]!r}")

    if not raw:
        raise RuntimeError(
            f"Claude returned no text content. stop_reason={message.stop_reason}, "
            f"content_types={[getattr(b, 'type', None) for b in message.content]}"
        )

    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Claude response was not valid JSON: {raw[:500]!r}") from e


_ENRICH_PROMPT = """You are a CRM assistant for Ackroyd Lowrie Architects (AL).
Given a meeting title and summary, extract structured CRM fields.
Output ONLY valid JSON — no markdown, no preamble.

Schema:
{
  "date": "YYYY-MM-DD — extract from the meeting title timestamp",
  "type": "Meeting",
  "stage": "<one of: Targeted | First Contact | Event | Lunch | Pitch | Feasibility | Won | Lost>",
  "crm_note": "<1-2 sentences capturing the purpose and key outcome, written for a CRM record>"
}

Stage guide:
- Targeted: prospect identified, no contact yet
- First Contact: very first meeting or intro call
- Event: met at an event (Breakfast Club, conference, etc.)
- Lunch: relationship-building lunch or social meeting
- Pitch: formal proposal or presentation was made
- Feasibility: feasibility study discussed or underway
- Won: project confirmed / contract signed
- Lost: prospect decided not to proceed"""


def enrich_interaction_fields(meeting_title: str, raw_summary: str) -> dict:
    """
    Extract CRM fields from a meeting title + summary.

    Returns:
        date      str  — YYYY-MM-DD
        type      str  — always "Meeting"
        stage     str  — inferred funnel stage
        crm_note  str  — 1-2 sentence CRM note
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_message = f"""Meeting title: {meeting_title}

Summary (first 3000 chars):
{raw_summary[:3000]}"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=_ENRICH_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    text_blocks = [b.text for b in message.content if getattr(b, "type", None) == "text"]
    raw = "".join(text_blocks).strip()
    print(f"[enrich] raw: {raw[:300]!r}")

    if raw.startswith("```"):
        raw = raw.strip("`").lstrip("json").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Enrich response was not valid JSON: {raw[:300]!r}") from e
