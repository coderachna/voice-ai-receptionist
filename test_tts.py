"""Find out why the voice isn't working:  python test_tts.py
Tries ElevenLabs and Deepgram voices directly, prints the REAL error message,
and saves an .mp3 for each one that works so you can play it."""
import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()
TEXT = "Hello, thank you for calling. How can I help you?"


def post(url, headers, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={**headers, "Content-Type": "application/json",
                                          "User-Agent": "tts-test"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def try_it(name, filename, fn):
    try:
        audio = fn()
        with open(filename, "wb") as f:
            f.write(audio)
        print(f"[OK]   {name}: works. Saved {filename} - double-click it to listen.")
    except urllib.error.HTTPError as e:
        print(f"[FAIL] {name}: HTTP {e.code}")
        print("       Reason from server:", e.read().decode(errors="replace")[:400])
    except Exception as e:
        print(f"[FAIL] {name}: {e}")


def eleven():
    voice = os.getenv("ELEVEN_VOICE_ID", "CwhRBWXzGAHq8TQ4Fs17")
    model = os.getenv("ELEVEN_MODEL", "eleven_flash_v2_5")
    return post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                {"xi-api-key": os.environ["ELEVEN_API_KEY"]},
                {"text": TEXT, "model_id": model})


def deepgram():
    model = os.getenv("DEEPGRAM_TTS_MODEL", "aura-2-thalia-en")
    return post(f"https://api.deepgram.com/v1/speak?model={model}",
                {"Authorization": f"Token {os.environ['DEEPGRAM_API_KEY']}"},
                {"text": TEXT})


try_it("ElevenLabs voice", "test_elevenlabs.mp3", eleven)
try_it("Deepgram voice", "test_deepgram.mp3", deepgram)
