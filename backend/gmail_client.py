"""Read-only Gmail. Run `python gmail_auth.py` once to sign in."""
from pathlib import Path

BASE = Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token = BASE / "token.json"
    if not token.exists():
        raise RuntimeError("Gmail isn't signed in yet. Run: python gmail_auth.py")
    creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token.write_text(creds.to_json())
    if not creds.valid:
        raise RuntimeError("Gmail sign-in expired. Run: python gmail_auth.py")
    return creds


def unread(limit: int = 5) -> tuple[int, list[dict]]:
    from googleapiclient.discovery import build

    svc = build("gmail", "v1", credentials=_credentials(), cache_discovery=False)
    res = svc.users().messages().list(userId="me", q="is:unread in:inbox", maxResults=limit).execute()
    total = res.get("resultSizeEstimate", 0)
    out = []
    for m in res.get("messages", []):
        msg = svc.users().messages().get(userId="me", id=m["id"], format="metadata",
                                         metadataHeaders=["From", "Subject"]).execute()
        h = {x["name"]: x["value"] for x in msg["payload"]["headers"]}
        sender = h.get("From", "someone").split("<")[0].strip().strip('"') or "someone"
        out.append({"from": sender, "subject": h.get("Subject", "(no subject)")})
    return total, out
