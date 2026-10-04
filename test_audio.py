"""Record 5 sec and check if mic captures voice"""
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
import time

print("="*60)
print("MIC TEST — 5 second recording")
print("="*60)

# Show ALL input devices
devices = sd.query_devices()
input_devs = [(i, d) for i, d in enumerate(devices) if d['max_input_channels'] > 0]

print(f"\n{len(input_devs)} input devices found\n")

# Test each device quickly
SAMPLE_RATE = 16000
DURATION = 3

for dev_id, dev in input_devs[:5]:  # First 5 devices
    print(f"\n{'─'*60}")
    print(f"Testing device [{dev_id}]: {dev['name'][:50]}")
    print(f"{'─'*60}")

    print(f"🔴 Recording 3 seconds — BOLO KUCH ('Hello, testing')...")
    time.sleep(0.5)

    try:
        audio = sd.rec(
            int(DURATION * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='int16',
            device=dev_id,
        )
        sd.wait()

        # Check volume
        max_amp = np.abs(audio).max()
        mean_amp = np.abs(audio).mean()

        print(f"   Max amplitude: {max_amp}")
        print(f"   Mean amplitude: {mean_amp:.1f}")

        if max_amp > 1000:
            print(f"   ✅ SPEAKING DETECTED! (device {dev_id} works)")
            # Save file
            write(f"data/audio/test_{dev_id}.wav", SAMPLE_RATE, audio)
            print(f"   💾 Saved: data/audio/test_{dev_id}.wav")
        else:
            print(f"   ❌ SILENT — not capturing audio")

    except Exception as e:
        print(f"   ❌ Error: {e}")

print(f"\n{'='*60}")
print("✅ Test complete — check which device works")
print("="*60)