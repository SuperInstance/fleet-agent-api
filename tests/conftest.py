"""Pytest configuration for fleet-agent-api tests."""

import sys
import os

# Ensure the repo root is on sys.path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Suppress noisy HTTP request logs during tests
import logging
logging.getLogger("urllib3").setLevel(logging.WARNING)
