"""
Uploads a Word doc to Google Drive using a Service Account.

Requires:
  GOOGLE_SERVICE_ACCOUNT_JSON  — full service account JSON (as string)
  GOOGLE_DRIVE_FOLDER_ID       — Drive folder ID to upload into
"""

import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

_SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_drive_service():
    sa_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=_SCOPES)
    return build("drive", "v3", credentials=creds)


def upload_to_drive(local_path: str, filename: str, folder_id: str | None = None) -> str | None:
    """
    Upload a DOCX to Google Drive.

    Returns webViewLink URL, or None if upload is skipped/failed.
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
            .create(
                body=file_metadata,
                media_body=media,
                fields="id,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
        url = uploaded.get("webViewLink", "")
        print(f"[drive] Uploaded: {filename} -> {url}")
    except Exception as e:
        print(f"[drive] Upload failed: {e}")
    finally:
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except OSError:
            pass
    return url
