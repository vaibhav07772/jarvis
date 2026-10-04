"""JARVIS — Streamlit Dashboard (text-input demo)"""
import sys
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import streamlit as st
from dotenv import load_dotenv

from src.tools.jarvis_tools import TOOLS_SCHEMA, execute_tool
from src.memory.jarvis_memory import JarvisMemory

load_dotenv()

# ─────────────────────────────────────────
# Page config
# ─────────────────────────────────────────
st.set_page_config(
    page_title="JARVIS",
    page_icon="🎙️",
    layout="wide",
)

# ─────────────────────────────────────────
# CSS
# ─────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: 700;
        background: linear-gradient(90deg, #00B4D8, #0077B6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0;
    }
    .sub-header {
        text-align: center;
        color: #6B7280;
        margin-bottom: 1.5rem;
    }
    .status-box {
        padding: 0.75rem;
        border-radius: 0.5rem;
        text-align: center;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    .status-listening { background: #D1FAE5; color: #065F46; }
    .status-thinking  { background: #FEF3C7; color: #92400E; }
    .status-speaking  { background: #DBEAFE; color: #1E40AF; }
    .fact-item {
        background: #F0F9FF;
        padding: 0.5rem;
        border-left: 3px solid #00B4D8;
        border-radius: 0.25rem;
        margin: 0.3rem 0;
        font-size: 0.9rem;
    }
    .tool-log {
        background: #F3F4F6;
        padding: 0.4rem 0.6rem;
        border-radius: 0.25rem;
        font-family: monospace;
        font-size: 0.8rem;
        margin: 0.2rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# Header
# ─────────────────────────────────────────
st.markdown('<h1 class="main-header">🎙️ JARVIS</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">Voice-first AI Assistant — Text Demo Mode</p>',
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────
# Initialize session state
# ─────────────────────────────────────────
if "memory" not in st.session_state:
    with st.spinner("Initializing JARVIS memory..."):
        st.session_state.memory = JarvisMemory()

if "history" not in st.session_state:
    st.session_state.history = []

if "tool_log" not in st.session_state:
    st.session_state.tool_log = []

if "llm_client" not in st.session_state:
    from groq import Groq
    import os
    st.session_state.llm_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

if "conversation" not in st.session_state:
    st.session_state.conversation = [
        {"role": "system", "content": """You are JARVIS, Iron Man inspired AI assistant.
Be concise (max 2-3 sentences). Call user "sir". No emojis, no markdown.
Use tools when needed."""}
    ]


# ─────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧠 Known Facts")
    facts = st.session_state.memory.get_all_facts()
    if facts:
        for k, v in facts.items():
            st.markdown(
                f'<div class="fact-item"><b>{k}:</b> {v}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No facts yet")

    st.markdown("---")
    st.markdown("### 📊 Session Stats")
    st.metric("Queries", len(st.session_state.history) // 2)
    st.metric("Tools used", len(st.session_state.tool_log))
    st.metric("Facts learned", len(facts))

    st.markdown("---")
    st.markdown("### 🔧 Available Tools")
    for tool in ["🌤️ Weather", "⏰ Time", "📅 Date", "💻 System Info", "🧮 Calculator", "📚 Wikipedia"]:
        st.caption(tool)

    st.markdown("---")
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.history = []
        st.session_state.conversation = [
            {"role": "system", "content": """You are JARVIS, Iron Man inspired AI assistant.
Be concise. Call user "sir". No emojis."""}
        ]
        st.rerun()


# ─────────────────────────────────────────
# Main area
# ─────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 💬 Conversation")
    
    # Chat history
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.history:
            if msg["role"] == "user":
                st.markdown(f"**👤 You:** {msg['content']}")
            else:
                st.markdown(f"**🤖 JARVIS:** {msg['content']}")
                st.markdown("---")

    # Input
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Ask JARVIS:",
            placeholder="e.g., What is my name? / Weather in Mumbai? / Calculate 25 times 4",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("🎯 Send", use_container_width=True)

with col2:
    st.markdown("### 🔧 Tool Activity")
    if st.session_state.tool_log:
        for log in st.session_state.tool_log[-10:][::-1]:
            st.markdown(
                f'<div class="tool-log">→ {log}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No tools used yet")


# ─────────────────────────────────────────
# Process input
# ─────────────────────────────────────────
if submitted and user_input.strip():
    user_text = user_input.strip()
    
    # Add user message
    st.session_state.history.append({"role": "user", "content": user_text})

    # ─── Status: thinking ───
    status_placeholder = st.empty()
    status_placeholder.markdown(
        '<div class="status-box status-thinking">🧠 Thinking...</div>',
        unsafe_allow_html=True,
    )

    # ─── Memory context ───
    memory_context = st.session_state.memory.get_context_for_llm(user_text)

    # ─── Build messages ───
    st.session_state.conversation.append({"role": "user", "content": user_text})

    messages = [st.session_state.conversation[0]]
    if memory_context:
        messages.append({
            "role": "system",
            "content": f"Context from memory:\n{memory_context}",
        })
    messages += st.session_state.conversation[-10:]

    # ─── First LLM call ───
    client = st.session_state.llm_client
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
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
        messages.append(message)

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
            except json.JSONDecodeError:
                tool_args = {}

            # Log
            st.session_state.tool_log.append(f"{tool_name}({tool_args})")

            result = execute_tool(tool_name, tool_args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
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

    # ─── Save to memory ───
    st.session_state.memory.save_conversation(user_text, reply)

    # ─── Auto-extract facts ───
    import re
    match = re.search(r"(?:my name is|i am|i'm)\s+([A-Z][a-z]+)", user_text)
    if match:
        st.session_state.memory.save_fact("name", match.group(1))

    match = re.search(r"(?:i live in|i'm from)\s+([A-Z][a-z]+)", user_text)
    if match:
        st.session_state.memory.save_fact("city", match.group(1))

    # ─── Save conversation ───
    st.session_state.history.append({"role": "assistant", "content": reply})
    st.session_state.conversation.append({"role": "assistant", "content": reply})

    # ─── Clear status ───
    status_placeholder.empty()

    st.rerun()