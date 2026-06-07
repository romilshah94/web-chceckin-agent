# India Domestic Airline Web Check-in Agent

Automates web check-in for IndiGo, Air India, and Air India Express using Playwright.

## Setup

```bash
pip3 install -r requirements.txt
python3 -m playwright install chromium
cp preferences.example.json preferences.json
# Edit preferences.json with your loyalty numbers and seat preference
```

For Gmail PNR fetching: place your Google OAuth credentials at `gmail_credentials.json` (gitignored).

## Running

```bash
# Interactive — fetches PNRs from Gmail, pick one
python3 checkin_agent.py

# Direct PNR
python3 checkin_agent.py --pnr ABCD12 --airline indigo

# Skip Gmail
python3 checkin_agent.py --no-gmail
```

Flags: `--pnr`, `--airline` (indigo/air_india/air_india_express), `--last-name`, `--no-gmail`, `--headless`

## File Structure

```
checkin_agent.py          # Main entry point
gmail_fetcher.py          # Gmail PNR extraction
seat_selector.py          # Aisle seat selection logic
boarding_pass_saver.py    # Screenshot → macOS Photos
preferences.json          # Your settings (gitignored)
preferences.example.json  # Template
airlines/
  indigo.py
  air_india.py
  air_india_express.py
```

## Key Notes

- `preferences.json` is gitignored — never commit it (contains loyalty numbers)
- `gmail_credentials.json` and `gmail_token.json` are gitignored — OAuth secrets
- Boarding passes are saved as screenshots and imported to macOS Photos (iCloud sync)
- Seat preference defaults to aisle; prompts user if unavailable
