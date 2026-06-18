import base64
import json
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def build_flow(client_id: str, client_secret: str, redirect_uri: str) -> Flow:
    return Flow.from_client_config(
        {
            "web": {
                "client_id":     client_id,
                "client_secret": client_secret,
                "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                "token_uri":     "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )


def creds_from_json(creds_json: str) -> Credentials | None:
    """Load + auto-refresh credentials from a JSON string (stored in session)."""
    if not creds_json:
        return None
    try:
        creds = Credentials.from_authorized_user_info(json.loads(creds_json), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds if creds.valid else None
    except Exception:
        return None


def send_offer_email(
    creds_json: str,
    to_email: str,
    subject: str,
    body_text: str,
    pdf_bytes: bytes | None = None,
    pdf_filename: str = "offer_letter.pdf",
) -> tuple[bool, str]:
    creds = creds_from_json(creds_json)
    if not creds:
        return False, "Not authorized. Please connect your Gmail account first."

    service = build("gmail", "v1", credentials=creds)

    msg = MIMEMultipart()
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain"))

    if pdf_bytes:
        part = MIMEBase("application", "pdf")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{pdf_filename}"')
        msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return True, "Email sent successfully."
