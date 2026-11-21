"""Google Calendar layer: find free slots and book them.

Uses a service account. Share your Google Calendar with the service
account's email ("Make changes to events") or every call will 404.
"""
import datetime as dt
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TZ = ZoneInfo(os.getenv("BUSINESS_TIMEZONE", "Asia/Kolkata"))
CALENDAR_ID = os.environ["GOOGLE_CALENDAR_ID"]
SLOT = dt.timedelta(minutes=int(os.getenv("SLOT_MINUTES", "30")))
OPEN_HOUR = int(os.getenv("OPEN_HOUR", "10"))
CLOSE_HOUR = int(os.getenv("CLOSE_HOUR", "19"))
# Python weekday numbers: Monday=0 ... Sunday=6
CLOSED_WEEKDAYS = {int(d) for d in os.getenv("CLOSED_WEEKDAYS", "6").split(",") if d.strip()}
MIN_NOTICE = dt.timedelta(minutes=int(os.getenv("MIN_NOTICE_MINUTES", "30")))

_service = None


class SlotUnavailable(Exception):
    pass


def _svc():
    # Build the client once and reuse it; rebuilding per call adds latency.
    global _service
    if _service is None:
        creds = service_account.Credentials.from_service_account_file(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json"), scopes=SCOPES
        )
        _service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return _service


def _parse(ts: str) -> dt.datetime:
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def free_slots(day: dt.date) -> list[dt.datetime]:
    """All bookable slot start times on a day, in business timezone."""
    if day.weekday() in CLOSED_WEEKDAYS:
        return []
    start = dt.datetime.combine(day, dt.time(OPEN_HOUR), tzinfo=TZ)
    end = dt.datetime.combine(day, dt.time(CLOSE_HOUR), tzinfo=TZ)
    earliest = dt.datetime.now(TZ) + MIN_NOTICE
    if end <= earliest:
        return []

    body = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "timeZone": TZ.key,
        "items": [{"id": CALENDAR_ID}],
    }
    result = _svc().freebusy().query(body=body).execute()
    busy = [(_parse(b["start"]), _parse(b["end"])) for b in result["calendars"][CALENDAR_ID]["busy"]]

    slots, t = [], start
    while t + SLOT <= end:
        overlaps = any(t < b_end and t + SLOT > b_start for b_start, b_end in busy)
        if t >= earliest and not overlaps:
            slots.append(t)
        t += SLOT
    return slots


def next_open_day(after: dt.date, max_days: int = 7) -> tuple[dt.date, list[dt.datetime]] | None:
    """First day after `after` that has at least one free slot."""
    for i in range(1, max_days + 1):
        day = after + dt.timedelta(days=i)
        slots = free_slots(day)
        if slots:
            return day, slots
    return None


def book(start: dt.datetime, name: str, phone: str, reason: str) -> dict:
    """Create the event. Re-checks the slot first so two callers can't double-book."""
    if start not in free_slots(start.date()):
        raise SlotUnavailable()
    event = {
        "summary": f"{name} - {reason}",
        "description": f"Booked by AI receptionist\nName: {name}\nPhone: {phone}\nReason: {reason}",
        "start": {"dateTime": start.isoformat(), "timeZone": TZ.key},
        "end": {"dateTime": (start + SLOT).isoformat(), "timeZone": TZ.key},
        # Note: service accounts can't send attendee invites without
        # Workspace domain-wide delegation, so no "attendees" field here.
    }
    return _svc().events().insert(calendarId=CALENDAR_ID, body=event).execute()
