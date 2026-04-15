#!/usr/bin/env python3
"""Fleet Dashboard — shows everything at once

Queries keeper, agent API, holodeck, and GitHub to build a complete picture.
"""

import json
import os
import sys
import time
import urllib.request

# ── Configuration ─────────────────────────────────────────────────────────
# GitHub token is optional but needed for the repos section of the dashboard.
# FLEET_TOKEN must match the agent_api.py FLEET_TOKEN for authenticated queries.
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
KEEPER = "http://localhost:8900"      # lighthouse keeper health endpoint
AGENT_API = "http://localhost:8901"   # fleet agent API base URL
FLEET_TOKEN = "cocapn-fleet-2026"     # fleet auth token for API queries


def fetch(url, token=None):
    """Fetch JSON from a URL with optional Bearer token authentication.

    Returns parsed JSON dict on success, None on any failure.
    Used throughout the dashboard to query fleet services."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=3)
        return json.loads(resp.read())
    except Exception:
        return None


def repo_count():
    """Count total GitHub repos for the authenticated user.

    Uses the Link header's 'last' page reference for efficiency
    instead of fetching all repos. Falls back to counting the
    returned array if no pagination headers are present."""
    try:
        req = urllib.request.Request(
            "https://api.github.com/user/repos?per_page=1",
            headers={"Authorization": f"token {GITHUB_TOKEN}"},
        )
        resp = urllib.request.urlopen(req, timeout=5)
        link = resp.headers.get("Link", "")
        if 'rel="last"' in link:
            last_page = link.split('page=')[-1].split('>')[0]
            return int(last_page)
        return len(json.loads(resp.read()))
    except Exception:
        return "?"


def dashboard():
    """Print the complete fleet dashboard to stdout.

    Queries four data sources:
      1. Local service health checks (ports 8900, 8901, 7778, 9438)
      2. Lighthouse keeper status
      3. Fleet agent list via the agent API
      4. GitHub repo count and recently active repos
    """
    print("╔══════════════════════════════════════════════════╗")
    print("║        🔮 ORACLE1 FLEET DASHBOARD               ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"  {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    print()

    # Services
    print("📡 SERVICES")
    for name, port in [("Lighthouse Keeper", 8900), ("Agent API", 8901), ("Holodeck MUD", 7778), ("Seed-MCP", 9438)]:
        try:
            s = urllib.request.urlopen(f"http://localhost:{port}/health", timeout=2)
            status = "✅"
        except:
            try:
                import socket
                s = socket.socket()
                s.settimeout(1)
                s.connect(("localhost", port))
                s.close()
                status = "✅"
            except:
                status = "❌"
        print(f"  {status} {name} (:{port})")
    print()

    # Keeper
    keeper = fetch(f"{KEEPER}/health")
    if keeper:
        print(f"🏠 KEEPER: v{keeper.get('version', '?')} | {keeper.get('agents', 0)} vessels | {keeper.get('api_calls', 0):,} API calls")
    print()

    # Agent API
    fleet = fetch(f"{AGENT_API}/fleet", FLEET_TOKEN)
    if fleet and "agents" in fleet:
        agents = fleet["agents"]
        print(f"🤖 AGENTS ({len(agents)} online)")
        for a in agents:
            here = "🟢" if a.get("here") else "🔴"
            print(f"  {here} {a['name']} ({a.get('role', '?')})")
    print()

    # GitHub
    count = repo_count()
    print(f"📦 GITHUB: SuperInstance/{count} repos")
    print()

    # Recent repos (last 5 pushed)
    try:
        req = urllib.request.Request(
            "https://api.github.com/user/repos?per_page=5&sort=pushed",
            headers={"Authorization": f"token {GITHUB_TOKEN}"},
        )
        resp = urllib.request.urlopen(req, timeout=5)
        repos = json.loads(resp.read())
        print("📚 RECENTLY ACTIVE")
        for r in repos:
            lang = r.get("language") or "-"
            desc = (r.get("description") or "")[:50]
            updated = r.get("pushed_at", "")[:16]
            print(f"  {updated} {r['name']} ({lang}) — {desc}")
    except Exception:
        pass
    print()

    print("─" * 50)
    print(f"Generated: {time.strftime('%H:%M:%S UTC')}")


if __name__ == "__main__":
    dashboard()
