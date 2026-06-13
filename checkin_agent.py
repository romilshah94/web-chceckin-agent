#!/usr/bin/env python3
"""
India Domestic Airline Web Check-in Agent
Supports: IndiGo, Air India, Air India Express

Features:
  - Fetches PNR from Gmail or accepts manual input
  - Loads frequent flyer numbers from preferences.json
  - Auto-selects aisle seat; prompts user if none available

PREFERRED EXECUTION (when running via Claude/AI assistant):
  Use the Claude Chrome browser extension (MCP: mcp__Claude_in_Chrome__*) to drive check-in
  in the user's existing Chrome browser. Do NOT launch a new Playwright browser unless the
  Chrome extension is unavailable. This avoids cookie/session issues and is faster.

PNR NOTE — Corporate bookings (Amex GBT / travel desk):
  The booking confirmation email contains TWO reference numbers:
    - Trip/booking ref (e.g. GWW3J6) — this is the TRAVEL AGENCY ref, NOT usable on airline site
    - Airline confirmation number (e.g. QD929E under "CONFIRMATION NO.") — use THIS as PNR
  The gmail_fetcher tries to extract PNRs automatically; for corporate bookings always verify
  against the "CONFIRMATION NO." field in the email.
"""
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional

LAST_NAME = "Shah"
PREFS_FILE = Path(__file__).parent / "preferences.json"

# Private GitHub repo storing preferences.json
# Set GITHUB_TOKEN env var or store in .env to enable remote fetch.
PREFS_REPO = "romilshah94/checkin-prefs"
PREFS_REMOTE_URL = f"https://api.github.com/repos/{PREFS_REPO}/contents/preferences.json"


