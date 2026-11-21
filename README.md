# AI Voice Receptionist

## Setup (about 30 minutes)

1. `python -m venv venv && source venv/bin/activate` (Python 3.10+), then `pip install -r requirements.txt`
2. `cp .env.example .env` and fill in keys from Deepgram, Groq, ElevenLabs and LiveKit Cloud.
3. Google Calendar:
   - Google Cloud Console -> new project -> enable **Google Calendar API**.
   - IAM -> Service Accounts -> create one -> Keys -> add JSON key -> save as `service_account.json` here.
   - In Google Calendar -> your calendar's Settings and sharing -> Share with specific people ->
     add the service account email with **Make changes to events**.
   - Put the calendar's ID (Settings -> Integrate calendar) in `GOOGLE_CALENDAR_ID`.
4. `python test_calendar.py` - must list slots and book a test event before you go further.
5. `python agent.py download-files` (once).
6. `python agent.py console` - talk to it from your terminal.
7. `python agent.py dev` - then open the Agent Console / Playground in LiveKit Cloud to talk from the browser.

## Edit for a new business
Change the `BUSINESS` dict at the top of `agent.py` and the hours in `.env`.

## Messages
Callback requests are saved to `messages.csv`.
