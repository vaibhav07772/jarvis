"""Test Groq LLM integration"""
import os
from dotenv import load_dotenv
from groq import Groq
from rich.console import Console

load_dotenv()
console = Console()

# ─────────────────────────────────────────
# Setup
# ─────────────────────────────────────────
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    console.print("[red]❌ GROQ_API_KEY not found in .env[/red]")
    exit(1)

client = Groq(api_key=api_key)

# Jarvis system prompt
SYSTEM_PROMPT = """You are JARVIS, a helpful AI assistant inspired by Iron Man's AI.

Personality:
- Concise and efficient (max 2-3 sentences)
- Friendly but professional
- Call the user "sir" occasionally
- If asked to do something you can't, say so briefly

Response style:
- Speak naturally (you'll be converted to speech)
- No emojis, no markdown
- Short and clear answers
"""

def ask_jarvis(question: str) -> str:
    """Send question to LLM and get response"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.7,
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()


# ─────────────────────────────────────────
# Test
# ─────────────────────────────────────────
console.print("\n" + "="*60)
console.print("[bold cyan]JARVIS — LLM Test[/bold cyan]")
console.print("="*60)

test_questions = [
    "Hey Jarvis, what is the weather today?",
    "Who are you?",
    "What can you do?",
    "Tell me a joke",
]

for q in test_questions:
    console.print(f"\n[bold yellow]👤 User:[/bold yellow] {q}")
    response = ask_jarvis(q)
    console.print(f"[bold green]🤖 Jarvis:[/bold green] {response}")

console.print("\n" + "="*60)
console.print("[bold green]✅ LLM working[/bold green]")
console.print("="*60)