"""Air India web check-in automation — with frequent flyer + seat selection."""
from playwright.sync_api import Page, TimeoutError as PWTimeout
from seat_selector import pick_aisle_seat, prompt_seat_choice

CHECKIN_URL = "https://www.airindia.com/in/en/manage/web-checkin.html"


def checkin(page: Page, pnr: str, last_name: str, prefs: dict) -> bool:
    ff_number = prefs.get("frequent_flyer", {}).get("air_india", {}).get("number", "")
    seat_pref = prefs.get("seat_preference", {}).get("type", "aisle")

    print(f"\n  [Air India] Navigating to check-in page...")
    page.goto(CHECKIN_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    # Dismiss cookie banners
    for sel in ["#onetrust-accept-btn-handler", "button:has-text('Accept All')", "button:has-text('Accept')"]:
        try:
            page.click(sel, timeout=2500)
        except PWTimeout:
            continue

    print(f"  [Air India] Entering PNR: {pnr} / last name: {last_name}")
    pnr_sels = ['input[placeholder*="PNR" i]', 'input[formcontrolname*="pnr" i]', 'input[id*="pnr" i]']
    for sel in pnr_sels:
        try:
            page.fill(sel, pnr, timeout=5000)
            break
        except PWTimeout:
            continue

    ln_sels = ['input[placeholder*="Last Name" i]', 'input[formcontrolname*="lastName" i]', 'input[id*="lastName" i]']
    for sel in ln_sels:
        try:
            page.fill(sel, last_name, timeout=5000)
            break
        except PWTimeout:
            continue

    for sel in ['button:has-text("Check-in")', 'button:has-text("Retrieve")', 'button[type="submit"]']:
        try:
            page.click(sel, timeout=4000)
            break
        except PWTimeout:
            continue

    print("  [Air India] Waiting for booking to load...")
    page.wait_for_timeout(5000)

    # Fill Flying Returns number if field is present
    if ff_number:
        _fill_frequent_flyer(page, ff_number)

    # Proceed to seat selection
    print(f"\n  [Air India] Attempting seat selection (preference: {seat_pref})...")
    seat_result = pick_aisle_seat(page, seat_pref)

    if seat_result == "none_available":
        print(f"  [Air India] No {seat_pref} seats available.")
        chosen = prompt_seat_choice(page)
        if chosen:
            print(f"  [Air India] Seat {chosen} selected by user.")

    elif seat_result == "no_map":
        print("  [Air India] Seat map not found. Proceeding without seat selection.")

    # Final confirm
    for sel in ['button:has-text("Confirm")', 'button:has-text("Get Boarding Pass")', 'button:has-text("Check-in")']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                el.click()
                page.wait_for_timeout(3000)
                break
        except PWTimeout:
            continue

    print("  [Air India] Please complete final steps in the browser.")
    return True


def _fill_frequent_flyer(page: Page, ff_number: str):
    for sel in [
        'input[placeholder*="Flying Returns" i]',
        'input[placeholder*="frequent" i]',
        'input[placeholder*="loyalty" i]',
        'input[name*="loyalty" i]',
        'input[name*="flyingReturns" i]',
        'input[id*="loyalty" i]',
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                el.fill(ff_number)
                print(f"  [Air India] Filled Flying Returns number: {ff_number}")
                return
        except PWTimeout:
            continue
    print(f"  [Air India] No frequent flyer field found (will skip).")
