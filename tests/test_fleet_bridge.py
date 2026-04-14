"""Tests for fleet_bridge.py — Telegram/MUD bridge utilities."""

import json
import os
import sys
import socket
from unittest.mock import patch, MagicMock

import pytest

# Ensure the repo root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fleet_bridge


# ===================== keeper_status =====================

class TestKeeperStatus:
    def test_returns_unreachable_when_connection_fails(self):
        result = fleet_bridge.keeper_status()
        assert result == {"status": "unreachable"}

    @patch("fleet_bridge.urllib.request.urlopen")
    def test_returns_parsed_json_on_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"status": "ok", "version": "0.3.0", "agents": 5, "api_calls": 1234}
        ).encode()
        mock_urlopen.return_value = mock_resp

        result = fleet_bridge.keeper_status()
        assert result["status"] == "ok"
        assert result["version"] == "0.3.0"
        assert result["agents"] == 5

    @patch("fleet_bridge.urllib.request.urlopen", side_effect=Exception("timeout"))
    def test_handles_timeout_gracefully(self, mock_urlopen):
        result = fleet_bridge.keeper_status()
        assert result["status"] == "unreachable"


# ===================== fleet_report =====================

class TestFleetReport:
    def test_unreachable_returns_warning(self):
        report = fleet_bridge.fleet_report()
        assert "unreachable" in report.lower() or "⚠" in report

    @patch("fleet_bridge.keeper_status", return_value={
        "status": "ok", "version": "0.5.0", "agents": 12, "api_calls": 9999
    })
    def test_reachable_returns_formatted_report(self, mock_status):
        report = fleet_bridge.fleet_report()
        assert "Lighthouse" in report
        assert "0.5.0" in report
        assert "12" in report
        assert "9999" in report


# ===================== mud_command =====================

class TestMudCommand:
    def test_connection_error_returns_message(self):
        result = fleet_bridge.mud_command("TestBot", "look")
        assert "connection error" in result.lower() or "error" in result.lower()

    @patch("socket.socket")
    def test_successful_command_flow(self, mock_socket_cls):
        # Simulate a MUD connection: welcome → name prompt → room → command → quit
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        responses = [
            b"Welcome to the Holodeck!\nEnter your vessel name: ",
            b"You are in Ten Forward.\n> ",
            b"You look around. It's a lounge.\n> ",
        ]
        mock_sock.recv.side_effect = iter(responses)

        result = fleet_bridge.mud_command("TestBot", "look")
        assert "Ten Forward" in result or "look" in result.lower()
        mock_sock.sendall.assert_called()
        mock_sock.close.assert_called_once()
