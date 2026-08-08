"""
gmail_auth.py — run this once, by hand, to authorize Gmail read access.

    python gmail_auth.py

See gmail_client.py for the full one-time setup steps (Google Cloud
project, OAuth consent screen, credentials.json) if you haven't done
those yet.
"""

import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_PATH = os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json")
TOKEN_PATH = os.environ.get("GMAIL_TOKEN_PATH", "token.json")

if __name__ == "__main__":
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"Missing {CREDENTIALS_PATH}.")
        print("Download it from Google Cloud Console first — see the setup")
        print("steps at the top of gmail_client.py.")
        raise SystemExit(1)

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    print(f"Authorized. Saved {TOKEN_PATH}.")
    print("The backend will use this automatically from now on.")
