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
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text.strip()
    return json.loads(raw)
