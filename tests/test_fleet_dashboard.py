"""Tests for fleet_dashboard.py — dashboard fetch and repo utilities."""

import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fleet_dashboard


# ===================== fetch =====================

class TestFetch:
    @patch("fleet_dashboard.urllib.request.urlopen")
    def test_fetch_valid_url(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"key": "value"}).encode()
        mock_urlopen.return_value = mock_resp

        result = fleet_dashboard.fetch("http://example.com/data")
        assert result == {"key": "value"}

    @patch("fleet_dashboard.urllib.request.urlopen", side_effect=Exception("timeout"))
    def test_fetch_invalid_url_returns_none(self, mock_urlopen):
        result = fleet_dashboard.fetch("http://nonexistent.invalid/data")
        assert result is None

    @patch("fleet_dashboard.urllib.request.urlopen")
    def test_fetch_with_token(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"auth": "yes"}).encode()
        mock_urlopen.return_value = mock_resp

        result = fleet_dashboard.fetch("http://example.com/data", token="my-token")
        assert result["auth"] == "yes"
        # Verify the request was made with the token
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert "Bearer my-token" in req.headers.get("Authorization", "")

    @patch("fleet_dashboard.urllib.request.urlopen")
    def test_fetch_without_token(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"no_auth": True}).encode()
        mock_urlopen.return_value = mock_resp

        result = fleet_dashboard.fetch("http://example.com/public")
        assert result["no_auth"] is True

    @patch("fleet_dashboard.urllib.request.urlopen")
    def test_fetch_invalid_json_returns_none(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html>not json</html>"
        mock_urlopen.return_value = mock_resp

        result = fleet_dashboard.fetch("http://example.com/bad")
        assert result is None


# ===================== repo_count =====================

class TestRepoCount:
    @patch("fleet_dashboard.urllib.request.urlopen")
    def test_repo_count_from_last_page(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.headers = {"Link": '<https://api.github.com/user/repos?page=42>; rel="last"'}
        mock_resp.read.return_value = b"[]"
        mock_urlopen.return_value = mock_resp

        count = fleet_dashboard.repo_count()
        assert count == 42

    @patch("fleet_dashboard.urllib.request.urlopen")
    def test_repo_count_single_page(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.headers = {}  # no Link header
        mock_resp.read.return_value = json.dumps([{"name": "repo1"}, {"name": "repo2"}]).encode()
        mock_urlopen.return_value = mock_resp

        count = fleet_dashboard.repo_count()
        assert count == 2

    @patch("fleet_dashboard.urllib.request.urlopen", side_effect=Exception("denied"))
    def test_repo_count_error_returns_question_mark(self, mock_urlopen):
        count = fleet_dashboard.repo_count()
        assert count == "?"
