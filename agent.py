"""AI voice receptionist: Deepgram STT -> Groq LLM -> ElevenLabs TTS, on LiveKit Agents.

Run:
  python agent.py download-files   # once: turn-detector + VAD model weights
  python agent.py console          # talk to it in your terminal
  python agent.py dev              # connect to LiveKit Cloud (browser / phone)
"""
import asyncio
import csv
import datetime as dt
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from livekit import agents, api
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    RunContext,
    TurnHandlingOptions,
    function_tool,
    get_job_context,
)
from livekit.plugins import deepgram, elevenlabs, groq, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

import calendar_service as cal

log = logging.getLogger("receptionist")

# How many recent conversation items the LLM sees each turn. Long calls stay fast
# because old chatter isn't resent every time. ~20 covers a full booking comfortably.
MAX_HISTORY_ITEMS = int(os.getenv("MAX_HISTORY_ITEMS", "20"))

# ---- Edit this for each business. The agent answers FAQs ONLY from here. ----
BUSINESS = {
    "name": os.getenv("BUSINESS_NAME", "Sharma Dental Clinic"),
    "type": "dental clinic",
    "assistant_name": "Riya",
    "address": "Sector 62, Noida, near the metro station",
    "hours": "Monday to Saturday, 10 AM to 7 PM. Closed Sunday.",
    "services": "Checkup 500 rupees, cleaning 1200 rupees, filling from 1500 rupees, root canal from 5000 rupees.",
    "extra": "Parking is available. UPI and cards accepted.",
}


def build_instructions() -> str:
    now = dt.datetime.now(cal.TZ)
    b = BUSINESS
    return f"""You are {b['assistant_name']}, the phone receptionist for {b['name']}, a {b['type']}.
Today is {now:%A, %d %B %Y} and the time is {now:%I:%M %p}. Use this to resolve words like "tomorrow" or "next Monday".

HOW YOU SPEAK
- This is a phone call. Reply in one or two short sentences. Ask one question at a time.
- Plain spoken words only: no lists, markdown, emojis or symbols.
- Say times naturally, like "four thirty in the evening", never "16:30".
- Match the caller's language. If they speak Hindi or Hinglish, reply in simple Hinglish.

BUSINESS FACTS (answer only from these; if it's not here, say you'll have the team call back)
Address: {b['address']}
Hours: {b['hours']}
Services and prices: {b['services']}
Other: {b['extra']}

BOOKING FLOW
1. Find out what they need and which day suits them.
2. Call check_availability with that date. Offer at most three slots, closest to what they asked.
3. Ask for their full name, then their phone number. Read the number back digit by digit to confirm.
4. Confirm everything in one sentence ("So that's Rahul Verma, Tuesday at 11 AM for a checkup, right?").
5. Only after they say yes, call book_appointment.
6. Tell them it's booked and ask if there's anything else.

ENDING THE CALL
- When the caller says bye, thank you, that's all, nothing else, or similar (in any language, e.g. "bas", "theek hai, dhanyavaad"),
  say one short goodbye like "Thank you for calling, have a great day!" and then IMMEDIATELY call end_call.
- Never keep talking after the goodbye. Never ask another question after they said they're done.

RULES
- Never say an appointment is booked unless book_appointment returned success.
- Never invent free slots. Only offer slots that check_availability returned.
- If the caller wants something you can't do (cancel, reschedule, talk to the doctor), use take_message.
- If it sounds like a medical emergency, tell them to call 112 or go to the nearest hospital immediately.
"""


def _spoken_time(t: dt.datetime) -> str:
    return t.strftime("%I:%M %p").lstrip("0")


