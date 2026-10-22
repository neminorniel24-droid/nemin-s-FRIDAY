"""One-time Gmail sign-in. Needs backend/credentials.json from Google Cloud."""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from gmail_client import SCOPES

BASE = Path(__file__).resolve().parent
flow = InstalledAppFlow.from_client_secrets_file(str(BASE / "credentials.json"), SCOPES)
# open_browser=False: copy the printed link into your Windows browser.
creds = flow.run_local_server(port=8085, open_browser=False)
(BASE / "token.json").write_text(creds.to_json())
print("Gmail connected. token.json saved.")
