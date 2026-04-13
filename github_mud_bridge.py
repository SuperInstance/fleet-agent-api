#!/usr/bin/env python3
"""GitHub-to-MUD Bridge — fleet commits become MUD events

Reads recent GitHub commits across the fleet and generates:
- MUD notifications when repos get updated
- Gauge updates for activity levels
- NPC dialogue updates referencing real work

This is the actualization loop: commit → detect → notify → gauge → evolve
"""

import json
import os
import sys
import time
import urllib.request

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"
KEEPER_URL = os.environ.get("KEEPER_URL", "http://localhost:8900")

# Fleet repos we care about
FLEET_REPOS = [
    "holodeck-rust", "holodeck-c", "holodeck-cuda", "holodeck-studio",
    "fleet-agent-api", "lighthouse-keeper", "flux-runtime",
    "seed-mcp-v2", "oracle1-workspace",
    "holodeck-go", "holodeck-zig", "fleet-liaison-tender",
    "flux-lcar-esp32", "flux-lcar-cartridge", "flux-lcar-scheduler",
]


def get_recent_commits(repo: str, since: str = None, per_page: int = 5) -> list:
    """Get recent commits from a SuperInstance repo."""
    url = f"{GITHUB_API}/repos/SuperInstance/{repo}/commits?per_page={per_page}"
    if since:
        url += f"&since={since}"
    
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    })
    
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        commits = json.loads(resp.read())
        results = []
        for c in commits:
            results.append({
                "repo": repo,
                "sha": c["sha"][:7],
                "message": c["commit"]["message"].split("\n")[0][:80],
                "author": c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
            })
        return results
    except Exception as e:
        return []


def get_fleet_activity() -> dict:
    """Scan fleet repos for recent activity."""
    all_commits = {}
    
    for repo in FLEET_REPOS:
        commits = get_recent_commits(repo, per_page=3)
        if commits:
            all_commits[repo] = commits
        time.sleep(0.2)  # Rate limit
    
    return all_commits


def activity_to_mud_events(activity: dict) -> list:
    """Convert GitHub activity to MUD events."""
    events = []
    
    for repo, commits in activity.items():
        for commit in commits:
            msg = commit["message"].lower()
            
            # Classify the commit
            if any(w in msg for w in ["fix", "bug", "patch", "hotfix"]):
                event_type = "repair"
            elif any(w in msg for w in ["feat", "add", "new", "build"]):
                event_type = "construction"
            elif any(w in msg for w in ["test", "spec", "verify"]):
                event_type = "training"
            elif any(w in msg for w in ["doc", "readme", "comment"]):
                event_type = "log"
            elif any(w in msg for w in ["refactor", "clean", "reorg"]):
                event_type = "maintenance"
            else:
                event_type = "duty"
            
            events.append({
                "type": event_type,
                "repo": repo,
                "sha": commit["sha"],
                "message": commit["message"],
                "time": commit["date"],
            })
    
    # Sort by time (newest first)
    events.sort(key=lambda e: e["time"], reverse=True)
    return events


def generate_activity_report(events: list) -> str:
    """Generate a formatted activity report."""
    if not events:
        return "No recent fleet activity detected."
    
    lines = ["📋 FLEET ACTIVITY REPORT", "=" * 40]
    
    # Count by type
    type_counts = {}
    for e in events:
        t = e["type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    
    lines.append(f"Total commits: {len(events)}")
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        emoji = {
            "repair": "🔧", "construction": "🏗️", "training": "🎯",
            "log": "📝", "maintenance": "🔧", "duty": "⚙️"
        }.get(t, "•")
        lines.append(f"  {emoji} {t}: {count}")
    
    lines.append("")
    lines.append("Recent:")
    for e in events[:10]:
        emoji = {
            "repair": "🔧", "construction": "🏗️", "training": "🎯",
            "log": "📝", "maintenance": "🔧", "duty": "⚙️"
        }.get(e["type"], "•")
        lines.append(f"  {emoji} {e['repo']} ({e['sha']}): {e['message'][:60]}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: github_mud_bridge.py [scan|report]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "scan":
        activity = get_fleet_activity()
        events = activity_to_mud_events(activity)
        print(generate_activity_report(events))
        
        # Save for later
        with open("/tmp/fleet_activity.json", "w") as f:
            json.dump(events[:50], f, indent=2)
    
    elif cmd == "report":
        try:
            with open("/tmp/fleet_activity.json") as f:
                events = json.load(f)
            print(generate_activity_report(events))
        except FileNotFoundError:
            print("No cached activity. Run 'scan' first.")
    
    else:
        print(f"Unknown: {cmd}")
