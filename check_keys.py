"""Run after filling .env:  python check_keys.py
Checks every API key with one tiny request, so you know they all work before touching voice."""
import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()


def get(url, headers):
    req = urllib.request.Request(url, headers={**headers, "User-Agent": "key-check"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def check(name, fn):
    try:
        msg = fn()
        print(f"[OK]   {name}: {msg}")
    except urllib.error.HTTPError as e:
        print(f"[FAIL] {name}: HTTP {e.code} - key wrong, expired, or missing permission")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")


def groq():
    key = os.environ["GROQ_API_KEY"]
    models = [m["id"] for m in get("https://api.groq.com/openai/v1/models",
                                   {"Authorization": f"Bearer {key}"})["data"]]
    want = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    if want not in models:
        raise Exception(f"key works, but model '{want}' not available. Pick one of: {', '.join(sorted(models))}")
    return f"key works, model '{want}' available"


def deepgram():
    key = os.environ["DEEPGRAM_API_KEY"]
    projects = get("https://api.deepgram.com/v1/projects", {"Authorization": f"Token {key}"})["projects"]
    return f"key works ({len(projects)} project)"


def elevenlabs():
    key = os.getenv("ELEVEN_API_KEY") or os.environ["ELEVENLABS_API_KEY"]
    vid = os.getenv("ELEVEN_VOICE_ID")
    if not vid:
        return "key present, no ELEVEN_VOICE_ID set (plugin default voice will be used)"
    v = get(f"https://api.elevenlabs.io/v1/voices/{vid}", {"xi-api-key": key})
    return f"key works, voice = {v.get('name')}"


def livekit():
    url, k, s = os.getenv("LIVEKIT_URL", ""), os.getenv("LIVEKIT_API_KEY"), os.getenv("LIVEKIT_API_SECRET")
    if not (url.startswith("wss://") and k and s):
        raise Exception("LIVEKIT_URL must start with wss:// and key + secret must be filled")
    return "all three values present (only needed for dev mode, not console)"


for n, f in [("Groq", groq), ("Deepgram", deepgram), ("ElevenLabs", elevenlabs), ("LiveKit", livekit)]:
    check(n, f)
