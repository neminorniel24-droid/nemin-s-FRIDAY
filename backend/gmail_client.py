"""
gmail_client.py — OAuth2 Gmail read access.

This is different from every other integration in this project: Gmail is
your private inbox, not public data, so Google requires an actual login +
consent flow (OAuth2), not just an API key. It's a one-time setup, done
once by hand, not something that happens automatically.

Setup (do this once, manually):

1. console.cloud.google.com — reuse the same project you made for YouTube,
   or create a new one.
2. APIs & Services -> Library -> search "Gmail API" -> Enable.
3. APIs & Services -> OAuth consent screen -> User Type: External ->
   fill in an app name (e.g. "Nemiii") and your own email as the support/
   developer contact -> Save. On the "Test users" step, add your own
   Google account email as a test user (required while the app is
   unpublished, which is fine for personal use).
4. APIs & Services -> Credentials -> Create Credentials -> OAuth client ID
   -> Application type: "Desktop app" -> Create. Download the JSON.
5. Save that downloaded file as backend/credentials.json.
   NEVER commit this file — it's in .gitignore already, double check.
6. Run once: python gmail_auth.py
   Opens a browser, you log in and grant read-only access. Saves
   backend/token.json (also gitignored) — the backend reuses this
   automatically after that, refreshing it as needed. You do NOT need to
   log in again unless you revoke access or delete token.json.

Scope used is read-only (gmail.readonly) — this can never send, delete,
or modify anything in your mailbox, only read it.
"""

from __future__ import annotations

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_PATH = os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json")
TOKEN_PATH = os.environ.get("GMAIL_TOKEN_PATH", "token.json")


def get_credentials():
    """Returns valid credentials, refreshing an expired token if needed.
    Returns None if never authorized — caller should say so, not crash."""
    if not os.path.exists(TOKEN_PATH):
        return None

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            return None
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        return creds

    return None


def get_service():
    creds = get_credentials()
    if not creds:
        return None
    return build("gmail", "v1", credentials=creds)
