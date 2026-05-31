"""
Seat selection logic for Indian airline web check-in.

Strategy:
  1. Parse the seat map rendered on the page.
  2. Filter available aisle seats (column C or D on narrow-body A320/B737;
     column C/D/H on wide-body).
  3. Prefer seats that are not in the middle block (exit rows or legroom rows are a bonus).
  4. If no aisle seat is found, call prompt_seat_choice() so the user can pick.
"""
import re
from typing import Optional
from playwright.sync_api import Page, TimeoutError as PWTimeout

# Typical aisle columns on IndiGo A320 (3-3 config): C and D
# Air India/AIX wide-body (2-4-2): C, D, G, H  — but domestic A320 same as above
AISLE_COLS = {"C", "D"}

# Seats to avoid if possible (middle cols on A320)
MIDDLE_COLS = {"B", "E"}


def pick_aisle_seat(page: Page, preference: str = "aisle") -> str:
    """
    Try to select a seat matching `preference`.

    Returns:
        "selected:<seat_label>"  — seat was selected
        "none_available"         — no matching seat found
        "no_map"                 — seat map not found on page
    """
    page.wait_for_timeout(2000)

    # Wait for seat map to appear
    seat_map_selectors = [
        "[class*='seat-map']",
        "[class*='seatmap']",
        "[class*='SeatMap']",
        "[data-testid*='seat']",
        ".seat",
    ]
    seat_map_found = False
    for sel in seat_map_selectors:
        try:
            page.wait_for_selector(sel, timeout=8000)
            seat_map_found = True
            break
        except PWTimeout:
            continue

    if not seat_map_found:
        print("  [SeatSelector] No seat map found on page.")
        return "no_map"

    # Collect all available seat elements
    available_seats = _get_available_seats(page)
    if not available_seats:
        print("  [SeatSelector] No available seats detected on the map.")
        return "none_available"

    print(f"  [SeatSelector] Found {len(available_seats)} available seats.")

    # Filter by preference
    if preference == "aisle":
        preferred = [s for s in available_seats if _is_aisle(s["label"])]
    elif preference == "window":
        preferred = [s for s in available_seats if _is_window(s["label"])]
    else:
        preferred = available_seats  # any

    if not preferred:
        print(f"  [SeatSelector] No {preference} seats available.")
        return "none_available"

    # Pick the first preferred seat (sorted by row number ascending)
    preferred.sort(key=lambda s: _row_number(s["label"]))
    chosen = preferred[0]

    print(f"  [SeatSelector] Selecting seat: {chosen['label']}")
    try:
        chosen["element"].click()
        page.wait_for_timeout(1500)
        # Confirm selection if a dialog/button appears
        _confirm_seat_dialog(page)
        return f"selected:{chosen['label']}"
    except Exception as e:
        print(f"  [SeatSelector] Failed to click seat {chosen['label']}: {e}")
        return "none_available"


def prompt_seat_choice(page: Page) -> Optional[str]:
    """
    Print available seats and ask the user to choose one via stdin.
    Returns the chosen seat label, or None if user skips.
    """
    available = _get_available_seats(page)
    if not available:
        print("  [SeatSelector] No available seats to display.")
        return None

    print("\n  ┌─────────────────────────────────────────────┐")
    print("  │  No aisle seats available. Choose a seat:  │")
    print("  └─────────────────────────────────────────────┘")

    # Group by row for readability
    by_row: dict[int, list[str]] = {}
    for s in available:
        row = _row_number(s["label"])
        by_row.setdefault(row, []).append(s["label"])

    for row in sorted(by_row):
        print(f"    Row {row:>2}: " + "  ".join(sorted(by_row[row])))

    choice = input("\n  Enter seat (e.g. 14C) or press ENTER to skip: ").strip().upper()
    if not choice:
        return None

    # Find and click the chosen seat
    match = next((s for s in available if s["label"] == choice), None)
    if match:
        try:
            match["element"].click()
            page.wait_for_timeout(1500)
            _confirm_seat_dialog(page)
            return choice
        except Exception as e:
            print(f"  [SeatSelector] Could not click seat {choice}: {e}")
    else:
        print(f"  [SeatSelector] Seat {choice} not found/available.")
    return None


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_available_seats(page: Page) -> list[dict]:
    """Return list of {label, element} for all available (clickable) seats."""
    seats = []

    # Broad selector — IndiGo and most SPAs mark available seats with classes
    # like 'available', 'open', 'free', or aria-disabled="false"
    candidate_selectors = [
        # IndiGo specific
        "[class*='seat']:not([class*='occupied']):not([class*='selected']):not([class*='blocked']):not([class*='disabled'])",
        "[class*='Seat']:not([class*='Occupied']):not([class*='Selected']):not([class*='Blocked'])",
        # Generic
        "button[aria-label*='seat' i][aria-disabled='false']",
        "[data-available='true']",
        "[data-status='available']",
    ]

    seen_labels = set()
    for sel in candidate_selectors:
        try:
            els = page.locator(sel).all()
            for el in els:
                try:
                    label = (
                        el.get_attribute("aria-label")
                        or el.get_attribute("data-seat")
                        or el.get_attribute("id")
                        or el.inner_text()
                    )
                    if not label:
                        continue
                    # Normalise: extract row+col like "14C"
                    label = _normalise_seat_label(label)
                    if not label or label in seen_labels:
                        continue
                    if not el.is_visible():
                        continue
                    seen_labels.add(label)
                    seats.append({"label": label, "element": el})
                except Exception:
                    continue
        except Exception:
            continue

    return seats


def _normalise_seat_label(raw: str) -> Optional[str]:
    """Extract seat label like '14C' from raw strings."""
    raw = raw.strip().upper()
    m = re.search(r"(\d{1,2}[A-HJ-Z])", raw)
    return m.group(1) if m else None


def _is_aisle(label: str) -> bool:
    if not label:
        return False
    col = label[-1].upper()
    return col in AISLE_COLS


def _is_window(label: str) -> bool:
    if not label:
        return False
    col = label[-1].upper()
    return col in {"A", "F"}


def _row_number(label: str) -> int:
    m = re.match(r"(\d+)", label)
    return int(m.group(1)) if m else 99


def _confirm_seat_dialog(page: Page):
    """Dismiss any seat confirmation popup/dialog."""
    for sel in [
        'button:has-text("Confirm")',
        'button:has-text("OK")',
        'button:has-text("Done")',
        'button:has-text("Select")',
        "[class*='confirm'] button",
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click()
                page.wait_for_timeout(1000)
                return
        except PWTimeout:
            continue
