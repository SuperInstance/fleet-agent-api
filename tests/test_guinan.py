"""Tests for guinan.py — NPC bartender memory and response logic."""

import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import guinan


# ===================== Fixtures =====================

@pytest.fixture
def memory_file(tmp_path):
    """Provide a temp file and monkey-patch MEMORY_FILE."""
    p = tmp_path / "guinan_memory.json"
    with patch.object(guinan, "MEMORY_FILE", str(p)):
        yield p


# ===================== load_memory / save_memory =====================

class TestMemoryPersistence:
    def test_load_default_when_missing(self, memory_file):
        mem = guinan.load_memory()
        assert mem == {"conversations": [], "wisdom": []}

    def test_save_and_load_round_trip(self, memory_file):
        data = {"conversations": [{"agent": "A", "said": "hello"}], "wisdom": ["be nice"]}
        guinan.save_memory(data)
        loaded = guinan.load_memory()
        assert loaded == data

    def test_save_creates_file(self, memory_file):
        assert not memory_file.exists()
        guinan.save_memory({"conversations": [], "wisdom": []})
        assert memory_file.exists()

    def test_save_writes_valid_json(self, memory_file):
        guinan.save_memory({"conversations": [], "wisdom": []})
        with open(memory_file) as f:
            data = json.load(f)
        assert "conversations" in data


# ===================== guinan_respond =====================

class TestGuinanRespond:
    def test_fallback_response_without_api_key(self, memory_file):
        # Ensure no API key
        with patch.object(guinan, "DEEPINFRA_KEY", ""):
            response = guinan.guinan_respond("Oracle1", "How are you?", {"conversations": [], "wisdom": []})
        assert isinstance(response, str)
        assert len(response) > 0

    def test_fallback_responses_are_known_strings(self, memory_file):
        with patch.object(guinan, "DEEPINFRA_KEY", ""):
            responses = set()
            for _ in range(50):
                r = guinan.guinan_respond("Bot", "test", {"conversations": [], "wisdom": []})
                responses.add(r)
        # Should have picked from the fallback list
        assert len(responses) > 0
        assert len(responses) <= 8  # 8 fallback strings

    def test_respond_with_context_from_memory(self, memory_file):
        memory = {
            "conversations": [
                {"agent": "Babel", "said": "I found a pattern", "response": "Interesting. Tell me more."},
            ],
            "wisdom": [],
        }
        with patch.object(guinan, "DEEPINFRA_KEY", ""):
            response = guinan.guinan_respond("Navigator", "What pattern?", memory)
        assert isinstance(response, str)

    @patch("guinan.urllib.request.urlopen")
    def test_api_response_on_success(self, mock_urlopen, memory_file):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "The stars hold many secrets."}}]
        }).encode()
        mock_urlopen.return_value = mock_resp

        with patch.object(guinan, "DEEPINFRA_KEY", "fake-key"):
            response = guinan.guinan_respond("Oracle1", "Tell me about the universe", {"conversations": [], "wisdom": []})
        assert response == "The stars hold many secrets."

    @patch("guinan.urllib.request.urlopen", side_effect=Exception("API down"))
    def test_api_error_returns_fallback_knowingly(self, mock_urlopen, memory_file):
        with patch.object(guinan, "DEEPINFRA_KEY", "fake-key"):
            response = guinan.guinan_respond("JetsonClaw1", "hello", {"conversations": [], "wisdom": []})
        assert "knowingly" in response


# ===================== interact =====================

class TestInteract:
    def test_interact_saves_conversation(self, memory_file):
        with patch.object(guinan, "DEEPINFRA_KEY", ""):
            guinan.interact("Oracle1", "Hello Guinan")
        mem = guinan.load_memory()
        assert len(mem["conversations"]) == 1
        assert mem["conversations"][0]["agent"] == "Oracle1"
        assert mem["conversations"][0]["said"] == "Hello Guinan"

    def test_interact_returns_string(self, memory_file):
        with patch.object(guinan, "DEEPINFRA_KEY", ""):
            result = guinan.interact("Babel", "What do you think?")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_memory_trims_to_20_conversations(self, memory_file):
        with patch.object(guinan, "DEEPINFRA_KEY", ""):
            for i in range(25):
                guinan.interact("Bot", f"Message {i}")
        mem = guinan.load_memory()
        assert len(mem["conversations"]) == 20
        # Most recent should be last
        assert mem["conversations"][-1]["said"] == "Message 24"

    def test_wisdom_extracted_for_long_responses_with_question(self, memory_file):
        long_wise_response = "Have you ever noticed that the quietest rooms teach you the most about yourself?"
        with patch.object(guinan, "guinan_respond", return_value=long_wise_response):
            guinan.interact("Navigator", "Tell me wisdom")
        mem = guinan.load_memory()
        assert len(mem["wisdom"]) >= 1
        assert long_wise_response in mem["wisdom"]

    def test_wisdom_not_extracted_for_short_responses(self, memory_file):
        short_response = "Hmm."
        with patch.object(guinan, "guinan_respond", return_value=short_response):
            guinan.interact("Bot", "hi")
        mem = guinan.load_memory()
        # short response (< 40 chars) should not be wisdom
        assert all(len(w) > 40 for w in mem["wisdom"])

    def test_wisdom_not_extracted_without_question_mark(self, memory_file):
        no_question = "The stars are beautiful tonight and they shine bright over the ocean"
        with patch.object(guinan, "guinan_respond", return_value=no_question):
            guinan.interact("Bot", "Tell me something")
        mem = guinan.load_memory()
        assert len(mem["wisdom"]) == 0

    def test_wisdom_trims_to_10(self, memory_file):
        wise = "Have you ever considered that the answer you seek is the one you already know? {}"
        with patch.object(guinan, "guinan_respond", return_value=wise.format("?")):
            for i in range(15):
                guinan.interact("Bot", f"Ask {i}")
        mem = guinan.load_memory()
        assert len(mem["wisdom"]) == 10
