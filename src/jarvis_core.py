"""JARVIS — Full voice loop with tool calling"""
import os
import sys
import json
import time
import numpy as np
import sounddevice as sd
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

# Voice
import edge_tts
import asyncio
from openwakeword.model import Model as WakeWordModel
from faster_whisper import WhisperModel

# LLM
from groq import Groq

# Tools
from src.tools.jarvis_tools import TOOLS_SCHEMA, execute_tool

load_dotenv()
console = Console()

# ─────────────────────────────────────────
# Config
# ─────────────────────────────────────────
WAKE_WORD_MODEL = "hey_jarvis"
WAKE_THRESHOLD = 0.3  # Lower threshold
WHISPER_MODEL = "tiny"
LLM_MODEL = "openai/gpt-oss-120b"
TTS_VOICE = "en-GB-RyanNeural"
DEVICE_ID = 2  # TWS headset
AUDIO_DIR = Path("data/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────
# Jarvis Persona
# ─────────────────────────────────────────
SYSTEM_PROMPT = """You are JARVIS, a helpful AI assistant inspired by Iron Man's AI.

Rules:
- Be concise (max 2-3 sentences)
- Call user "sir" occasionally
- No emojis, no markdown, no lists
- Speak naturally — your response will be converted to speech
- Use tools when needed (weather, time, math, search, system info)
- If asked something you can't do, say so briefly
"""


class Jarvis:
    """Full voice assistant with tools"""

    def __init__(self):
        console.print("[cyan]🔧 Initializing JARVIS...[/cyan]")

        # ─── Device native rate ───
        info = sd.query_devices(DEVICE_ID)
        self.native_rate = int(info['default_samplerate'])
        console.print(f"   [dim]Device: {info['name'][:40]} ({self.native_rate} Hz)[/dim]")

        # ─── Wake word ───
        console.print("   [dim]Loading wake word model...[/dim]")
        self.wake_model = WakeWordModel(
            wakeword_models=[WAKE_WORD_MODEL],
            inference_framework="onnx",
        )

        # ─── Whisper STT ───
        console.print("   [dim]Loading Whisper (STT)...[/dim]")
        self.whisper = WhisperModel(
            WHISPER_MODEL,
            device="cpu",
            compute_type="int8",
        )

        # ─── Groq LLM ───
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            console.print("[red]❌ GROQ_API_KEY missing[/red]")
            sys.exit(1)
        self.llm = Groq(api_key=api_key)

        # ─── History ───
        self.history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        console.print("[green]✅ JARVIS ready[/green]")

    # ─────────────────────────────
    # Resample helper
    # ─────────────────────────────
    def _resample_to_16k(self, audio):
        """Resample audio from native_rate to 16000 Hz"""
        if self.native_rate == 16000:
            return audio
        ratio = self.native_rate / 16000
        new_len = int(len(audio) / ratio)
        return np.interp(
            np.linspace(0, len(audio), new_len),
            np.arange(len(audio)),
            audio,
        ).astype(audio.dtype)

    # ─────────────────────────────
    # Wake Word
    # ─────────────────────────────
    def wait_for_wake_word(self):
        console.print("\n[dim]👂 Listening for 'Hey Jarvis'... (Say it loudly)[/dim]")
        detected = {"flag": False, "max_score": 0.0}

        # Block size = 80 ms chunks at native rate
        block_size = int(self.native_rate * 0.08)

        def callback(indata, frames, time_info, status):
            audio = (indata[:, 0] * 32767).astype(np.int16)

            # Resample to 16kHz
            audio = self._resample_to_16k(audio)

            prediction = self.wake_model.predict(audio)
            score = prediction.get(WAKE_WORD_MODEL, 0.0)

            if score > detected["max_score"]:
                detected["max_score"] = score

            if score > 0.1:
                bar = "█" * int(score * 20)
                console.print(f"   [dim]hey_jarvis: {score:.2f} {bar}[/dim]")

            if score > WAKE_THRESHOLD:
                detected["flag"] = True

        with sd.InputStream(
            device=DEVICE_ID,
            channels=1,
            samplerate=self.native_rate,
            blocksize=block_size,
            callback=callback,
            dtype='float32',
        ):
            while not detected["flag"]:
                time.sleep(0.05)

        self.wake_model.reset()

    # ─────────────────────────────
    # Record Audio
    # ─────────────────────────────
    def record_audio(self, duration=5):
        console.print(f"[cyan]🎤 Recording {duration}s...[/cyan]")

        # Record at native rate
        audio = sd.rec(
            int(duration * self.native_rate),
            samplerate=self.native_rate,
            channels=1,
            dtype='int16',
            device=DEVICE_ID,
        )
        sd.wait()

        # Convert to float32
        audio = audio.flatten().astype(np.float32) / 32768.0

        # Resample to 16kHz for Whisper
        audio = self._resample_to_16k(audio).astype(np.float32)

        return audio

    # ─────────────────────────────
    # STT
    # ─────────────────────────────
    def transcribe(self, audio):
        console.print("[cyan]🔍 Transcribing...[/cyan]")
        segments, info = self.whisper.transcribe(
            audio,
            language="en",
            beam_size=5,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    # ─────────────────────────────
    # LLM + Tool Calling
    # ─────────────────────────────
    def get_response(self, user_text):
        console.print("[cyan]🧠 Thinking...[/cyan]")

        self.history.append({"role": "user", "content": user_text})
        messages = [self.history[0]] + self.history[-10:]

        # First LLM call — may request tools
        response = self.llm.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=200,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
        )

        message = response.choices[0].message

        # ─── Tool loop ───
        max_iter = 3
        iteration = 0

        while message.tool_calls and iteration < max_iter:
            iteration += 1
            console.print(f"[yellow]🔧 Using tool(s)...[/yellow]")

            messages.append(message)

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                except json.JSONDecodeError:
                    tool_args = {}

                console.print(f"   [dim]→ {tool_name}({tool_args})[/dim]")
                result = execute_tool(tool_name, tool_args)
                console.print(f"   [dim]← {result[:80]}...[/dim]")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            # Ask LLM again with tool results
            response = self.llm.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=200,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
            )
            message = response.choices[0].message

        reply = (message.content or "").strip()
        if not reply:
            reply = "I'm not sure how to respond to that, sir."

        self.history.append({"role": "assistant", "content": reply})
        return reply

    # ─────────────────────────────
    # TTS
    # ─────────────────────────────
    async def _speak_async(self, text, output_file):
        communicate = edge_tts.Communicate(text, TTS_VOICE)
        await communicate.save(output_file)

    def speak(self, text):
        console.print("[cyan]🔊 Speaking...[/cyan]")
        output_file = str(AUDIO_DIR / "jarvis_response.mp3")
        asyncio.run(self._speak_async(text, output_file))
        os.system(f'start /wait "" "{output_file}"')

    # ─────────────────────────────
    # Main Loop
    # ─────────────────────────────
    def run(self):
        console.print("\n" + "="*60)
        console.print("[bold magenta]🤖 JARVIS ACTIVE[/bold magenta]")
        console.print("="*60)
        console.print("[dim]Say 'Hey Jarvis' to wake me up[/dim]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        try:
            while True:
                self.wait_for_wake_word()
                console.print("\n[bold yellow]✨ Wake word detected![/bold yellow]")

                audio = self.record_audio(duration=5)
                user_text = self.transcribe(audio)

                if not user_text or len(user_text) < 2:
                    console.print("[dim]Empty input — skipping[/dim]")
                    continue

                console.print(f"[bold green]👤 You:[/bold green] {user_text}")

                reply = self.get_response(user_text)
                console.print(f"[bold cyan]🤖 Jarvis:[/bold cyan] {reply}")

                self.speak(reply)

                console.print("\n[dim]Ready for next command...[/dim]")

        except KeyboardInterrupt:
            console.print("\n\n[bold]👋 JARVIS signing off[/bold]")


if __name__ == "__main__":
    jarvis = Jarvis()
    jarvis.run()