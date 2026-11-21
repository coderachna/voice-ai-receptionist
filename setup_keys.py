"""Easy key setup. Run:  python setup_keys.py

For each service it opens the right website, tells you what to click,
asks you to paste the key, tests it right away, and saves it into .env.
You never have to edit .env by hand.
"""
import json
import os
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from dotenv import load_dotenv, set_key

HERE = Path(__file__).parent
ENV = HERE / ".env"
if not ENV.exists():
    ENV.write_text((HERE / ".env.example").read_text())
load_dotenv(ENV, override=True)

PLACEHOLDERS = ("", "wss://your-project.livekit.cloud")


def get_json(url, headers):
    req = urllib.request.Request(url, headers={**headers, "User-Agent": "setup-keys"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


# ---------- tests: return a success message, or raise with a reason ----------

def test_groq(key):
    models = [m["id"] for m in get_json(
        "https://api.groq.com/openai/v1/models", {"Authorization": f"Bearer {key}"})["data"]]
    current = os.getenv("GROQ_MODEL", "")
    if current not in models:
        for choice in ("openai/gpt-oss-20b", "openai/gpt-oss-120b"):
            if choice in models:
                save("GROQ_MODEL", choice)
                return f"key works. Model set to {choice}"
        return f"key works, but pick a model from this list for GROQ_MODEL in .env: {', '.join(models)}"
    return f"key works. Model {current} is available"


def test_deepgram(key):
    get_json("https://api.deepgram.com/v1/projects", {"Authorization": f"Token {key}"})
    return "key works"


def test_eleven_key(key):
    get_json("https://api.elevenlabs.io/v1/voices", {"xi-api-key": key})
    return "key works"


def test_eleven_voice(voice_id):
    v = get_json(f"https://api.elevenlabs.io/v1/voices/{voice_id}",
                 {"xi-api-key": os.environ["ELEVEN_API_KEY"]})
    return f"voice found: {v.get('name')}"


def test_lk_url(url):
    if not url.startswith("wss://"):
        raise ValueError("the URL must start with wss://")
    return "looks right"


def test_not_empty(value):
    if len(value) < 8:
        raise ValueError("that looks too short, copy the full value")
    return "saved"


# ---------- the guided steps ----------

SERVICES = [
    {
        "name": "GROQ  (the AI brain)",
        "url": "https://console.groq.com/keys",
        "how": [
            "Sign in with Google.",
            "Click the button 'Create API Key'.",
            "Type the name: receptionist   then click Submit.",
            "Click the copy icon next to the key (it starts with gsk_).",
        ],
        "fields": [("GROQ_API_KEY", "Groq API key", test_groq)],
    },
    {
        "name": "DEEPGRAM  (turns speech into text)",
        "url": "https://console.deepgram.com/",
        "how": [
            "Sign up with Google. Skip or answer any welcome questions.",
            "In the left menu click 'API Keys'.",
            "Click 'Create a New API Key'. Name: receptionist. Keep other options as they are.",
            "Copy the key NOW. Deepgram shows it only once.",
        ],
        "fields": [("DEEPGRAM_API_KEY", "Deepgram API key", test_deepgram)],
    },
    {
        "name": "ELEVENLABS  (turns text into a voice)",
        "url": "https://elevenlabs.io/app/settings/api-keys",
        "how": [
            "Sign up (free plan). You should land on the API Keys page.",
            "Click 'Create API Key'. Turn ON 'Text to Speech'. Set 'Voices' to Read.",
            "Click Create and copy the key.",
            "Then for the voice: open 'Voices' in the left menu, pick a default voice,",
            "click the three dots next to it and choose 'Copy voice ID'.",
        ],
        "fields": [
            ("ELEVEN_API_KEY", "ElevenLabs API key", test_eleven_key),
            ("ELEVEN_VOICE_ID", "ElevenLabs voice ID", test_eleven_voice),
        ],
    },
    {
        "name": "LIVEKIT  (connects the call; you can skip this for now with Enter)",
        "url": "https://cloud.livekit.io/",
        "how": [
            "Sign up and create a project named: ai-receptionist",
            "Open Settings -> API Keys and create a new key.",
            "You get 3 values: a URL starting with wss://, an API key, and a secret.",
            "Copy the secret now, it may be shown only once.",
        ],
        "fields": [
            ("LIVEKIT_URL", "LiveKit URL (starts with wss://)", test_lk_url),
            ("LIVEKIT_API_KEY", "LiveKit API key", test_not_empty),
            ("LIVEKIT_API_SECRET", "LiveKit API secret", test_not_empty),
        ],
    },
]


def save(var, value):
    set_key(str(ENV), var, value, quote_mode="never")
    os.environ[var] = value


def ask(var, label, test):
    current = os.getenv(var, "")
    has_current = current not in PLACEHOLDERS
    while True:
        hint = " (press Enter to keep the one already saved)" if has_current else " (press Enter to skip)"
        value = input(f"\n  Paste your {label}{hint}:\n  > ").strip().strip('"').strip("'")
        if not value:
            print("  - kept existing value" if has_current else "  - skipped")
            return
        try:
            msg = test(value)
            save(var, value)
            print(f"  [OK] {msg}. Saved to .env")
            return
        except urllib.error.HTTPError as e:
            print(f"  [FAIL] HTTP {e.code}: key is wrong or missing a permission. Copy it again.")
        except Exception as e:
            print(f"  [FAIL] {e}")
        if input("  Try again? (y/n): ").strip().lower() != "y":
            return


def main():
    print("\nThis will set up your keys one website at a time.")
    print("To paste in the VS Code terminal use Ctrl+V (or right-click).")
    for i, s in enumerate(SERVICES, 1):
        print("\n" + "=" * 60)
        print(f"STEP {i} of {len(SERVICES)}: {s['name']}")
        print("=" * 60)
        input("Press Enter to open the website in your browser...")
        webbrowser.open(s["url"])
        print("On that website:")
        for n, line in enumerate(s["how"], 1):
            print(f"  {n}. {line}")
        for var, label, test in s["fields"]:
            ask(var, label, test)
    print("\nAll done. Your keys are saved in .env")
    print("Next step: Google Calendar setup.\n")


if __name__ == "__main__":
    main()