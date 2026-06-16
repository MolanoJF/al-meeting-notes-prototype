"""
Uploads a Word doc to Google Drive.
Prototype stand-in for Egnyte — swap this module for egnyte.py in production.
Requires: GOOGLE_DRIVE_FOLDER_ID and GOOGLE_CREDENTIALS_JSON env vars.
"""

import base64
import json
import os
import tempfile

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _get_drive_service():
    creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    if not creds_b64:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON env var not set")

    creds_json = base64.b64decode(creds_b64).decode("utf-8")
    creds_info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def upload_to_drive(local_path: str, meeting_title: str, date: str) -> str | None:
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id:
        print("[drive] GOOGLE_DRIVE_FOLDER_ID not set — skipping upload")
        return None

    try:
        service = _get_drive_service()
        file_name = f"{date} — {meeting_title}.docx"
        file_metadata = {
            "name": file_name,
            "parents": [folder_id],
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        media = MediaFileUpload(
            local_path,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        uploaded = service.files().create(body=file_metadata, media_body=media, fields="id,webViewLink").execute()
        url = uploaded.get("webViewLink", "")
        print(f"[drive] Uploaded: {file_name} → {url}")
        return url
    except Exception as e:
        print(f"[drive] Upload failed: {e}")
        return None
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)
