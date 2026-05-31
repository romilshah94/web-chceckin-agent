# India Domestic Airline Web Check-in Agent

Automates web check-in for Indian domestic airlines — IndiGo, Air India, Air India Express.

## Features
- Fetches PNR from Gmail or accepts manual input
- Auto-fills frequent flyer number from `preferences.json`
- Prefers aisle seat; prompts if unavailable
- Screenshots boarding pass → imports to macOS Photos (iCloud syncs to iPhone)

## Supported Airlines
| Airline | Check-in URL |
|---|---|
| IndiGo | goindigo.in |
| Air India | airindia.com |
| Air India Express | airindiaexpress.com |

## Setup

```bash
pip3 install -r requirements.txt
python3 -m playwright install chromium
```

Copy and fill in your details:
```bash
cp preferences.example.json preferences.json
# Edit preferences.json with your loyalty numbers and seat preference
```

### Gmail PNR fetch (optional)
1. Enable Gmail API in Google Cloud Console
2. Create OAuth 2.0 Desktop credentials
3. Save as `gmail_credentials.json` in this folder

## Usage

```bash
# Interactive — fetches PNRs from Gmail, pick one
python3 checkin_agent.py

# Direct PNR
python3 checkin_agent.py --pnr ABCD12 --airline indigo

# Skip Gmail, enter PNR manually
python3 checkin_agent.py --no-gmail
```

| Flag | Description |
|---|---|
| `--pnr` | PNR / Booking Reference |
| `--airline` | `indigo` / `air_india` / `air_india_express` |
| `--last-name` | Passenger last name |
| `--no-gmail` | Skip Gmail scan |
| `--headless` | Run browser without window |

## File Structure
```
checkin-agent/
├── checkin_agent.py        # Main entry point
├── gmail_fetcher.py        # Gmail PNR extraction
├── seat_selector.py        # Aisle seat selection logic
├── boarding_pass_saver.py  # Screenshot → Photos
├── preferences.json        # Your settings (gitignored)
├── preferences.example.json
└── airlines/
    ├── indigo.py
    ├── air_india.py
    └── air_india_express.py
```