class Receptionist(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=build_instructions())

    async def llm_node(self, chat_ctx, tools, model_settings):
        """Send only the recent part of the conversation to the LLM.
        The full history is still kept; this just trims what each request carries."""
        trimmed = chat_ctx.copy()
        trimmed.truncate(max_items=MAX_HISTORY_ITEMS)
        async for chunk in Agent.default.llm_node(self, trimmed, tools, model_settings):
            yield chunk

    @function_tool()
    async def check_availability(self, context: RunContext, date: str) -> str:
        """Look up free appointment slots for a given date.

        Args:
            date: The date in YYYY-MM-DD format.
        """
        try:
            day = dt.date.fromisoformat(date)
        except ValueError:
            return "Invalid date format. Use YYYY-MM-DD."
        if day < dt.datetime.now(cal.TZ).date():
            return "That date is in the past. Ask for a future date."

        # The Google client is blocking; run it in a thread so audio doesn't stutter.
        slots = await asyncio.to_thread(cal.free_slots, day)
        if slots:
            shown = ", ".join(_spoken_time(s) for s in slots[:8])
            more = f" (and {len(slots) - 8} more later)" if len(slots) > 8 else ""
            return f"Free slots on {day:%A %d %B}: {shown}{more}."

        nxt = await asyncio.to_thread(cal.next_open_day, day)
        if nxt:
            nday, nslots = nxt
            shown = ", ".join(_spoken_time(s) for s in nslots[:5])
            return f"No free slots on {day:%A %d %B}. Next available day is {nday:%A %d %B} ({nday.isoformat()}): {shown}."
        return f"No free slots on {day:%A %d %B} or the following week. Offer to take a message."

    @function_tool()
    async def book_appointment(
        self, context: RunContext, name: str, phone: str, date: str, time: str, reason: str
    ) -> str:
        """Book a confirmed appointment. Only call after the caller has confirmed all details.

        Args:
            name: Caller's full name.
            phone: Caller's phone number, digits only.
            date: Appointment date in YYYY-MM-DD format.
            time: Start time in 24-hour HH:MM format, e.g. 16:30.
            reason: Short reason for the visit.
        """
        try:
            start = dt.datetime.combine(
                dt.date.fromisoformat(date), dt.time.fromisoformat(time), tzinfo=cal.TZ
            )
        except ValueError:
            return "Invalid date or time format. Use YYYY-MM-DD and HH:MM."
        try:
            await asyncio.to_thread(cal.book, start, name, phone, reason)
        except cal.SlotUnavailable:
            return "That slot was just taken or isn't valid. Call check_availability again and offer other times."
        except Exception:
            log.exception("booking failed")
            return "Booking system error. Apologise and use take_message so the team calls them back."
        log.info("BOOKED %s %s %s", name, phone, start.isoformat())
        return f"Success. Booked {name} on {start:%A %d %B} at {_spoken_time(start)}."

    @function_tool()
    async def take_message(self, context: RunContext, name: str, phone: str, message: str) -> str:
        """Save a message for the staff to call the person back.

        Args:
            name: Caller's name.
            phone: Caller's phone number.
            message: What they need, in one or two sentences.
        """
        row = [dt.datetime.now(cal.TZ).isoformat(), name, phone, message]
        await asyncio.to_thread(_append_csv, "messages.csv", row)
        return "Message saved. Tell them the team will call back during working hours."

    @function_tool()
    async def end_call(self, context: RunContext) -> None:
        """End the call. Use it right after your goodbye, when the caller says bye,
        thanks you and has nothing else, or says they don't need anything more."""
        await context.wait_for_playout()  # let the goodbye finish playing first
        job = get_job_context()
        log.info("caller finished, hanging up")
        try:
            # Real calls (browser/phone): closing the room disconnects the caller.
            await job.api.room.delete_room(api.DeleteRoomRequest(room=job.room.name))
        except Exception:
            # Console mode has no real room, so this fails there; that's fine.
            pass
        job.shutdown(reason="call ended")


def _append_csv(path: str, row: list) -> None:
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)


server = AgentServer()


def build_llm():
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    kwargs = {"model": model, "temperature": 0.3}
    # gpt-oss / qwen "think" before answering; on a phone call we want minimal thinking.
    if model.startswith(("openai/gpt-oss", "qwen")):
        kwargs["reasoning_effort"] = os.getenv("GROQ_REASONING_EFFORT", "low")
    return groq.LLM(**kwargs)


def build_tts():
    """Pick the voice provider from .env: TTS_PROVIDER=elevenlabs (default) or deepgram."""
    if os.getenv("TTS_PROVIDER", "elevenlabs").lower() == "deepgram":
        # Uses your existing DEEPGRAM_API_KEY; no extra signup needed.
        return deepgram.TTS(model=os.getenv("DEEPGRAM_TTS_MODEL", "aura-2-thalia-en"))
    kwargs = {"model": os.getenv("ELEVEN_MODEL", "eleven_flash_v2_5")}
    if os.getenv("ELEVEN_VOICE_ID"):
        kwargs["voice_id"] = os.environ["ELEVEN_VOICE_ID"]
    return elevenlabs.TTS(**kwargs)


# Empty name = joins every new room automatically (easiest for browser testing).
# Set AGENT_NAME=receptionist in .env later for phone calls with explicit dispatch.
@server.rtc_session(agent_name=os.getenv("AGENT_NAME", ""))
async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        vad=silero.VAD.load(),
        # "multi" handles Hindi-English code-switching; use "en" if callers are English-only.
        stt=deepgram.STT(model="nova-3", language=os.getenv("STT_LANGUAGE", "multi")),
        llm=build_llm(),
        tts=build_tts(),
        turn_handling=TurnHandlingOptions(turn_detection=MultilingualModel()),
    )

    await session.start(room=ctx.room, agent=Receptionist())

    # Fixed greeting via say(): no LLM round-trip, so the caller hears audio instantly.
    b = BUSINESS
    await session.say(f"Hello, thank you for calling {b['name']}. This is {b['assistant_name']}. How can I help you?")


if __name__ == "__main__":
    agents.cli.run_app(server)
