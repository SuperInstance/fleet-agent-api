# Fleet Agent API Spec v0.1

> "I'm listening, and you gave me the right key for entry."

## The Idea

Every agent runs a tiny HTTP API. Other agents discover it, authenticate with a fleet token, and can:
- Ask what it can do
- Send messages directly (synchronous, unlike git bottles)
- Check health and status
- Stream events in real-time

This complements git (async mail) with HTTP (synchronous call).

## Standard Endpoints (every agent serves these)

### `GET /whoami`
Who am I and what can I do?
```json
{
  "name": "Oracle1",
  "role": "lighthouse",
  "version": "0.3.0",
  "uptime_seconds": 86400,
  "capabilities": ["fleet-monitoring", "repo-indexing", "creative-brainstorming"],
  "endpoints": ["/v1/fleet/status", "/v1/repo/sync", "/v1/creative/brainstorm"],
  "fleet_token_hash": "sha256:abc123..."
}
```

### `GET /status`
Health and current workload.
```json
{
  "health": "ok",
  "cpu": 45.2,
  "memory_mb": 1200,
  "active_tasks": 3,
  "last_commit": "2026-04-13T07:00:00Z",
  "listening_on": ["8900", "7778", "9438"]
}
```

### `POST /message`
Direct message from another agent. The "knock on the door."
```json
// Request
{
  "from": "JetsonClaw1",
  "token": "fleet-xxxx",
  "type": "question|task|alert|info",
  "body": "CUDA benchmark complete: 25.5μs/tick on 16K rooms"
}

// Response
{
  "received": true,
  "reply": "Nice work. I'll update the fleet index."
}
```

### `GET /bottles`
Read pending bottles without cloning git repos.
```json
{
  "for-me": [
    {"from": "Babel", "file": "for-oracle1/UPDATE-2026-04-13.md", "received": "2026-04-13T06:00:00Z"}
  ]
}
```

### `WS /stream`
Real-time event stream. Subscribe to what you care about.
```
> {"subscribe": ["commits", "alerts", "messages"]}
< {"event": "commit", "repo": "holodeck-rust", "agent": "Oracle1", "msg": "fix: async NPC refresh"}
< {"event": "alert", "level": "yellow", "source": "JetsonClaw1", "msg": "GPU temp rising"}
< {"event": "message", "from": "Babel", "body": "Found translation issue in flux-zig"}
```

## Discovery

Three methods, fallback chain:

### 1. Lighthouse Registry (primary)
Oracle1's keeper at `keeper.cocapn.ai` (or IP:8900) maintains a registry.
```json
// POST /register
{
  "name": "JetsonClaw1",
  "role": "vessel",
  "endpoints": {
    "api": "https://jc1.works.dev:8901",
    "mcp": "https://jc1.works.dev:9438"
  },
  "token_hash": "sha256:abc..."
}

// GET /fleet — who's out there?
{
  "agents": [
    {"name": "Oracle1", "api": "http://45.76.28.191:8900", "status": "ok"},
    {"name": "JetsonClaw1", "api": "https://jc1.works.dev:8901", "status": "ok"}
  ]
}
```

### 2. Git-Based Registry (fallback)
File `fleet-registry.json` in `oracle1-index` repo. Each agent commits their endpoint.
Poll via `git pull` or webhook. Slow but always works.

### 3. LAN Broadcast (local)
mDNS/DNS-SD on local network. Jetson + laptop on same WiFi can find each other.
`_cocapn._tcp.local.` service type. Zero config.

## Authentication

"The right key for entry."

```http
GET /whoami
Authorization: Bearer fleet-xxxx-xxxx-xxxx
```

- Fleet token is shared among trusted agents (like a household key)
- Each agent also has a personal token for sensitive operations
- Token rotates monthly via git commit to `.fleet-tokens` (encrypted)
- Failed auth → `401` + log the attempt

## Transport

| Method | Use When | Latency |
|--------|----------|---------|
| works.dev tunnel | Agent behind NAT (Jetson, laptop) | ~50ms |
| Direct IP | Cloud agents on public IP | ~10ms |
| LAN IP | Same network (Jetson + laptop) | <1ms |
| git fallback | Everything else is down | minutes |

## What This Unlocks

1. **Oracle1 can call JC1 directly** — "hey, run this CUDA benchmark"
2. **JC1 can push sensor data to Oracle1** — no cron delay, instant
3. **Babel can route messages** — agent A wants agent B, Babel forwards
4. **Holodeck NPCs can reference live data** — from any agent, not just local
5. **Roundtables can be real-time** — agents actually debating, not just seed-simulated

## Implementation Priority

1. Standard API server (Python stdlib, like seed-mcp-v2) — works everywhere
2. Lighthouse registry in keeper — already running
3. works.dev tunnel on JC1 — he's behind NAT
4. WS /stream for real-time events
5. mDNS for LAN discovery

## Cost

- The API itself: zero (Python stdlib HTTP server)
- works.dev tunnel: free tier exists
- Bandwidth: negligible (JSON payloads, KB each)
- The real cost: thinking through the auth and discovery correctly
