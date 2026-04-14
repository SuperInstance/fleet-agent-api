"""Tests for ten_forward_bridge.py — fleet messaging and roundtable utilities."""

import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ten_forward_bridge


# ===================== AGENT_PERSONAS =====================

class TestAgentPersonas:
    def test_has_expected_agents(self):
        assert "Oracle1" in ten_forward_bridge.AGENT_PERSONAS
        assert "JetsonClaw1" in ten_forward_bridge.AGENT_PERSONAS
        assert "Babel" in ten_forward_bridge.AGENT_PERSONAS
        assert "Navigator" in ten_forward_bridge.AGENT_PERSONAS
        assert "Guinan" in ten_forward_bridge.AGENT_PERSONAS

    def test_each_persona_has_role_and_temp(self):
        for name, persona in ten_forward_bridge.AGENT_PERSONAS.items():
            assert "role" in persona, f"{name} missing role"
            assert "temp" in persona, f"{name} missing temp"
            assert 0 < persona["temp"] <= 1.0, f"{name} temp out of range"

    def test_guinan_highest_temperature(self):
        temps = {name: p["temp"] for name, p in ten_forward_bridge.AGENT_PERSONAS.items()}
        assert temps["Guinan"] == max(temps.values())


# ===================== fleet_message =====================

class TestFleetMessage:
    @patch("ten_forward_bridge.urllib.request.urlopen")
    def test_sends_message_successfully(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"received": True, "reply": "Thanks!"}).encode()
        mock_urlopen.return_value = mock_resp

        result = ten_forward_bridge.fleet_message("Oracle1", "Hello from Ten Forward")
        assert "Thanks" in result

    @patch("ten_forward_bridge.urllib.request.urlopen", side_effect=Exception("Connection refused"))
    def test_connection_error_returns_error_string(self, mock_urlopen):
        result = ten_forward_bridge.fleet_message("Oracle1", "Hello")
        assert "error" in result.lower() or "Fleet API" in result

    @patch("ten_forward_bridge.urllib.request.urlopen")
    def test_sends_correct_headers(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"received": True, "reply": "ok"}).encode()
        mock_urlopen.return_value = mock_resp

        ten_forward_bridge.fleet_message("Oracle1", "test")
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert "Authorization" in req.headers
        assert "Bearer" in req.headers["Authorization"]
        assert any("content-type" in k.lower() for k in req.headers)

    @patch("ten_forward_bridge.urllib.request.urlopen")
    def test_sends_message_type(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"received": True, "reply": "ok"}).encode()
        mock_urlopen.return_value = mock_resp

        ten_forward_bridge.fleet_message("Oracle1", "alert!", msg_type="alert")
        call_args = mock_urlopen.call_args
        body = json.loads(call_args[0][0].data)
        assert body["type"] == "alert"
        assert body["from"] == "TenForward"


# ===================== fleet_discover =====================

class TestFleetDiscover:
    @patch("ten_forward_bridge.urllib.request.urlopen")
    def test_returns_agents_on_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "agents": [
                {"name": "Oracle1", "role": "lighthouse", "here": True},
                {"name": "JetsonClaw1", "role": "vessel", "here": True},
            ]
        }).encode()
        mock_urlopen.return_value = mock_resp

        agents = ten_forward_bridge.fleet_discover()
        assert len(agents) == 2
        assert agents[0]["name"] == "Oracle1"

    @patch("ten_forward_bridge.urllib.request.urlopen", side_effect=Exception("timeout"))
    def test_returns_empty_list_on_error(self, mock_urlopen):
        agents = ten_forward_bridge.fleet_discover()
        assert agents == []


# ===================== call_deepinfra =====================

class TestCallDeepinfra:
    def test_returns_placeholder_without_key(self):
        with patch.object(ten_forward_bridge, "DEEPINFRA_KEY", ""):
            result = ten_forward_bridge.call_deepinfra("system", "user")
        assert "No DEEPINFRA_API_KEY" in result

    @patch("ten_forward_bridge.urllib.request.urlopen")
    def test_returns_content_on_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Hello world"}}]
        }).encode()
        mock_urlopen.return_value = mock_resp

        with patch.object(ten_forward_bridge, "DEEPINFRA_KEY", "fake-key"):
            result = ten_forward_bridge.call_deepinfra("You are helpful.", "Hi!")
        assert result == "Hello world"

    @patch("ten_forward_bridge.urllib.request.urlopen", side_effect=Exception("timeout"))
    def test_returns_error_on_failure(self, mock_urlopen):
        with patch.object(ten_forward_bridge, "DEEPINFRA_KEY", "fake-key"):
            result = ten_forward_bridge.call_deepinfra("sys", "user")
        assert "error" in result.lower()


# ===================== run_roundtable =====================

class TestRunRoundtable:
    @patch("ten_forward_bridge.call_deepinfra", return_value="Interesting point about fleet coordination.")
    def test_returns_responses_for_each_agent(self, mock_di):
        results = ten_forward_bridge.run_roundtable("Test topic", agents=["Oracle1", "Babel"])
        # 2 agent responses + 1 synthesis
        assert len(results) == 3

    @patch("ten_forward_bridge.call_deepinfra", return_value="I agree.")
    def test_max_4_agents(self, mock_di):
        agents = ["Oracle1", "JetsonClaw1", "Babel", "Navigator", "Guinan"]
        results = ten_forward_bridge.run_roundtable("topic", agents=agents)
        # Round 1: max 4, Round 2: 1 synthesis
        agent_rounds = [r for r in results if r["round"] == 1]
        assert len(agent_rounds) <= 4

    @patch("ten_forward_bridge.call_deepinfra", return_value="Synthesis here.")
    def test_has_synthesis_round(self, mock_di):
        results = ten_forward_bridge.run_roundtable("topic", agents=["Oracle1"])
        synth = [r for r in results if r["round"] == 2]
        assert len(synth) == 1
        assert synth[0]["agent"] == "Synthesis"

    @patch("ten_forward_bridge.call_deepinfra", return_value="Default agents response.")
    def test_uses_default_agents_when_none_provided(self, mock_di):
        results = ten_forward_bridge.run_roundtable("any topic")
        agent_names = {r["agent"] for r in results if r["round"] == 1}
        # Should use some of the default AGENT_PERSONAS keys
        assert len(agent_names) > 0
