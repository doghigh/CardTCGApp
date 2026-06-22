"""
Lorebox Voice Assistant
-----------------------
Wake words:  "hey claude"      → routes to Claude API
             "hey perplexity"  → routes to Perplexity API

Setup:
    pip install SpeechRecognition pyaudio pyttsx3 anthropic requests
    On Linux: sudo apt-get install portaudio19-dev python3-pyaudio espeak

Environment variables (put in .env or export before running):
    ANTHROPIC_API_KEY   – your Anthropic key
    PERPLEXITY_API_KEY  – your Perplexity key
"""

import os
import sys
import threading
import queue
import time

try:
    import speech_recognition as sr
    import pyttsx3
    import anthropic
    import requests
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install SpeechRecognition pyaudio pyttsx3 anthropic requests")
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────────────────────
WAKE_CLAUDE      = "hey claude"
WAKE_PERPLEXITY  = "hey perplexity"
CLAUDE_MODEL     = "claude-sonnet-4-6"
PERPLEXITY_MODEL = "llama-3.1-sonar-large-128k-online"

ANTHROPIC_KEY    = os.getenv("ANTHROPIC_API_KEY", "")
PERPLEXITY_KEY   = os.getenv("PERPLEXITY_API_KEY", "")

# ── TTS engine ───────────────────────────────────────────────────────────────
tts = pyttsx3.init()
tts.setProperty("rate", 175)
tts.setProperty("volume", 1.0)

def speak(text: str) -> None:
    print(f"[speaking] {text}")
    tts.say(text)
    tts.runAndWait()

# ── Claude API ───────────────────────────────────────────────────────────────
def ask_claude(prompt: str) -> str:
    if not ANTHROPIC_KEY:
        return "Anthropic API key not set. Please export ANTHROPIC_API_KEY."
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text

# ── Perplexity API ────────────────────────────────────────────────────────────
def ask_perplexity(prompt: str) -> str:
    if not PERPLEXITY_KEY:
        return "Perplexity API key not set. Please export PERPLEXITY_API_KEY."
    resp = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={
            "Authorization": f"Bearer {PERPLEXITY_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": PERPLEXITY_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 512,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]

# ── Listener ──────────────────────────────────────────────────────────────────
recognizer = sr.Recognizer()
recognizer.energy_threshold = 300
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 1.2

def listen_for_speech(timeout: int = 8, phrase_limit: int = 15) -> str | None:
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.3)
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        except sr.WaitTimeoutError:
            return None
    try:
        return recognizer.recognize_google(audio).lower().strip()
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        print(f"[error] STT service error: {e}")
        return None

# ── Main loop ─────────────────────────────────────────────────────────────────
def run() -> None:
    print("=" * 50)
    print("  Lorebox Voice Assistant")
    print(f"  Say '{WAKE_CLAUDE}' or '{WAKE_PERPLEXITY}'")
    print("  Ctrl+C to quit")
    print("=" * 50)
    speak("Voice assistant ready. Say hey Claude or hey Perplexity to begin.")

    while True:
        print("\n[listening for wake word...]")
        text = listen_for_speech(timeout=None, phrase_limit=6)
        if not text:
            continue

        print(f"[heard] {text}")

        if WAKE_CLAUDE in text:
            router = ask_claude
            label  = "Claude"
        elif WAKE_PERPLEXITY in text:
            router = ask_perplexity
            label  = "Perplexity"
        else:
            continue

        # strip wake word from the text if the question was said in the same breath
        for wake in (WAKE_CLAUDE, WAKE_PERPLEXITY):
            text = text.replace(wake, "").strip()

        if not text:
            speak(f"{label} is listening.")
            print("[listening for question...]")
            text = listen_for_speech(timeout=8, phrase_limit=20)
            if not text:
                speak("I didn't catch that. Try again.")
                continue

        print(f"[question → {label}] {text}")
        speak(f"One moment.")

        try:
            answer = router(text)
        except Exception as e:
            answer = f"Sorry, I ran into an error: {e}"

        speak(answer)

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nGoodbye.")
        speak("Goodbye.")
