"""
Uploads a Word doc to Google Drive.
Prototype stand-in for Egnyte — swap this module for egnyte.py in production.

Uses OAuth2 user credentials (same Workspace account as the `gws` CLI),
not a service account — this puts uploads in the operator's actual Drive.
Requires: GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET,
GOOGLE_OAUTH_REFRESH_TOKEN, GOOGLE_DRIVE_FOLDER_ID env vars.
"""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def _get_drive_service():
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError(
            "Missing one of GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET / GOOGLE_OAUTH_REFRESH_TOKEN"
        )

    # No `scopes` passed here on purpose — this is an existing refresh token
    # (shared with the gws CLI) already bound to whatever scopes it was granted.
    # Requesting a different/narrower scope on refresh causes invalid_scope.
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    creds.refresh(Request())
    return build("drive", "v3", credentials=creds)


def upload_to_drive(local_path: str, meeting_title: str, date: str) -> str | None:
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id:
        print("[drive] GOOGLE_DRIVE_FOLDER_ID not set — skipping upload")
        return None

    url = None
    try:
        service = _get_drive_service()
        file_name = f"{date} - {meeting_title}.docx"
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
        print(f"[drive] Uploaded: {file_name} -> {url}")
    except Exception as e:
        print(f"[drive] Upload failed: {e}")
    finally:
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except OSError:
            pass  # file handle still released by OS; not worth failing the request over
    return url