def load_preferences() -> dict:
    """Load preferences: tries remote private repo first, falls back to local file."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        try:
            import urllib.request
            req = urllib.request.Request(
                PREFS_REMOTE_URL,
                headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.raw"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                prefs = json.loads(resp.read().decode())
                print("  Preferences loaded from private GitHub repo.")
                # Cache locally for offline use
                PREFS_FILE.write_text(json.dumps(prefs, indent=2))
                return prefs
        except Exception as e:
            print(f"  [!] Remote preferences fetch failed: {e}. Falling back to local file.")

    if PREFS_FILE.exists():
        try:
            prefs = json.loads(PREFS_FILE.read_text())
            print("  Preferences loaded from local file.")
            return prefs
        except Exception as e:
            print(f"  [!] Could not load preferences.json: {e}")

    print("  [!] No preferences found. Set GITHUB_TOKEN env var or create preferences.json.")
    return {}

AIRLINES = {
    "1": ("indigo", "IndiGo"),
    "2": ("air_india", "Air India"),
    "3": ("air_india_express", "Air India Express"),
}

AIRLINE_MODULES = {
    "indigo": "airlines.indigo",
    "air_india": "airlines.air_india",
    "air_india_express": "airlines.air_india_express",
}


def pick_airline_interactive() -> tuple[str, str]:
    print("\nSelect airline:")
    for k, (code, name) in AIRLINES.items():
        print(f"  {k}. {name}")
    print("  4. Auto-detect (from PNR prefix or email)")
    choice = input("\nEnter choice [1-4]: ").strip()
    if choice in AIRLINES:
        return AIRLINES[choice]
    return ("auto", "Auto-detect")


def detect_airline_from_pnr(pnr: str) -> Optional[str]:
    """Rough heuristic: IndiGo PNRs often start with digits, AI with letters."""
    pnr = pnr.upper()
    # IndiGo PNRs are typically all-numeric or start with digits
    if pnr[:2].isdigit():
        return "indigo"
    # Air India Express often IX prefix in ticket, PNR may start with certain letters
    # Air India typically starts with AI
    # These are approximate — airline must be confirmed by user when ambiguous
    return None


def get_pnr_interactive(gmail_pnrs: list[dict]) -> tuple[str, str]:
    """Return (pnr, airline_code)."""
    if gmail_pnrs:
        print("\nBookings found in Gmail:")
        for i, b in enumerate(gmail_pnrs, 1):
            airline_label = b.get("airline") or "unknown airline"
            print(f"  {i}. PNR: {b['pnr']}  |  {airline_label}  |  {b['subject'][:60]}")
        print(f"  {len(gmail_pnrs)+1}. Enter PNR manually")
        choice = input(f"\nSelect booking [1-{len(gmail_pnrs)+1}]: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(gmail_pnrs):
                b = gmail_pnrs[idx]
                return b["pnr"], b.get("airline") or "auto"
        except ValueError:
            pass

    pnr = input("\nEnter PNR / Booking Reference: ").strip().upper()
    if not pnr:
        print("No PNR entered. Exiting.")
        sys.exit(1)
    return pnr, "auto"



def _save_boarding_pass(page, pnr: str, airline_code: str = "unknown"):
    """Screenshot the boarding pass page and import to Photos."""
    try:
        from boarding_pass_saver import capture_and_save
        capture_and_save(page, pnr, airline_code)
    except Exception as e:
        print(f"  [BoardingPass] Could not save: {e}")


def run_checkin(pnr: str, airline_code: str, last_name: str, headless: bool = False):
    from playwright.sync_api import sync_playwright
    import importlib

    prefs = load_preferences()
    ff_info = prefs.get("frequent_flyer", {}).get(airline_code, {})
    seat_pref = prefs.get("seat_preference", {}).get("type", "aisle")

    print(f"\n  Preferences loaded:")
    print(f"    Seat preference : {seat_pref} (fallback: prompt)")
    if ff_info:
        print(f"    Frequent flyer  : {ff_info.get('program')} — {ff_info.get('number')}")

    if airline_code == "auto" or airline_code not in AIRLINE_MODULES:
        detected = detect_airline_from_pnr(pnr)
        if detected:
            print(f"\n  Auto-detected airline: {detected}")
            airline_code = detected
        else:
            print("\nCould not auto-detect airline from PNR.")
            _, airline_code = pick_airline_interactive()

    module = importlib.import_module(AIRLINE_MODULES[airline_code])

    print(f"\n  Launching browser (headless={headless})...")
    import shutil, tempfile
    # Copy Chrome cookies to a temp profile so the IndiGo micro-frontend loads
    tmp_profile = "/tmp/chrome_tmp_profile"
    shutil.rmtree(tmp_profile, ignore_errors=True)
    os.makedirs(f"{tmp_profile}/Default", exist_ok=True)
    chrome_cookies = (
        "/Users/romilshah/Library/Application Support/Google/Chrome/Default/Cookies"
    )
    if os.path.exists(chrome_cookies):
        shutil.copy2(chrome_cookies, f"{tmp_profile}/Default/Cookies")
        print("  Using Chrome cookies for session continuity.")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=tmp_profile,
            channel="chrome",
            headless=headless,
            slow_mo=200,
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )
        page = context.new_page()

        success = module.checkin(page, pnr, last_name, prefs)

        if success:
            print("\n  Check-in flow complete.")
            _save_boarding_pass(page, pnr, airline_code)
            if not headless:
                print("  Browser will stay open for 3 minutes. Close it manually when done.")
                page.wait_for_timeout(180000)
        else:
            print("\n  Check-in could not be completed automatically.")
            # Always take a screenshot of the current state for inspection
            _save_boarding_pass(page, pnr, airline_code)
            if not headless:
                print("  The browser will stay open for 60s so you can complete it manually.")
                page.wait_for_timeout(60000)

        context.close()


def main():
    parser = argparse.ArgumentParser(description="India Domestic Airline Web Check-in Agent")
    parser.add_argument("--pnr", help="PNR / Booking Reference (skips Gmail fetch)")
    parser.add_argument(
        "--airline",
        choices=["indigo", "air_india", "air_india_express", "auto"],
        default="auto",
        help="Airline to check in with",
    )
    parser.add_argument("--last-name", default=LAST_NAME, help=f"Passenger last name (default: {LAST_NAME})")
    parser.add_argument("--headless", action="store_true", help="Run browser headless (no window)")
    parser.add_argument("--no-gmail", action="store_true", help="Skip Gmail PNR fetch")
    args = parser.parse_args()

    print("=" * 55)
    print("  India Domestic Airline Web Check-in Agent")
    print("=" * 55)
    print(f"  Passenger last name: {args.last_name}")

    # Resolve PNR
    if args.pnr:
        pnr = args.pnr.upper()
        airline_code = args.airline
        print(f"  PNR: {pnr}  |  Airline: {airline_code}")
    else:
        gmail_pnrs = []
        if not args.no_gmail:
            try:
                from gmail_fetcher import fetch_pnrs_from_gmail
                gmail_pnrs = fetch_pnrs_from_gmail()
            except Exception as e:
                print(f"  Gmail fetch skipped: {e}")

        pnr, airline_code = get_pnr_interactive(gmail_pnrs)

        if airline_code == "auto" and args.airline != "auto":
            airline_code = args.airline

    # Pick airline if still unknown
    if airline_code == "auto":
        detected = detect_airline_from_pnr(pnr)
        if not detected:
            _, airline_code = pick_airline_interactive()
        else:
            airline_code = detected

    run_checkin(pnr, airline_code, args.last_name, headless=args.headless)


if __name__ == "__main__":
    main()
