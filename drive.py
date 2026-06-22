"""
Uploads a Word doc to Google Drive using a service account.

Requires:
  GOOGLE_SERVICE_ACCOUNT_JSON  — full service account JSON key as a string
  GOOGLE_DRIVE_FOLDER_ID       — Drive folder ID to upload into

AL shares the target Drive folder with the service account email (Editor).
No OAuth flow or user interaction required.
"""

import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _get_drive_service():
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_JSON env var")
    info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    return build("drive", "v3", credentials=creds)


def upload_to_drive(local_path: str, filename: str, folder_id: str | None = None) -> str | None:
    """
    Upload a DOCX to Google Drive.

    Args:
        local_path: absolute path to the local file
        filename:   name to use in Drive (include .docx extension)
        folder_id:  Drive folder ID; falls back to GOOGLE_DRIVE_FOLDER_ID env var

    Returns:
        webViewLink URL, or None if upload is skipped/failed
    """
    folder_id = folder_id or os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id:
        print("[drive] GOOGLE_DRIVE_FOLDER_ID not set — skipping upload")
        return None

    url = None
    try:
        service = _get_drive_service()
        file_metadata = {
            "name": filename,
            "parents": [folder_id],
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        media = MediaFileUpload(
            local_path,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        uploaded = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id,webViewLink")
            .execute()
        )
        url = uploaded.get("webViewLink", "")
        print(f"[drive] Uploaded: {filename} → {url}")
    except Exception as e:
        print(f"[drive] Upload failed: {e}")
    finally:
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except OSError:
            pass
    return url
