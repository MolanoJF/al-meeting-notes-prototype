"""
Uploads a Word doc to Google Drive using OAuth user credentials.

Requires:
  GOOGLE_OAUTH_CLIENT_ID       — OAuth client ID
  GOOGLE_OAUTH_CLIENT_SECRET   — OAuth client secret
  GOOGLE_OAUTH_REFRESH_TOKEN   — long-lived refresh token
  GOOGLE_DRIVE_FOLDER_ID       — Drive folder ID to upload into
"""

import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _get_drive_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        token_uri=_TOKEN_URI,
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        scopes=_SCOPES,
    )
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
