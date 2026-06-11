"""
boarding_pass_saver.py — screenshot the boarding pass page and save to Photos.

Platform behaviour:
  macOS   — imports into Photos.app via AppleScript (syncs to iPhone via iCloud)
  Windows — copies to ~/Pictures/BoardingPasses/ and opens in the default viewer
  Linux   — saves to boarding_passes/ next to the script; no photo-app integration
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SAVE_DIR = Path(__file__).parent / "boarding_passes"
SAVE_DIR.mkdir(exist_ok=True)


def capture_and_save(page, pnr: str, airline: str) -> Path | None:
    """
    Scroll to top of the boarding pass page, take a full-page screenshot
    (so the QR code is included), save locally, then import to the platform
    photo app where supported.
    """
    out = SAVE_DIR / f"BoardingPass_{airline.upper()}_{pnr}_{datetime.now().strftime('%Y%m%d_%H%M')}.png"

    # Ensure QR is visible — scroll to top
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(1000)

    page.screenshot(path=str(out), full_page=True)
    print(f"  [BoardingPass] Screenshot saved → {out.name}")

    _import_to_photos(out)
    return out


def _import_to_photos(path: Path):
    if sys.platform == "darwin":
        # macOS — import to Photos.app; iCloud syncs it to iPhone automatically
        script = f'tell application "Photos" to import POSIX file "{path.resolve()}" skip check duplicates yes'
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if r.returncode == 0:
            print("  [BoardingPass] Imported to Photos — will sync to iPhone via iCloud")
        else:
            print(f"  [BoardingPass] Photos import failed: {r.stderr.strip()}")

    elif sys.platform == "win32":
        # Windows — copy to Pictures\BoardingPasses so Windows Photos discovers it,
        # then open the file with the default image viewer
        dest_dir = Path.home() / "Pictures" / "BoardingPasses"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / path.name
        shutil.copy2(path, dest)
        os.startfile(str(dest))
        print(f"  [BoardingPass] Saved to Pictures\\BoardingPasses and opened in Photos")

    else:
        # Linux / other — screenshot already saved locally, no photo-app integration
        print(f"  [BoardingPass] Saved to: {path.resolve()}")
