"""Air India Express web check-in automation — with frequent flyer + seat selection."""
from playwright.sync_api import Page, TimeoutError as PWTimeout
from seat_selector import pick_aisle_seat, prompt_seat_choice

CHECKIN_URL = "https://www.airindiaexpress.com/checkin-home"


def checkin(page: Page, pnr: str, last_name: str, prefs: dict) -> bool:
    ff_number = prefs.get("frequent_flyer", {}).get("air_india_express", {}).get("number", "")
    seat_pref = prefs.get("seat_preference", {}).get("type", "aisle")

    print(f"\n  [Air India Express] Navigating to check-in page...")
    page.goto(CHECKIN_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    for sel in ["button:has-text('Accept')", "#onetrust-accept-btn-handler"]:
        try:
            page.click(sel, timeout=2500)
        except PWTimeout:
            continue

    print(f"  [Air India Express] Entering PNR: {pnr} / last name: {last_name}")
    for sel in ['input[placeholder*="PNR" i]', 'input[name*="pnr" i]', 'input[formcontrolname*="pnr" i]']:
        try:
            page.fill(sel, pnr, timeout=5000)
            break
        except PWTimeout:
            continue

    for sel in ['input[placeholder*="Last Name" i]', 'input[name*="lastName" i]', 'input[formcontrolname*="lastName" i]']:
        try:
            page.fill(sel, last_name, timeout=5000)
            break
        except PWTimeout:
            continue

    for sel in ['button:has-text("Check-in")', 'button:has-text("Retrieve Booking")', 'button[type="submit"]']:
        try:
            page.click(sel, timeout=4000)
            break
        except PWTimeout:
            continue

    print("  [Air India Express] Waiting for booking to load...")
    page.wait_for_timeout(5000)

    if ff_number:
        _fill_frequent_flyer(page, ff_number)

    print(f"\n  [Air India Express] Attempting seat selection (preference: {seat_pref})...")
    seat_result = pick_aisle_seat(page, seat_pref)

    if seat_result == "none_available":
        print(f"  [Air India Express] No {seat_pref} seats available.")
        chosen = prompt_seat_choice(page)
        if chosen:
            print(f"  [Air India Express] Seat {chosen} selected by user.")
    elif seat_result == "no_map":
        print("  [Air India Express] Seat map not found. Proceeding.")

    for sel in ['button:has-text("Confirm")', 'button:has-text("Get Boarding Pass")', 'button:has-text("Check-in")']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                el.click()
                page.wait_for_timeout(3000)
                break
        except PWTimeout:
            continue

    print("  [Air India Express] Please complete final steps in the browser.")
    return True


def _fill_frequent_flyer(page: Page, ff_number: str):
    for sel in [
        'input[placeholder*="Flying Returns" i]',
        'input[placeholder*="frequent" i]',
        'input[placeholder*="loyalty" i]',
        'input[name*="loyalty" i]',
        'input[id*="loyalty" i]',
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                el.fill(ff_number)
                print(f"  [Air India Express] Filled Flying Returns number: {ff_number}")
                return
        except PWTimeout:
            continue
    print(f"  [Air India Express] No frequent flyer field found (will skip).")
