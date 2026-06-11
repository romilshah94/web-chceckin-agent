"""IndiGo web check-in automation — with frequent flyer + seat selection."""
import tempfile
from pathlib import Path
from playwright.sync_api import Page, TimeoutError as PWTimeout
from seat_selector import pick_aisle_seat, prompt_seat_choice

CHECKIN_URL = "https://www.goindigo.in/web-check-in.html"


def checkin(page: Page, pnr: str, last_name: str, prefs: dict) -> bool:
    ff_number = prefs.get("frequent_flyer", {}).get("indigo", {}).get("number", "")
    seat_pref = prefs.get("seat_preference", {}).get("type", "aisle")

    print(f"\n  [IndiGo] Navigating to check-in page...")
    page.goto(CHECKIN_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(4000)

    # --- Wait for micro-frontend widget to render ---
    print(f"  [IndiGo] Waiting for check-in widget to load...")
    try:
        page.wait_for_selector('input[name="pnr-booking-ref"]', timeout=20000)
    except PWTimeout:
        print("  [IndiGo] Widget did not load in time. Retrying once...")
        try:
            page.goto(CHECKIN_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(8000)
            page.wait_for_selector('input[name="pnr-booking-ref"]', timeout=15000)
        except PWTimeout:
            print("  [IndiGo] Widget still not available.")
            return False

    # --- Fill PNR + Last Name ---
    print(f"  [IndiGo] Entering PNR: {pnr} and last name: {last_name}")
    try:
        page.click('input[name="pnr-booking-ref"]')
        page.type('input[name="pnr-booking-ref"]', pnr, delay=80)
        page.keyboard.press("Tab")
        page.type('input[name="email-last-name"]', last_name, delay=80)
        page.wait_for_timeout(500)
        # Verify both fields have values before submitting
        pnr_val = page.input_value('input[name="pnr-booking-ref"]')
        ln_val  = page.input_value('input[name="email-last-name"]')
        print(f"  [IndiGo] Form values — PNR: {pnr_val}, Last Name: {ln_val}")
        page.click('button[type="submit"]', timeout=5000)
    except PWTimeout as e:
        print(f"  [IndiGo] Could not fill form: {e}")
        return False

    # --- Wait for booking view ---
    print("  [IndiGo] Waiting for booking to load...")
    try:
        page.wait_for_url("**/checkin/view**", timeout=15000)
    except PWTimeout:
        page.wait_for_timeout(5000)

    page.screenshot(path=str(Path(tempfile.gettempdir()) / "indigo_booking_view.png"))
    print("  [IndiGo] Booking loaded.")

    # --- Fill Frequent Flyer number if field exists ---
    if ff_number:
        _fill_frequent_flyer(page, ff_number)

    # --- Proceed to check-in (click Check-in / Proceed button) ---
    _click_proceed(page)

    # --- Seat Selection ---
    print(f"\n  [IndiGo] Attempting seat selection (preference: {seat_pref})...")
    seat_result = pick_aisle_seat(page, seat_pref)

    if seat_result == "none_available":
        print(f"  [IndiGo] No {seat_pref} seats available.")
        chosen = prompt_seat_choice(page)
        if chosen:
            print(f"  [IndiGo] Seat {chosen} selected by user.")
        else:
            print("  [IndiGo] Skipping seat selection.")

    # --- Final confirm / get boarding pass ---
    _confirm_checkin(page)
    return True


def _fill_frequent_flyer(page: Page, ff_number: str):
    """Try to fill IndiGo BluChip number if the field is present."""
    ff_selectors = [
        'input[placeholder*="BluChip" i]',
        'input[placeholder*="frequent" i]',
        'input[placeholder*="loyalty" i]',
        'input[name*="loyalty" i]',
        'input[name*="frequentFlyer" i]',
        'input[id*="bluechip" i]',
        'input[id*="loyalty" i]',
    ]
    for sel in ff_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                el.fill(ff_number)
                print(f"  [IndiGo] Filled BluChip number: {ff_number}")
                return
        except PWTimeout:
            continue
    print(f"  [IndiGo] No frequent flyer field found (will skip).")


def _click_proceed(page: Page):
    """Click the Check-in / Proceed / Continue button on the booking view."""
    for sel in [
        'button:has-text("Check-in")',
        'button:has-text("Proceed to check-in")',
        'button:has-text("Proceed")',
        'button:has-text("Continue")',
        'a:has-text("Check-in")',
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                el.click()
                print(f"  [IndiGo] Clicked proceed button.")
                page.wait_for_timeout(3000)
                return
        except PWTimeout:
            continue


def _confirm_checkin(page: Page):
    """Click final confirm / get boarding pass button."""
    for sel in [
        'button:has-text("Confirm")',
        'button:has-text("Get Boarding Pass")',
        'button:has-text("Download Boarding Pass")',
        'button:has-text("Check-in")',
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                el.click()
                print(f"  [IndiGo] Confirmed check-in.")
                page.wait_for_timeout(4000)
                return
        except PWTimeout:
            continue
    print("  [IndiGo] Please complete final confirmation in the browser.")
