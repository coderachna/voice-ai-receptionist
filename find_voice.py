"""Find an ElevenLabs voice your free plan can use via the API:  python find_voice.py

Lists the voices in your account, tries each with a tiny request ("Hi.", about 3 credits),
and saves the first one that works into .env as ELEVEN_VOICE_ID.
"""
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv, set_key

ENV = Path(__file__).with_name(".env")
load_dotenv(ENV)
KEY = os.environ["ELEVEN_API_KEY"]
MODEL = os.getenv("ELEVEN_MODEL", "eleven_flash_v2_5")
MAX_TRIES = 15


def call(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"xi-api-key": KEY, "Content-Type": "application/json",
                                          "User-Agent": "find-voice"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


voices = json.loads(call("https://api.elevenlabs.io/v1/voices"))["voices"]
print(f"Your account has {len(voices)} voices. Testing up to {MAX_TRIES}...\n")

# Voices you created yourself are most likely to work on free, so try those first.
voices.sort(key=lambda v: v.get("category") not in ("generated", "cloned"))

for v in voices[:MAX_TRIES]:
    name, vid, cat = v["name"], v["voice_id"], v.get("category", "?")
    try:
        call(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}", {"text": "Hi.", "model_id": MODEL})
    except urllib.error.HTTPError as e:
        print(f"  [no]  {name:<30} ({cat}) - HTTP {e.code}")
        continue
    print(f"  [YES] {name:<30} ({cat})")
    set_key(str(ENV), "ELEVEN_VOICE_ID", vid, quote_mode="never")
    set_key(str(ENV), "TTS_PROVIDER", "elevenlabs", quote_mode="never")
    print(f"\nSaved {name} to .env. Now run:  python agent.py console")
    break
else:
    print("\nNo voice in your account works on the free API plan.")
    print("Option A: create your own voice with Voice Design on elevenlabs.io, then run this again.")
    print("Option B: use Deepgram's voice: set TTS_PROVIDER=deepgram in .env")
