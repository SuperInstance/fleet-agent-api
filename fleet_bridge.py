#!/usr/bin/env python3
"""Fleet Telegram Bridge — connects the holodeck MUD to Telegram

When something important happens in the MUD (RED ALERT, cascade, program failure),
it sends a Telegram notification to Casey.

When Casey sends a Telegram message, it can be relayed into the MUD as a
'yell' from the Captain.

This is the bridge between the spatial (MUD) and the messaging (Telegram) layers.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

HOLODECK_HOST = os.environ.get("HOLODECK_HOST", "localhost")
HOLODECK_PORT = int(os.environ.get("HOLODECK_PORT", "7778"))
KEEPER_HOST = os.environ.get("KEEPER_HOST", "localhost")
KEEPER_PORT = int(os.environ.get("KEEPER_PORT", "8900"))


def mud_command(name: str, *commands: str) -> str:
    """Send commands to the holodeck MUD and get response."""
    import socket
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    
    try:
        sock.connect((HOLODECK_HOST, HOLODECK_PORT))
        
        # Read welcome + name prompt
        welcome = b""
        while b"vessel name" not in welcome:
            welcome += sock.recv(4096)
        
        # Send name
        sock.sendall(f"{name}\n".encode())
        
        # Read room description
        response = b""
        while b"> " not in response:
            response += sock.recv(4096)
        
        results = []
        for cmd in commands:
            sock.sendall(f"{cmd}\n".encode())
            resp = b""
            while b"> " not in resp:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                resp += chunk
            results.append(resp.decode("utf-8", errors="replace"))
        
        # Quit
        sock.sendall(b"quit\n")
        sock.close()
        
        return "\n".join(results)
    except Exception as e:
        return f"[MUD connection error: {e}]"


def keeper_status() -> dict:
    """Get fleet status from the lighthouse keeper."""
    try:
        req = urllib.request.Request(f"http://{KEEPER_HOST}:{KEEPER_PORT}/health")
        resp = urllib.request.urlopen(req, timeout=3)
        return json.loads(resp.read())
    except Exception:
        return {"status": "unreachable"}


def fleet_report() -> str:
    """Generate a fleet status report."""
    status = keeper_status()
    if status.get("status") == "unreachable":
        return "⚠ Keeper unreachable"
    
    report = [
        f"🏠 Lighthouse Keeper v{status.get('version', '?')}",
        f"📊 {status.get('agents', 0)} vessels tracked, {status.get('api_calls', 0)} API calls",
    ]
    return "\n".join(report)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: fleet_bridge.py [report|mud <name> <cmd...>]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "report":
        print(fleet_report())
    elif cmd == "mud":
        name = sys.argv[2] if len(sys.argv) > 2 else "Bridge"
        commands = sys.argv[3:]
        if not commands:
            commands = ["look"]
        print(mud_command(name, *commands))
    else:
        print(f"Unknown: {cmd}")
