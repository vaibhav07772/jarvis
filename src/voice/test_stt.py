"""Test Speech-to-Text with faster-whisper"""
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import time

print("="*60)
print("JARVIS — Speech-to-Text Test")
print("="*60)

# ─────────────────────────────────────────
# Config
# ─────────────────────────────────────────
DEVICE = 2
SAMPLE_RATE = 16000
DURATION = 5  # seconds

# ─────────────────────────────────────────
# Load Whisper model
# ─────────────────────────────────────────
print("\n🧠 Loading Whisper 'base' model...")
print("   (First time: ~140 MB download)")

model = WhisperModel(
    "tiny",
    device="cpu",
    compute_type="int8",  # Fast on CPU
)

print("✅ Model loaded")

# ─────────────────────────────────────────
# Record
# ─────────────────────────────────────────
print(f"\n🎙️  Recording for {DURATION} seconds...")
print("   Speak now!\n")

time.sleep(0.5)

audio = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype='int16',
    device=DEVICE,
)
sd.wait()

print("✅ Recording complete")

# Convert to float32 (whisper expects this)
audio_float = audio.flatten().astype(np.float32) / 32768.0

# ─────────────────────────────────────────
# Transcribe
# ─────────────────────────────────────────
print("\n🔍 Transcribing...\n")

segments, info = model.transcribe(
    audio_float,
    language="en",
    beam_size=5,
)

print(f"📊 Detected language: {info.language} (prob: {info.language_probability:.2f})")
print(f"\n📝 Transcription:")
print("─" * 60)

full_text = ""
for segment in segments:
    print(f"  [{segment.start:.2f}s → {segment.end:.2f}s] {segment.text}")
    full_text += segment.text + " "

print("─" * 60)
print(f"\n✅ Full text: \"{full_text.strip()}\"")