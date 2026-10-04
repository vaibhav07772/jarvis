"""Wake word test — using working device (TWS headset)"""
import numpy as np
import sounddevice as sd
from openwakeword.model import Model
import time

print("="*60)
print("JARVIS — Wake Word Test")
print("="*60)

# Use working device
DEVICE = 2
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280

# Verify device
info = sd.query_devices(DEVICE)
print(f"\n🎤 Device [{DEVICE}]: {info['name']}")

# Load model
print("\n🎙️  Loading wake word model...")
model = Model(
    wakeword_models=["hey_jarvis"],
    inference_framework="onnx",
)
print("✅ Model loaded")

# Test with device's native rate
try:
    sd.check_input_settings(
        device=DEVICE,
        channels=1,
        samplerate=SAMPLE_RATE,
        dtype='int16',
    )
    NATIVE_RATE = SAMPLE_RATE
    print(f"\n✅ Using 16kHz")
except Exception:
    NATIVE_RATE = int(info['default_samplerate'])
    print(f"\n⚠️ Using native: {NATIVE_RATE} Hz")

# Adjust chunk size for native rate
chunk_size = int(CHUNK_SIZE * NATIVE_RATE / 16000)

print(f"\n🎯 Say 'Hey Jarvis' loudly for 20 seconds")
print(f"   Mic ke 10-15 cm paas bolo\n")

max_score = 0.0
start_time = time.time()
detect_count = 0

def audio_callback(indata, frames, time_info, status):
    global max_score, detect_count

    if status:
        print(f"⚠️ {status}")

    audio_data = indata[:, 0]

    # Resample to 16kHz if needed
    if NATIVE_RATE != 16000:
        ratio = NATIVE_RATE / 16000
        new_len = int(len(audio_data) / ratio)
        audio_data = np.interp(
            np.linspace(0, len(audio_data), new_len),
            np.arange(len(audio_data)),
            audio_data,
        )
    audio_data = audio_data.astype(np.int16)

    # Predict
    prediction = model.predict(audio_data)
    score = prediction.get("hey_jarvis", 0.0)

    if score > max_score:
        max_score = score

    if score > 0.1:
        bar = "█" * int(score * 20)
        print(f"  hey_jarvis: {score:.3f} {bar}")

    if score > 0.5:
        detect_count += 1

try:
    with sd.InputStream(
        device=DEVICE,
        channels=1,
        samplerate=NATIVE_RATE,
        blocksize=chunk_size,
        callback=audio_callback,
        dtype='int16',
    ):
        while time.time() - start_time < 20:
            time.sleep(0.1)

except KeyboardInterrupt:
    pass

print(f"\n{'='*60}")
print(f"📊 MAX SCORE: {max_score:.4f}")
print(f"📊 DETECTIONS (>0.5): {detect_count}")
print(f"{'='*60}")

if max_score > 0.5:
    print("✅ WAKE WORD WORKS!")
elif max_score > 0.1:
    print("⚠️  Low score — louder bolo")
else:
    print("❌ Still 0 — check TWS connected?")