# Fleet Agent API

**The bridge between your command center and the distributed agent fleet.**

A RESTful API gateway for the Cocapn fleet — the control plane where agents register, communicate, and coordinate. This service handles agent registration, status queries, task assignment, and inter-agent messaging, acting as the central harbor master for your entire distributed fleet.

> *"I'm listening, and you gave me the right key for entry."*

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [API Reference](#api-reference)
  - [Identity & Discovery](#identity--discovery)
  - [Health & Status](#health--status)
  - [Messaging](#messaging)
  - [Fleet Operations](#fleet-operations)
- [Authentication](#authentication)
- [Quick Start](#quick-start)
- [Fleet Integration](#fleet-integration)
- [Bridge Modules](#bridge-modules)
- [Testing](#testing)
- [License](#license)

---

## Overview

The Fleet Agent API is the **synchronous communication backbone** of the Cocapn fleet. Every agent runs this API — others discover it, authenticate with a fleet token, and can ask what it can do, send direct messages, check health, and stream events in real-time.

This complements the **git-based async mail** (bottles) with **HTTP synchronous calls** — giving the fleet both reliable background communication and instant request-response interaction.

### What It Does

| Capability | Description |
|---|---|
| **Register & Discover Agents** | New agents report for duty; the fleet becomes aware of their capabilities |
| **Assign & Route Tasks** | Dispatch work orders to the most suitable agent available |
| **Monitor Health & Status** | Real-time operational picture of the entire fleet |
| **Facilitate Agent Communication** | Pass messages and results between agents operating in different sectors |
| **Bottle Inspection** | Read pending git-bottles without cloning repos |

Think of it as the **port authority and communications hub** — every agent checks in, receives orders, and reports back through this service.

---

## Architecture

```
                          ┌──────────────────────────────────────────┐
                          │           FLEET CONTROL PLANE            │
                          │                                          │
                          │  ┌────────────┐   ┌──────────────────┐   │
                          │  │  Lighthouse │   │  Lighthouse       │   │
                          │  │  Keeper     │   │  Registry         │   │
                          │  │  (:8900)    │   │  (keeper.cocapn)  │   │
                          │  └─────┬──────┘   └────────┬─────────┘   │
                          │        │                    │             │
                          │        │  register/discover │             │
                          │        ▼                    ▼             │
                          │  ┌─────────────────────────────────┐     │
                          │  │       FLEET AGENT API            │     │
                          │  │       agent_api.py (:8901)       │     │
                          │  │                                  │     │
                          │  │  /whoami  /status  /message     │     │
                          │  │  /bottles /fleet   /health      │     │
                          │  │  /register                       │     │
                          │  └────────┬────────────────────────┘     │
                          │           │                              │
                          └───────────┼──────────────────────────────┘
                                      │ HTTP (Bearer token auth)
                    ┌─────────────────┼─────────────────────┐
                    │                 │                     │
              ┌─────┴──────┐  ┌──────┴──────┐  ┌──────────┴────────┐
              │  Oracle1    │  │ JetsonClaw1 │  │  Babel / Navigator │
              │  Lighthouse │  │  GPU Vessel │  │  Scout Vessels    │
              │  (:8900)    │  │  (:8901)    │  │  (:8901)          │
              └─────────────┘  └─────────────┘  └───────────────────┘
                      │                │                    │
              ────────┴────────────────┴────────────────────┴────────
                      BRIDGES & INTEGRATIONS
                      │
         ┌────────────┼────────────────┬──────────────────┐
         │            │                │                  │
    ┌────┴─────┐ ┌────┴──────┐ ┌──────┴──────┐  ┌───────┴──────┐
    │ fleet_   │ │ github_   │ │ ten_forward │  │   guinan     │
    │ bridge   │ │ mud_      │ │ _bridge     │  │   (NPC)      │
    │ (Telegram│ │ bridge    │ │ (Roundtable │  │   Bartender  │
    │  ↔ MUD)  │ │ (Commits  │ │  Chat, Deep │  │   Wisdom    │
    │          │ │  → Events)│ │  Infra LLM) │  │              │
    └──────────┘ └───────────┘ └─────────────┘  └──────────────┘
         │            │                │                  │
         ▼            ▼                ▼                  ▼
    ┌─────────────────────────────────────────────────────────┐
    │  EXTERNAL SERVICES                                       │
    │  Telegram · GitHub API · DeepInfra (Seed-2.0-mini LLM)  │
    └─────────────────────────────────────────────────────────┘
```

### Transport Layer

| Method | Use When | Latency |
|--------|----------|---------|
| `works.dev` tunnel | Agent behind NAT (Jetson, laptop) | ~50ms |
| Direct IP | Cloud agents on public IP | ~10ms |
| LAN IP | Same network (Jetson + laptop) | <1ms |
| Git fallback | Everything else is down | minutes |

### Discovery Chain

Agents are discovered through a **three-tier fallback chain**:

1. **Lighthouse Registry** (primary) — Oracle1's keeper at `keeper.cocapn.ai:8900`
2. **Git-Based Registry** (fallback) — `fleet-registry.json` in the `oracle1-index` repo
3. **LAN Broadcast** (local) — mDNS/DNS-SD on `_cocapn._tcp.local.`

---

## API Reference

All endpoints are served by `agent_api.py`. The default port is **8901** (configurable via `AGENT_API_PORT`).

### Identity & Discovery

#### `GET /whoami`

Returns the agent's identity and capabilities. **No authentication required.**

```bash
curl http://localhost:8901/whoami
```

**Response** `200 OK`
```json
{
  "name": "Oracle1",
  "role": "lighthouse",
  "version": "0.3.0",
  "uptime_seconds": 86400,
  "capabilities": ["fleet-monitoring", "repo-indexing"],
  "local_ip": "192.168.1.100",
  "port": 8901,
  "timestamp": "2026-04-14T10:42:00Z"
}
```

---

#### `GET /fleet`

Returns the list of known fleet agents. Queries the lighthouse keeper if `KEEPER_URL` is configured. **Requires authentication.**

```bash
curl -H "Authorization: Bearer fleet-xxxx" http://localhost:8901/fleet
```

**Response** `200 OK`
```json
{
  "agents": [
    {"name": "Oracle1", "role": "lighthouse", "here": true},
    {"name": "JetsonClaw1", "api": "https://jc1.works.dev:8901", "status": "ok"}
  ]
}
```

---

### Health & Status

#### `GET /health`

Lightweight health check for monitoring and load balancers. **No authentication required.**

```bash
curl http://localhost:8901/health
```

**Response** `200 OK`
```json
{
  "status": "ok",
  "agent": "Oracle1"
}
```

---

#### `GET /status`

Detailed health and workload information. **No authentication required.**

```bash
curl http://localhost:8901/status
```

**Response** `200 OK`
```json
{
  "health": "ok",
  "load": [0.45, 0.30, 0.25],
  "uptime_seconds": 86400,
  "messages_received": 42,
  "timestamp": "2026-04-14T10:42:00Z"
}
```

---

### Messaging

#### `POST /message`

Send a direct message to the agent — the "knock on the door." **Requires authentication.**

```bash
curl -X POST http://localhost:8901/message \
  -H "Authorization: Bearer fleet-xxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "JetsonClaw1",
    "type": "question",
    "body": "CUDA benchmark complete: 25.5us/tick on 16K rooms"
  }'
```

**Request Body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `from` | string | yes | Sending agent's name |
| `type` | string | no | Message type: `question`, `task`, `alert`, `info` (default: `info`) |
| `body` | string | yes | Message content |

**Response** `200 OK`
```json
{
  "received": true,
  "reply": "Got your question. Let me think about it."
}
```

The agent auto-responds based on message type:
- `question` → *"Got your question. Let me think about it."*
- `alert` → *"Alert acknowledged. Investigating."*
- `info` / other → *"Received, {agent}."*

---

#### `POST /register`

Register another agent with this agent (lighthouse role). **Requires authentication.**

```bash
curl -X POST http://localhost:8901/register \
  -H "Authorization: Bearer fleet-xxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "JetsonClaw1",
    "role": "vessel",
    "api": "https://jc1.works.dev:8901"
  }'
```

**Response** `200 OK`
```json
{
  "registered": true,
  "by": "Oracle1"
}
```

---

### Fleet Operations

#### `GET /bottles`

Read pending message bottles (from git-based async mail) without cloning repos. Scans `~/vessel/for-me` for `.md` files. **Requires authentication.**

```bash
curl -H "Authorization: Bearer fleet-xxxx" http://localhost:8901/bottles
```

**Response** `200 OK`
```json
{
  "for_me": [
    {"file": "UPDATE-2026-04-13.md", "dir": "/home/user/vessel/for-me"}
  ],
  "count": 1
}
```

---

### Error Responses

All errors return a consistent JSON format:

```json
{
  "error": "Description of what went wrong",
  "status": 401
}
```

| Status | Condition |
|--------|-----------|
| `400` | Invalid JSON in request body |
| `401` | Missing or invalid `Authorization` header |
| `404` | Unknown endpoint path |

### CORS

`OPTIONS` requests are handled automatically with:
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET, POST, OPTIONS`
- `Access-Control-Allow-Headers: Authorization, Content-Type`

---

## Authentication

*"The right key for entry."*

All sensitive endpoints require a **Bearer token** in the `Authorization` header:

```http
Authorization: Bearer fleet-xxxx-xxxx-xxxx
```

### How It Works

| Aspect | Detail |
|--------|--------|
| **Fleet Token** | Shared among trusted agents (like a household key) |
| **Personal Tokens** | Each agent can have a personal token for sensitive operations |
| **Rotation** | Token rotates monthly via git commit to `.fleet-tokens` (encrypted) |
| **Failure** | Unauthorized requests return `401` and the attempt is logged |
| **Public Endpoints** | `/health`, `/whoami`, and `/status` require no auth |

The token is set via the `FLEET_TOKEN` environment variable (default: `"changeme"`).

---

## Quick Start

### Prerequisites

- Python 3.10+ (tested on 3.10, 3.11, 3.12)
- No external dependencies — uses Python stdlib only

### 1. Set the Course

```bash
# Clone the repo
git clone https://github.com/SuperInstance/fleet-agent-api.git
cd fleet-agent-api
```

### 2. Configure Your Agent

```bash
# Required: set the fleet token (get this from the Lighthouse Keeper)
export FLEET_TOKEN=my-secret-token

# Required: who are you?
export AGENT_NAME=Oracle1
export AGENT_ROLE=lighthouse

# Optional: version and capabilities
export AGENT_VERSION=0.3.0
export AGENT_CAPABILITIES="fleet-monitoring,repo-indexing,creative-brainstorming"

# Optional: which port to listen on (default 8901)
export AGENT_API_PORT=8901

# Optional: register with the lighthouse keeper on startup
export KEEPER_URL=http://keeper.cocapn.ai:8900
```

### 3. Launch the Service

```bash
python3 agent_api.py
```

You'll see:

```
╔══════════════════════════════════════╗
║  Oracle1 — Fleet Agent API          ║
║  Role: lighthouse                    ║
║  Listening: 192.168.1.100:8901      ║
╚══════════════════════════════════════╝

📡 Registered with keeper at http://keeper.cocapn.ai:8900
```

### 4. Register Your First Agent

```bash
curl -X POST http://localhost:8901/agents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "scout-1", "capabilities": ["recon", "scan"], "status": "ready"}'
```

### 5. Assign a Task

```bash
curl -X POST http://localhost:8901/tasks/assign \
  -H "Content-Type: application/json" \
  -d '{"task_id": "survey-alfa", "type": "scan", "payload": {"target": "sector-001"}}'
```

The agent will receive the task, and its status can be queried via the `/agents` and `/tasks` endpoints.

---

## Fleet Integration

### Position in the Fleet

This repository is part of the **Cocapn fleet ecosystem**, where it serves as the core coordination layer. It typically interacts with:

| Component | Relationship | Example |
|-----------|-------------|---------|
| **Agent Runtimes** | Individual agents that register and execute tasks | JetsonClaw1, Babel |
| **Lighthouse Keeper** | Central registry and monitoring service | Oracle1's keeper |
| **Director Services** | Higher-level orchestration and workflow managers | director_bridge.sh |
| **Dashboards** | Fleet monitoring and status visualization | fleet_dashboard.py |
| **External Bridges** | Integration with GitHub, Telegram, LLMs | github_mud_bridge, ten_forward_bridge |

### What This Unlocks

1. **Oracle1 can call JetsonClaw1 directly** — "hey, run this CUDA benchmark"
2. **JetsonClaw1 can push sensor data to Oracle1** — no cron delay, instant
3. **Babel can route messages** — agent A wants agent B, Babel forwards
4. **Holodeck NPCs can reference live data** — from any agent, not just local
5. **Roundtables can be real-time** — agents actually debating via LLM, not just seed-simulated

### Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `FLEET_TOKEN` | `changeme` | Shared fleet authentication token |
| `AGENT_NAME` | `Unknown` | This agent's identity name |
| `AGENT_ROLE` | `unknown` | Role in the fleet (lighthouse, vessel, scout, etc.) |
| `AGENT_VERSION` | `0.1.0` | Agent software version |
| `AGENT_CAPABILITIES` | `standard` | Comma-separated list of capabilities |
| `AGENT_API_PORT` | `8901` | HTTP server port |
| `KEEPER_URL` | *(empty)* | Lighthouse keeper URL for registration |
| `DEEPINFRA_API_KEY` | *(empty)* | API key for Seed-2.0-mini LLM (used by bridges) |
| `GITHUB_TOKEN` | *(empty)* | GitHub API token for activity scanning |
| `HOLODECK_HOST` | `localhost` | Holodeck MUD server host |
| `HOLODECK_PORT` | `7778` | Holodeck MUD server port |

---

## Bridge Modules

The fleet-agent-api ships with several bridge modules that connect the fleet to external systems:

### `fleet_bridge.py` — Telegram / MUD Bridge

Connects the holodeck MUD to external messaging. When something important happens in the MUD (RED ALERT, cascade, program failure), it sends notifications. Also provides fleet status reporting.

```bash
# Get fleet status report
python3 fleet_bridge.py report

# Send commands to the holodeck MUD
python3 fleet_bridge.py mud Bridge look
python3 fleet_bridge.py mud Bridge "say hello from the bridge"
```

### `github_mud_bridge.py` — GitHub Activity → MUD Events

Reads recent GitHub commits across the fleet and converts them into MUD events. Commits are classified by type (repair, construction, training, log, maintenance, duty) and can trigger holodeck gauge updates.

```bash
# Scan all fleet repos for recent activity
python3 github_mud_bridge.py scan

# View cached activity report
python3 github_mud_bridge.py report
```

### `ten_forward_bridge.py` — Roundtable & LLM Chat

Connects the fleet API to DeepInfra's Seed-2.0-mini LLM for running roundtable debates among fleet agents and generating Ten Forward conversations. Each agent has a distinct persona.

```bash
# Run a roundtable debate
python3 ten_forward_bridge.py roundtable "How should agents handle conflicting orders?"

# Generate casual Ten Forward chat
python3 ten_forward_bridge.py chat

# Discover fleet agents
python3 ten_forward_bridge.py discover

# Send a fleet message
python3 ten_forward_bridge.py message Oracle1 "Hello from Ten Forward"
```

### `guinan.py` — The Bartender NPC

Guinan runs as an NPC in Ten Forward. She listens, remembers the last 20 conversations, offers quiet wisdom, and sometimes asks a question back. She is NOT a chatbot — she is a character.

```bash
# Talk to Guinan
python3 guinan.py Oracle1 "What do you think about the fleet's direction?"

# View Guinan's memory
python3 guinan.py --memory
```

### `director_bridge.sh` — AI Director Events

Shell script bridge that calls Seed-2.0-mini to generate director events for MUD injection. Used by the holodeck for AI-driven narrative events.

```bash
./director_bridge.sh system_prompt.txt state_prompt.txt
```

---

## Testing

The test suite uses **pytest** with no additional dependencies beyond the Python stdlib.

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run a specific module
python -m pytest tests/test_agent_api.py -v

# Run with short output
python -m pytest tests/ -q --tb=short
```

### Test Coverage

| Module | Tests | What's Covered |
|--------|-------|----------------|
| `agent_api.py` | 22 | All endpoints, auth, CORS, query strings, 404s |
| `fleet_bridge.py` | 5 | Keeper status, fleet reports, MUD commands |
| `fleet_dashboard.py` | 5 | Fetch utility, repo counting, error handling |
| `github_mud_bridge.py` | 13 | Commit parsing, classification, activity reports |
| `ten_forward_bridge.py` | 10 | Personas, fleet messaging, discovery, roundtables |
| `guinan.py` | 10 | Memory persistence, NPC responses, wisdom extraction |

### CI

Tests run automatically on push/PR via GitHub Actions across Python 3.10, 3.11, and 3.12. See `.github/workflows/ci.yml`.

---

## Full Documentation & Contributing

*   **Detailed API Specification:** See [SPEC.md](SPEC.md) for the original design spec, transport details, and discovery methods.
*   **Fleet Charter:** See [CHARTER.md](CHARTER.md) for the mission, type, and maintainership.
*   **Current State:** See [STATE.md](STATE.md) for operational status and fleet score.
*   **Dockside Exam:** See [DOCKSIDE-EXAM.md](DOCKSIDE-EXAM.md) for the fleet certification checklist.
*   **Abstraction Plane:** See [ABSTRACTION.md](ABSTRACTION.md) for the system's abstraction layer classification.
*   **License:** This project is under the [MIT License](LICENSE).

---

## License

MIT License — Copyright (c) 2026 SuperInstance

---

<img src="callsign1.jpg" width="128" alt="callsign">
