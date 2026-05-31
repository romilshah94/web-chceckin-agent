"""Fetch flight booking PNRs from Gmail."""
import os
import re
import base64
import json
from pathlib import Path
from typing import Optional

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_FILE = Path(__file__).parent / "gmail_token.json"
CREDS_FILE = Path(__file__).parent / "gmail_credentials.json"

# PNR patterns: 6 alphanumeric chars, common in Indian airline bookings
PNR_PATTERN = re.compile(r"\b([A-Z0-9]{6})\b")

AIRLINE_KEYWORDS = {
    "indigo": ["indigo", "goindigo", "6e"],
    "air_india": ["air india", "airindia.com", "maharaja"],
    "air_india_express": ["air india express", "airindiaexpress", "ix "],
}


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print("  [!] Google API libraries not installed. Run: pip3 install google-api-python-client google-auth-oauthlib")
        return None

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                print(f"\n  [!] Gmail credentials file not found at: {CREDS_FILE}")
                print("      To enable Gmail PNR fetch:")
                print("      1. Go to Google Cloud Console → APIs & Services → Credentials")
                print("      2. Create OAuth 2.0 Client ID (Desktop app)")
                print(f"      3. Download and save as: {CREDS_FILE}")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())

    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=creds)


def _decode_body(payload) -> str:
    """Recursively extract text from email payload."""
    text = ""
    if payload.get("body", {}).get("data"):
        text += base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
    for part in payload.get("parts", []):
        text += _decode_body(part)
    return text


def _detect_airline(text: str) -> Optional[str]:
    lower = text.lower()
    for airline, keywords in AIRLINE_KEYWORDS.items():
        if any(k in lower for k in keywords):
            return airline
    return None


def _extract_pnr_candidates(text: str) -> list[str]:
    """Extract PNR-like tokens near keywords 'PNR', 'booking ref', 'booking id'."""
    candidates = []

    # Look for PNR near label keywords
    for match in re.finditer(
        r"(?:PNR|booking\s+(?:reference|ref|id|number|code))[^\w]*([A-Z0-9]{5,7})",
        text,
        re.IGNORECASE,
    ):
        candidates.append(match.group(1).upper())

    # Fallback: any 6-char alphanumeric token (common format)
    if not candidates:
        for m in PNR_PATTERN.finditer(text.upper()):
            tok = m.group(1)
            # Filter out pure numbers and obvious non-PNR tokens
            if re.search(r"[A-Z]", tok) and re.search(r"[0-9]", tok):
                candidates.append(tok)

    return list(dict.fromkeys(candidates))  # deduplicate, preserve order


def fetch_pnrs_from_gmail() -> list[dict]:
    """
    Search Gmail for flight booking emails and extract PNRs.
    Returns list of dicts: {pnr, airline, subject, date}
    """
    service = get_gmail_service()
    if not service:
        return []

    print("\n  Searching Gmail for flight booking emails...")

    query = (
        "subject:(booking confirmation OR e-ticket OR itinerary OR PNR) "
        "(indigo OR \"air india\" OR \"air india express\") "
        "newer_than:90d"
    )

    try:
        result = service.users().messages().list(userId="me", q=query, maxResults=20).execute()
        messages = result.get("messages", [])
    except Exception as e:
        print(f"  [!] Gmail search failed: {e}")
        return []

    found = []
    for msg in messages:
        try:
            full = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
            headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}
            subject = headers.get("Subject", "")
            date = headers.get("Date", "")
            body = _decode_body(full["payload"])
            full_text = subject + "\n" + body

            airline = _detect_airline(full_text)
            pnrs = _extract_pnr_candidates(full_text)

            for pnr in pnrs[:1]:  # take first/best PNR per email
                found.append({"pnr": pnr, "airline": airline, "subject": subject[:80], "date": date[:16]})
        except Exception:
            continue

    if found:
        print(f"  Found {len(found)} booking(s) in Gmail.")
    else:
        print("  No bookings found in Gmail (last 90 days).")

    return found
