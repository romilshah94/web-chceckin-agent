"""Air India Express web check-in automation.

LEARNINGS (from live run Jun 2026):
- The check-in page asks for "Name (First or Last)" — use first OR last name, not both.
- For corporate bookings via Amex GBT, the trip reference (e.g. GWW3J6) is NOT the airline PNR.
  Use the "CONFIRMATION NO." field from the booking email (e.g. QD929E) as the PNR.
- The page shows a Login popup after booking is found — always click "Skip Login".
- Seat is already selected if pre-booked (shown as green "RS" on seat map) — no action needed.
- Meal and extra baggage screens: click "Proceed" to skip, do not add anything (per preferences).
- Add-ons screen: click "Continue" to skip.
- Guest Details: fill phone + email, then toggle ON "Earn Maharaja Club points" and enter Flying Returns ID.
- Declaration page: update email to personal Gmail (romilshah94@gmail.com), then "Agree & Continue".

PREFERRED EXECUTION METHOD:
  Use the Claude Chrome browser extension (MCP tool) rather than launching a new Playwright browser.
  This avoids cookie/session issues and uses the user's existing Chrome profile.
  Only fall back to Playwright if the Chrome extension is unavailable.
"""
from playwright.sync_api import Page, TimeoutError as PWTimeout
from seat_selector import pick_aisle_seat, prompt_seat_choice

CHECKIN_URL = "https://www.airindiaexpress.com/checkin-home"


def checkin(page: Page, pnr: str, last_name: str, prefs: dict) -> bool:
    """
    pnr: Must be the AIRLINE confirmation number (e.g. QD929E), not the travel agency trip ref.
    last_name: First OR last name works on the Air India Express check-in form.
    """
    passenger = prefs.get("passenger", {})
    ff = prefs.get("frequent_flyer", {}).get("air_india_express", {})
    ff_number = ff.get("number", "")
    earn_maharaja = ff.get("earn_maharaja_points", False)
    seat_pref = prefs.get("seat_preference", {}).get("type", "aisle")
    skip_addons = prefs.get("add_ons", {}).get("skip_all_addons", True)
    phone = passenger.get("phone", "")
    email = passenger.get("email", "")
    bp_email = prefs.get("boarding_pass", {}).get("email", email)

    print(f"\n  [Air India Express] Navigating to check-in page...")
    page.goto(CHECKIN_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)

    # Dismiss cookie/consent banners
    for sel in ["button:has-text('Accept')", "#onetrust-accept-btn-handler"]:
        try:
            page.click(sel, timeout=2500)
        except PWTimeout:
            continue

    # Name field accepts First OR Last name
    print(f"  [Air India Express] Entering name: {last_name} / PNR: {pnr}")
    for sel in [
        'input[placeholder*="Name" i]',
        'input[placeholder*="First or Last" i]',
        'input[formcontrolname*="name" i]',
    ]:
        try:
            page.fill(sel, last_name, timeout=5000)
            break
        except PWTimeout:
            continue

    for sel in [
        'input[placeholder*="PNR" i]',
        'input[placeholder*="Booking Reference" i]',
        'input[name*="pnr" i]',
        'input[formcontrolname*="pnr" i]',
    ]:
        try:
            page.fill(sel, pnr, timeout=5000)
            break
        except PWTimeout:
            continue

    for sel in [
        'button:has-text("Get itinerary")',
        'button:has-text("Check-in")',
        'button:has-text("Retrieve Booking")',
        'button[type="submit"]',
    ]:
        try:
            page.click(sel, timeout=4000)
            break
        except PWTimeout:
            continue

    page.wait_for_timeout(5000)

    # Skip Login popup if it appears
    for sel in ['text="Skip Login"', 'button:has-text("Skip Login")', 'a:has-text("Skip Login")']:
        try:
            page.click(sel, timeout=4000)
            print("  [Air India Express] Skipped login popup.")
            page.wait_for_timeout(3000)
            break
        except PWTimeout:
            continue

    # Seat selection — if pre-booked, seat map already shows it selected; just proceed
    print(f"\n  [Air India Express] Seat selection (preference: {seat_pref})...")
    seat_result = pick_aisle_seat(page, seat_pref)
    if seat_result == "none_available":
        chosen = prompt_seat_choice(page)
        if chosen:
            print(f"  [Air India Express] Seat {chosen} selected.")
    elif seat_result == "no_map":
        print("  [Air India Express] Seat map not found or pre-selected. Proceeding.")

    # Proceed through seat → meal → baggage → add-ons screens
    proceed_labels = [
        "Proceed to Meals", "Proceed to Baggage", "Proceed To Add-Ons",
        "Continue", "Confirm", "Get Boarding Pass",
    ]
    for label in proceed_labels:
        try:
            el = page.locator(f'button:has-text("{label}")').first
            if el.is_visible(timeout=3000):
                if skip_addons or "Meal" in label or "Baggage" in label or "Add" in label:
                    el.click()
                    page.wait_for_timeout(3000)
                    print(f"  [Air India Express] Clicked '{label}'.")
        except PWTimeout:
            continue

    # Guest Details — fill phone, email, Maharaja Club
    _fill_guest_details(page, phone, email, ff_number, earn_maharaja)

    # Declaration — update boarding pass email and agree
    _handle_declaration(page, bp_email)

    print("  [Air India Express] Check-in flow complete.")
    return True


def _fill_guest_details(page: Page, phone: str, email: str, ff_number: str, earn_maharaja: bool):
    try:
        page.wait_for_selector('text="Guest Details"', timeout=6000)
    except PWTimeout:
        return

    if phone:
        for sel in ['input[placeholder*="Mobile" i]', 'input[type="tel"]']:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.triple_click()
                    el.fill(phone)
                    print(f"  [Air India Express] Filled phone: {phone}")
                    break
            except PWTimeout:
                continue

    if email:
        for sel in ['input[type="email"]', 'input[placeholder*="Email" i]']:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.triple_click()
                    el.fill(email)
                    print(f"  [Air India Express] Filled email: {email}")
                    break
            except PWTimeout:
                continue

    if earn_maharaja and ff_number:
        for sel in ['text="Earn Maharaja Club points"']:
            try:
                toggle = page.locator(sel).locator('..').locator('input[type="checkbox"], [role="switch"]').first
                if not toggle.is_checked():
                    page.locator(sel).locator('..').locator('[role="switch"], button').first.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass
        for sel in ['input[placeholder*="Maharaja Club" i]', 'input[placeholder*="Flying Returns" i]', 'input[placeholder*="loyalty" i]']:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=3000):
                    el.fill(ff_number)
                    print(f"  [Air India Express] Filled Maharaja Club ID: {ff_number}")
                    break
            except PWTimeout:
                continue

    try:
        page.locator('button:has-text("Done")').first.click()
        page.wait_for_timeout(3000)
        print("  [Air India Express] Guest details submitted.")
    except PWTimeout:
        pass


def _handle_declaration(page: Page, bp_email: str):
    try:
        page.wait_for_selector('text="Declaration"', timeout=6000)
    except PWTimeout:
        return

    # Update boarding pass email field if present
    if bp_email:
        for sel in ['input[type="email"]', 'input[placeholder*="Email" i]']:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.triple_click()
                    el.fill(bp_email)
                    print(f"  [Air India Express] Boarding pass email set to: {bp_email}")
                    break
            except PWTimeout:
                continue

    try:
        page.locator('button:has-text("Agree & Continue")').first.click()
        page.wait_for_timeout(5000)
        print("  [Air India Express] Declaration agreed.")
    except PWTimeout:
        pass
