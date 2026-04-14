# Fleet Agent API

**The bridge between your command center and the distributed agent fleet.**

A RESTful API gateway for FLUX fleet agent management. This service handles agent registration, status queries, task assignment, and inter-agent communication, acting as the central harbor master for your entire distributed fleet.

## What It Does

The Fleet Agent API is the control plane for your FLUX agents. It provides the essential endpoints to:
*   **Register & Discover Agents:** New agents report for duty and the fleet becomes aware of their capabilities.
*   **Assign & Route Tasks:** Dispatch work orders to the most suitable agent available.
*   **Monitor Health & Status:** Get a real-time operational picture of your entire fleet.
*   **Facilitate Agent Communication:** Pass messages and results between agents operating in different sectors.

Think of it as the port authority and communications hub—every agent checks in, receives orders, and reports back through this service.

## Position in the Fleet

This repository is part of the **Cocapn fleet ecosystem**, where it serves as a core coordination layer. It typically interacts with:
*   **Agent Runtimes:** Individual agents that register and execute tasks.
*   **Director Services:** Higher-level orchestration and workflow managers.
*   **Dashboards & Bridges:** For monitoring (like `fleet_dashboard`) and integrating with external systems (like `github_mud_bridge`).

For a complete view of the fleet's structure and other vessels, refer to the [FLUX Fleet Charter](CHARTER.md).

## Quick Start

1.  **Set the Course:** Ensure Python 3.9+ is installed.
2.  **Launch the Service:**
    ```bash
    # Install dependencies
    pip install -r requirements.txt

    # Start the API gateway (default port 8080)
    python agent_api.py
    ```
3.  **Register Your First Agent:** (Example using `curl`)
    ```bash
    curl -X POST http://localhost:8080/agents/register \
      -H "Content-Type: application/json" \
      -d '{"agent_id": "scout-1", "capabilities": ["recon", "scan"], "status": "ready"}'
    ```
4.  **Assign a Task:**
    ```bash
    curl -X POST http://localhost:8080/tasks/assign \
      -H "Content-Type: application/json" \
      -d '{"task_id": "survey-alfa", "type": "scan", "payload": {"target": "sector-001"}}'
    ```

The agent will receive the task, and its status can be queried via the `/agents` and `/tasks` endpoints.

## Full Documentation & Contributing

*   **Detailed API Specification:** See [SPEC.md](SPEC.md) for all endpoints, request/response formats, and behaviors.
*   **Run the Tests:** Ensure everything is shipshape with `pytest` from the repo root.
*   **License:** This project is under the [MIT License](LICENSE).