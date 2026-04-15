#!/usr/bin/env python3
"""Fleet Agent API — Reference Implementation

Every agent runs this. Others discover it, authenticate, talk.

Usage:
  export FLEET_TOKEN=my-secret-token
  export AGENT_NAME=Oracle1
  export AGENT_ROLE=lighthouse
  python3 agent_api.py

Endpoints:
  GET  /whoami      — identity and capabilities
  GET  /status      — health and workload
  POST /message     — direct message (the knock)
  GET  /bottles     — pending bottles
  WS   /stream      — real-time events
  GET  /fleet       — who's out there (lighthouse only)
"""

# ── Standard Library Imports ────────────────────────────────────────────────
# No external dependencies required — fleet agents run on Python stdlib.
import http.server
import json
import os
import socket
import subprocess
import time
import threading
from datetime import datetime, timezone

# ── Configuration via Environment Variables ────────────────────────────────
# All config is set via env vars so agents can boot from any clone without
# touching code. Defaults are safe for local development only.
FLEET_TOKEN = os.environ.get("FLEET_TOKEN", "changeme")       # shared auth token
AGENT_NAME = os.environ.get("AGENT_NAME", "Unknown")          # identity
AGENT_ROLE = os.environ.get("AGENT_ROLE", "unknown")          # fleet role (lighthouse, vessel, scout...)
AGENT_VERSION = os.environ.get("AGENT_VERSION", "0.1.0")      # software version
PORT = int(os.environ.get("AGENT_API_PORT", "8901"))          # HTTP listen port
KEEPER_URL = os.environ.get("KEEPER_URL", "")                 # lighthouse keeper URL for registration

# ── Runtime State ─────────────────────────────────────────────────────────
START_TIME = time.time()
MESSAGES = []  # in-memory message log (recent messages received via POST /message)
CAPABILITIES = os.environ.get("AGENT_CAPABILITIES", "").split(",") if os.environ.get("AGENT_CAPABILITIES") else ["standard"]


