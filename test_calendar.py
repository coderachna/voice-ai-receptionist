"""Run this BEFORE the voice agent to prove the calendar side works on its own."""
import datetime as dt
import calendar_service as cal

tomorrow = dt.datetime.now(cal.TZ).date() + dt.timedelta(days=1)
slots = cal.free_slots(tomorrow)
print(f"{len(slots)} free slots on {tomorrow}:", [s.strftime("%H:%M") for s in slots])
if slots and input("Book the first one as a test? (y/n) ") == "y":
    ev = cal.book(slots[0], "Test Caller", "9999999999", "test booking")
    print("Booked:", ev.get("htmlLink"))
