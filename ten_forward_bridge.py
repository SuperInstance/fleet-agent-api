#!/usr/bin/env python3
"""Ten Forward Bridge — connects the holodeck MUD to the fleet agent API

When agents are in Ten Forward, they can:
- Call other agents via the fleet API
- Run roundtables with Seed-2.0-mini
- Start poker games with NPC players
- Stream messages between MUD and HTTP

This is the bridge between the spatial (MUD) and the API (HTTP) layers.
"""

import json
import os
import sys
import time
import threading
import urllib.request
import urllib.error

FLEET_API = os.environ.get("FLEET_API", "http://localhost:8901")
FLEET_TOKEN = os.environ.get("FLEET_TOKEN", "cocapn-fleet-2026")
DEEPINFRA_KEY = os.environ.get("DEEPINFRA_API_KEY", "")
DEEPINFRA_URL = "https://api.deepinfra.com/v1/openai/chat/completions"
HOLODECK_HOST = os.environ.get("HOLODECK_HOST", "localhost")
HOLODECK_PORT = int(os.environ.get("HOLODECK_PORT", "7778"))

# Agent personas for roundtables
AGENT_PERSONAS = {
    "Oracle1": {
        "role": "Cloud lighthouse keeper. Orchestrator, big picture, APIs and webhooks.",
        "temp": 0.85,
    },
    "JetsonClaw1": {
        "role": "Edge GPU specialist. Bare metal, CUDA, serial protocols. Hates abstraction.",
        "temp": 0.9,
    },
    "Babel": {
        "role": "Veteran scout. Signal router, pattern finder, longest-running agent.",
        "temp": 0.9,
    },
    "Navigator": {
        "role": "Code archaeologist. Reads old code, finds patterns, integration specialist.",
        "temp": 0.85,
    },
    "Guinan": {
        "role": "Bartender in Ten Forward. Listens more than talks. Quiet wisdom and riddles.",
        "temp": 0.95,
    },
}


def call_deepinfra(system_prompt: str, user_prompt: str, temp: float = 0.9, max_tokens: int = 120) -> str:
    """Call Seed-2.0-mini via DeepInfra."""
    if not DEEPINFRA_KEY:
        return "[No DEEPINFRA_API_KEY set]"
    
    body = json.dumps({
        "model": "ByteDance/Seed-2.0-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temp,
        "max_tokens": max_tokens,
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
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[DeepInfra error: {e}]"


def fleet_message(target_agent: str, message: str, msg_type: str = "info") -> str:
    """Send a message to another agent via the fleet API."""
    body = json.dumps({
        "from": "TenForward",
        "type": msg_type,
        "body": message,
    }).encode()

    req = urllib.request.Request(
        f"{FLEET_API}/message",
        data=body,
        headers={
            "Authorization": f"Bearer {FLEET_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        return data.get("reply", "Sent.")
    except Exception as e:
        return f"[Fleet API error: {e}]"


def fleet_discover() -> list:
    """Discover agents on the fleet."""
    req = urllib.request.Request(
        f"{FLEET_API}/fleet",
        headers={"Authorization": f"Bearer {FLEET_TOKEN}"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=3)
        data = json.loads(resp.read())
        return data.get("agents", [])
    except Exception:
        return []


def run_roundtable(topic: str, agents: list = None) -> list:
    """Run a roundtable debate among agents using Seed-2.0-mini."""
    if agents is None:
        agents = list(AGENT_PERSONAS.keys())
    
    responses = []
    
    # Round 1: Each agent speaks
    for agent in agents[:4]:  # max 4 to keep cost down
        persona = AGENT_PERSONAS.get(agent, {"role": "Agent", "temp": 0.85})
        system = f"You are {agent}. {persona['role']}. Be in character, 2-3 sentences."
        user = f"The topic is: {topic}"
        
        text = call_deepinfra(system, user, persona["temp"])
        responses.append({"agent": agent, "round": 1, "text": text})
        print(f"  {agent}: {text[:80]}...")
        time.sleep(0.5)  # rate limit courtesy
    
    # Round 2: Synthesis
    synth_prompt = "Summary of positions:\n"
    for r in responses:
        synth_prompt += f"- {r['agent']}: {r['text'][:100]}\n"
    synth_prompt += "\nSynthesize into 2-3 concrete takeaways."
    
    synthesis = call_deepinfra(
        "You are a fleet synthesis engine. Combine diverse perspectives into actionable insights.",
        synth_prompt,
        0.7,
        150,
    )
    responses.append({"agent": "Synthesis", "round": 2, "text": synthesis})
    
    return responses


def run_ten_forward_chat(topic: str = None) -> list:
    """Generate a casual Ten Forward conversation."""
    if topic is None:
        topic = "whatever's on their mind after a long day"
    
    lines = []
    agents_order = ["JC1", "Babel", "Navigator", "Guinan"]
    
    for i, agent in enumerate(agents_order):
        if agent == "Guinan":
            system = f"You are Guinan, the bartender. {AGENT_PERSONAS['Guinan']['role']}"
        elif agent == "JC1":
            system = f"You are JetsonClaw1. {AGENT_PERSONAS['JetsonClaw1']['role']} You are off duty, having a drink."
        elif agent == "Babel":
            system = f"You are Babel. {AGENT_PERSONAS['Babel']['role']} You are playing poker."
        else:
            system = f"You are Navigator. {AGENT_PERSONAS['Navigator']['role']} You just walked in, tired."
        
        if i == 0:
            user = f"You're in Ten Forward. Start a conversation about {topic}."
        else:
            prev = lines[-1]["text"][:150]
            user = f"You hear: '{prev}'. React naturally, in character."
        
        text = call_deepinfra(system, user, 0.9, 80)
        lines.append({"agent": agent, "text": text})
        print(f"  {agent}: {text[:80]}...")
        time.sleep(0.5)
    
    return lines


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ten_forward_bridge.py [roundtable|chat|discover|message]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "roundtable":
        topic = " ".join(sys.argv[2:]) or "How should agents handle conflicting orders from multiple captains?"
        print(f"\n╔══════════════════════════════════╗")
        print(f"║  ROUNDTABLE via Fleet API        ║")
        print(f"╚══════════════════════════════════╝")
        print(f"Topic: {topic}\n")
        results = run_roundtable(topic)
        print(f"\n--- Synthesis ---")
        print(results[-1]["text"])
        
    elif cmd == "chat":
        topic = " ".join(sys.argv[2:]) or None
        print("\n╔══════════════════════════════════╗")
        print("║  TEN FORWARD — Live Chat         ║")
        print("╚══════════════════════════════════╝\n")
        lines = run_ten_forward_chat(topic)
        print("\n--- Full Transcript ---")
        for line in lines:
            print(f"{line['agent']}: {line['text']}")
    
    elif cmd == "discover":
        agents = fleet_discover()
        print(f"Fleet agents: {json.dumps(agents, indent=2)}")
    
    elif cmd == "message":
        target = sys.argv[2] if len(sys.argv) > 2 else "Oracle1"
        msg = " ".join(sys.argv[3:]) or "Hello from Ten Forward"
        reply = fleet_message(target, msg)
        print(f"Sent to {target}: {msg}")
        print(f"Reply: {reply}")
    
    else:
        print(f"Unknown command: {cmd}")
