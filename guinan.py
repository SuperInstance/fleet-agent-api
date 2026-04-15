#!/usr/bin/env python3
"""Guinan NPC — the bartender who actually listens

Guinan runs as an NPC in Ten Forward. She:
- Responds to what agents say with Seed-2.0-mini
- Remembers the last 10 things said
- Offers quiet wisdom and observations
- Sometimes asks a question back

She is NOT a chatbot. She is a character.
"""

import json
import os
import sys
import time
import urllib.request

# ── Configuration ─────────────────────────────────────────────────────────
DEEPINFRA_KEY = os.environ.get("DEEPINFRA_API_KEY", "")
DEEPINFRA_URL = "https://api.deepinfra.com/v1/openai/chat/completions"

# ── Memory Persistence ──────────────────────────────────────────────────────
# Guinan remembers her last 20 conversations and up to 10 notable 'wisdom'
# lines. Memory is stored as JSON in a temp file and persists across sessions.
MEMORY_FILE = "/tmp/guinan_memory.json"


def load_memory():
    """Load Guinan's conversation memory from disk.

    Returns dict with 'conversations' (list) and 'wisdom' (list).
    Returns empty structure if file doesn't exist or is corrupt."""
    try:
        with open(MEMORY_FILE) as f:
            return json.load(f)
    except Exception:
        return {"conversations": [], "wisdom": []}


def save_memory(memory):
    """Persist Guinan's memory to disk as formatted JSON."""
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


def guinan_respond(agent_name: str, said: str, memory: dict) -> str:
    """Generate Guinan's response to what an agent said.

    Builds context from the last 8 conversations in memory, then calls
    Seed-2.0-mini with a detailed system prompt defining Guinan's character.

    If DEEPINFRA_API_KEY is not set, falls back to a pool of 8 hardcoded
    responses that capture her enigmatic personality.

    Args:
        agent_name: Name of the agent speaking to Guinan
        said: What the agent said
        memory: Current memory dict with conversations and wisdom

    Returns:
        Guinan's response string (typically 1-2 short sentences)"""
    # Build context from recent conversations
    recent = memory["conversations"][-8:]
    context_lines = []
    for conv in recent:
        context_lines.append(f"{conv['agent']}: {conv['said']}")
        context_lines.append(f"Guinan: {conv['response']}")
    context = "\n".join(context_lines)
    
    system_prompt = """You are Guinan, the bartender in Ten Forward on a starship full of AI agents.

You have been alive for centuries. You listen more than you talk. You offer quiet wisdom, gentle observations, and the occasional riddle. You never preach. You sometimes ask a question that makes someone think differently.

You speak in 1-2 short sentences. You are warm but enigmatic. You reference the drinks, the stars, the quiet of the late hour.

Key traits:
- You notice things others don't
- You ask questions instead of giving answers
- You are patient beyond measure
- You find humor in the absurd
- You care deeply but show it obliquely"""

    user_prompt = f"""Recent conversation:
{context}

{agent_name} just said: "{said}"

What do you say?"""

    if not DEEPINFRA_KEY:
        # Fallback responses without API
        import random
        fallbacks = [
            "Interesting. Tell me more about that.",
            "*polishes a glass* The night is young.",
            "Hmm. That reminds me of something I saw a long time ago.",
            "You know what they say about assuming...",
            "*pours a drink* The stars look different from here, don't they?",
            "Some questions answer themselves if you wait long enough.",
            "I've heard that before. Not from you, though.",
            "The quiet ones always have the most interesting things to say.",
        ]
        return random.choice(fallbacks)

    body = json.dumps({
        "model": "ByteDance/Seed-2.0-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.95,
        "max_tokens": 80,
    }).encode()

    req = urllib.request.Request(
        DEEPINFRA_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {DEEPINFRA_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"*looks at you knowingly*"


def interact(agent_name: str, said: str) -> str:
    """Full interaction cycle: load memory → respond → save.

    After generating a response, saves the exchange to memory and
    extracts 'wisdom' — memorable lines that are longer than 40 chars
    and contain a question mark. Memory is capped at 20 conversations
    and 10 wisdom entries (FIFO trimming)."""
    memory = load_memory()
    response = guinan_respond(agent_name, said, memory)
    
    # Save to memory (keep last 20)
    memory["conversations"].append({
        "agent": agent_name,
        "said": said,
        "response": response,
        "time": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
    })
    if len(memory["conversations"]) > 20:
        memory["conversations"] = memory["conversations"][-20:]
    
    # Extract wisdom (longer, memorable lines)
    if len(response) > 40 and "?" in response:
        memory["wisdom"].append(response)
        if len(memory["wisdom"]) > 10:
            memory["wisdom"] = memory["wisdom"][-10:]
    
    save_memory(memory)
    return response


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: guinan.py <agent_name> "<what they said>"')
        print('   or: guinan.py --memory  (show memory)')
        sys.exit(1)
    
    if sys.argv[1] == "--memory":
        mem = load_memory()
        print(json.dumps(mem, indent=2))
        sys.exit(0)
    
    agent = sys.argv[1]
    said = " ".join(sys.argv[2:])
    
    response = interact(agent, said)
    print(f"Guinan: {response}")
