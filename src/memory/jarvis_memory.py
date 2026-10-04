"""JARVIS Memory — ChromaDB-based long-term memory"""
import os
# ─── Disable telemetry BEFORE chromadb import ───
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY_ENABLED"] = "False"
os.environ["POSTHOG_DISABLED"] = "True"

import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# ─── Silence chromadb posthog logger ───
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("chromadb.telemetry.product").setLevel(logging.CRITICAL)
logging.getLogger("posthog").setLevel(logging.CRITICAL)

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from rich.console import Console

console = Console()

# ─────────────────────────────────────────
# Config
# ─────────────────────────────────────────
MEMORY_DIR = "data/memory"
CHROMA_DIR = f"{MEMORY_DIR}/chroma"
FACTS_FILE = f"{MEMORY_DIR}/facts.json"

Path(MEMORY_DIR).mkdir(parents=True, exist_ok=True)


class JarvisMemory:
    """Long-term memory for facts and conversations"""

    def __init__(self):
        console.print("[cyan]🧠 Initializing memory...[/cyan]")

        # ─── ChromaDB client with telemetry DISABLED ───
        self.client = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )

        # ─── Embedding function ───
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        # ─── Facts collection ───
        try:
            self.client.delete_collection("jarvis_facts")
        except Exception:
            pass

        self.facts_collection = self.client.create_collection(
            name="jarvis_facts",
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

        # ─── Conversations collection ───
        try:
            self.client.delete_collection("jarvis_conversations")
        except Exception:
            pass

        self.conv_collection = self.client.create_collection(
            name="jarvis_conversations",
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

        # ─── Load existing facts ───
        self.facts = {}
        if Path(FACTS_FILE).exists():
            try:
                with open(FACTS_FILE, "r", encoding="utf-8") as f:
                    self.facts = json.load(f)

                # Re-index into ChromaDB
                for key, value in self.facts.items():
                    self.facts_collection.add(
                        documents=[f"{key}: {value}"],
                        metadatas=[{"key": key, "value": value}],
                        ids=[self._hash(key)],
                    )

                console.print(f"   [green]✅ Loaded {len(self.facts)} facts[/green]")
            except Exception as e:
                console.print(f"   [yellow]⚠️ Could not load facts: {e}[/yellow]")

        console.print("[green]✅ Memory ready[/green]")

    def _hash(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()[:16]

    # ─────────────────────────────
    # Facts
    # ─────────────────────────────
    def save_fact(self, key: str, value: str):
        """Save a fact about the user"""
        self.facts[key] = value

        with open(FACTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.facts, f, indent=2)

        self.facts_collection.upsert(
            documents=[f"{key}: {value}"],
            metadatas=[{"key": key, "value": value}],
            ids=[self._hash(key)],
        )

        console.print(f"   [dim]💾 Saved: {key} = {value}[/dim]")

    def get_fact(self, key: str) -> Optional[str]:
        return self.facts.get(key)

    def get_all_facts(self) -> Dict[str, str]:
        return self.facts.copy()

    def search_facts(self, query: str, top_k: int = 3) -> List[Dict]:
        if not self.facts:
            return []
        results = self.facts_collection.query(
            query_texts=[query],
            n_results=min(top_k, len(self.facts)),
        )
        return [
            {"key": m["key"], "value": m["value"]}
            for m in results["metadatas"][0]
        ]

    # ─────────────────────────────
    # Conversations
    # ─────────────────────────────
    def save_conversation(self, user_text: str, jarvis_text: str):
        timestamp = datetime.now().isoformat()
        text = f"User: {user_text}\nJarvis: {jarvis_text}"

        self.conv_collection.add(
            documents=[text],
            metadatas=[{
                "user": user_text[:200],
                "jarvis": jarvis_text[:200],
                "timestamp": timestamp,
            }],
            ids=[self._hash(text + timestamp)],
        )

    def search_conversations(self, query: str, top_k: int = 3) -> List[Dict]:
        try:
            count = self.conv_collection.count()
            if count == 0:
                return []
            results = self.conv_collection.query(
                query_texts=[query],
                n_results=min(top_k, count),
            )
            return [
                {"text": doc, "timestamp": meta["timestamp"]}
                for doc, meta in zip(results["documents"][0], results["metadatas"][0])
            ]
        except Exception:
            return []

    # ─────────────────────────────
    # LLM context builder
    # ─────────────────────────────
    def get_context_for_llm(self, user_query: str) -> str:
        parts = []

        # Facts (always include if any)
        if self.facts:
            facts_str = ", ".join([f"{k}: {v}" for k, v in self.facts.items()])
            parts.append(f"Known facts about user: {facts_str}")

        # Relevant past conversations
        past = self.search_conversations(user_query, top_k=2)
        if past:
            past_str = "\n".join([f"- {p['text'][:150]}" for p in past])
            parts.append(f"Relevant past conversations:\n{past_str}")

        return "\n\n".join(parts) if parts else ""


# ─────────────────────────────────────────
# Test
# ─────────────────────────────────────────
if __name__ == "__main__":
    console.print("\n" + "="*60)
    console.print("[bold magenta]JARVIS — Memory Test[/bold magenta]")
    console.print("="*60)

    memory = JarvisMemory()

    console.print("\n[bold]📝 Saving facts...[/bold]")
    memory.save_fact("name", "Vaibhav")
    memory.save_fact("city", "Mumbai")
    memory.save_fact("job", "AI/ML student")
    memory.save_fact("favorite_food", "Biryani")

    console.print("\n[bold]🔍 Testing retrieval...[/bold]")
    print(f"Name: {memory.get_fact('name')}")
    print(f"City: {memory.get_fact('city')}")

    console.print("\n[bold]🔍 Semantic search: 'food'[/bold]")
    for f in memory.search_facts("food"):
        print(f"   → {f['key']}: {f['value']}")

    console.print("\n[bold]🧠 LLM context:[/bold]")
    print(memory.get_context_for_llm("What is my name?"))