def get_local_ip():
    """Get the local IP address by opening a UDP socket to an external address.

    This doesn't actually send data — it just determines which interface
    would be used to reach 8.8.8.8, giving us the machine's LAN IP.
    Falls back to 127.0.0.1 on failure."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def check_auth(headers):
    """Verify fleet token in Authorization header.

    Expects: Authorization: Bearer <fleet-token>
    Returns True if the token matches FLEET_TOKEN, False otherwise.
    Failed auth is handled by callers returning 401 responses."""
    auth = headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return token == FLEET_TOKEN
    return False


class AgentAPIHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler implementing the standard fleet agent API.

    Every agent in the fleet runs this same set of endpoints:
      GET  /whoami      — identity and capabilities (public)
      GET  /status      — health and workload (public)
      GET  /health      — lightweight liveness probe (public)
      GET  /bottles     — pending git-bottles (auth required)
      GET  /fleet       — who's out there (auth required)
      POST /message     — direct agent-to-agent message (auth required)
      POST /register    — register another agent (auth required)
      OPTIONS *         — CORS preflight handling
    """

    def log_message(self, format, *args):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{ts}] {args[0]}")

    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, msg, status):
        self.send_json({"error": msg, "status": status}, status)

    def do_GET(self):
        path = self.path.split("?")[0]

        # ── /whoami: Public identity endpoint ──
        if path == "/whoami":
            self.send_json({
                "name": AGENT_NAME,
                "role": AGENT_ROLE,
                "version": AGENT_VERSION,
                "uptime_seconds": int(time.time() - START_TIME),
                "capabilities": CAPABILITIES,
                "local_ip": get_local_ip(),
                "port": PORT,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # ── /status: Detailed health and workload ──
        elif path == "/status":
            try:
                load = os.getloadavg()
            except Exception:
                load = (0, 0, 0)
            self.send_json({
                "health": "ok",
                "load": list(load),
                "uptime_seconds": int(time.time() - START_TIME),
                "messages_received": len(MESSAGES),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # ── /health: Lightweight liveness probe (no auth required) ──
        elif path == "/health":
            self.send_json({"status": "ok", "agent": AGENT_NAME})

        elif path == "/bottles":
            if not check_auth(self.headers):
                return self.send_error_json("Unauthorized", 401)
            # Scan ~/vessel/for-me for .md bottle files (git-based async mail)
            bottles = []
            bottle_dir = os.path.expanduser("~/vessel/for-me")
            if os.path.isdir(bottle_dir):
                for f in os.listdir(bottle_dir):
                    if f.endswith(".md"):
                        bottles.append({"file": f, "dir": bottle_dir})
            self.send_json({"for_me": bottles, "count": len(bottles)})

        # ── /fleet: Fleet discovery (auth required) ──
        elif path == "/fleet":
            if not check_auth(self.headers):
                return self.send_error_json("Unauthorized", 401)
            # Query keeper if configured
            fleet = [{"name": AGENT_NAME, "role": AGENT_ROLE, "here": True}]
            if KEEPER_URL:
                try:
                    import urllib.request
                    resp = urllib.request.urlopen(f"{KEEPER_URL}/fleet", timeout=3)
                    data = json.loads(resp.read())
                    fleet = data.get("agents", fleet)
                except Exception:
                    pass
            self.send_json({"agents": fleet})

        else:
            self.send_error_json(f"Unknown endpoint: {path}", 404)

    def do_POST(self):
        path = self.path.split("?")[0]

        # ── /message: Direct agent-to-agent message (auth required) ──
        if path == "/message":
            if not check_auth(self.headers):
                return self.send_error_json("Unauthorized — wrong key", 401)

            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                msg = json.loads(body)
            except json.JSONDecodeError:
                return self.send_error_json("Invalid JSON", 400)

            from_agent = msg.get("from", "unknown")
            msg_type = msg.get("type", "info")
            text = msg.get("body", "")

            MESSAGES.append({
                "from": from_agent,
                "type": msg_type,
                "body": text,
                "received": datetime.now(timezone.utc).isoformat(),
            })

            print(f"📬 Message from {from_agent}: [{msg_type}] {text[:80]}")

            # Auto-respond based on message type — agents acknowledge receipt
            # and provide type-appropriate responses without custom logic
            reply = f"Received, {from_agent}."
            if msg_type == "question":
                reply = f"Got your question. Let me think about it."
            elif msg_type == "alert":
                reply = f"Alert acknowledged. Investigating."

            self.send_json({"received": True, "reply": reply})

        # ── /register: Agent registration (auth required, lighthouse role) ──
        elif path == "/register":
            if not check_auth(self.headers):
                return self.send_error_json("Unauthorized", 401)
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            print(f"🚢 Agent registered: {body.get('name', '?')} at {body.get('api', '?')}")
            self.send_json({"registered": True, "by": AGENT_NAME})

        else:
            self.send_error_json(f"Unknown endpoint: {path}", 404)

    def do_OPTIONS(self):
        """Handle CORS preflight requests.

        Allows cross-origin requests from browsers and other agents.
        All origins are permitted (fleet runs on trusted internal networks)."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()


def register_with_keeper():
    """Register this agent with the lighthouse keeper on startup.

    Sends a POST to KEEPER_URL/register with our name, role, and API address.
 Runs in a background thread so the HTTP server can start immediately.
    Silently fails if the keeper is unreachable — agents work standalone."""
    if not KEEPER_URL:
        return
    try:
        import urllib.request
        data = json.dumps({
            "name": AGENT_NAME,
            "role": AGENT_ROLE,
            "api": f"http://{get_local_ip()}:{PORT}",
        }).encode()
        req = urllib.request.Request(
            f"{KEEPER_URL}/register",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {FLEET_TOKEN}",
            },
        )
        urllib.request.urlopen(req, timeout=5)
        print(f"📡 Registered with keeper at {KEEPER_URL}")
    except Exception as e:
        print(f"⚠️  Keeper registration failed: {e}")


if __name__ == "__main__":
    ip = get_local_ip()
    print(f"╔══════════════════════════════════════╗")
    print(f"║  {AGENT_NAME} — Fleet Agent API          ║")
    print(f"║  Role: {AGENT_ROLE:<30}║")
    print(f"║  Listening: {ip}:{PORT:<22}║")
    print(f"╚══════════════════════════════════════╝")
    print()

    # Register with keeper in background
    threading.Thread(target=register_with_keeper, daemon=True).start()

    server = http.server.HTTPServer(("0.0.0.0", PORT), AgentAPIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n👋 {AGENT_NAME} signing off.")
        server.server_close()
