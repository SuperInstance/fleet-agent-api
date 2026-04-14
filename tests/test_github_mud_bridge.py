"""Tests for github_mud_bridge.py — commit classification and activity reports."""

import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import github_mud_bridge


# ===================== get_recent_commits =====================

class TestGetRecentCommits:
    @patch("github_mud_bridge.urllib.request.urlopen")
    def test_parses_commits_correctly(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps([
            {
                "sha": "abcdef1234567890",
                "commit": {
                    "message": "feat: add new warp drive",
                    "author": {"name": "Oracle1", "date": "2026-04-13T10:00:00Z"},
                },
            },
            {
                "sha": "1234567890abcdef",
                "commit": {
                    "message": "fix: repair deflector shield",
                    "author": {"name": "JetsonClaw1", "date": "2026-04-13T09:00:00Z"},
                },
            },
        ]).encode()
        mock_urlopen.return_value = mock_resp

        commits = github_mud_bridge.get_recent_commits("holodeck-rust")
        assert len(commits) == 2
        assert commits[0]["sha"] == "abcdef1"
        assert commits[0]["repo"] == "holodeck-rust"
        assert commits[0]["author"] == "Oracle1"
        assert commits[1]["sha"] == "1234567"

    @patch("github_mud_bridge.urllib.request.urlopen", side_effect=Exception("rate limited"))
    def test_returns_empty_list_on_error(self, mock_urlopen):
        commits = github_mud_bridge.get_recent_commits("nonexistent")
        assert commits == []

    @patch("github_mud_bridge.urllib.request.urlopen")
    def test_truncates_long_messages(self, mock_urlopen):
        mock_resp = MagicMock()
        long_msg = "x" * 200
        mock_resp.read.return_value = json.dumps([
            {
                "sha": "a" * 40,
                "commit": {
                    "message": long_msg,
                    "author": {"name": "Bot", "date": "2026-04-13T00:00:00Z"},
                },
            }
        ]).encode()
        mock_urlopen.return_value = mock_resp

        commits = github_mud_bridge.get_recent_commits("test-repo")
        assert len(commits[0]["message"]) <= 80

    @patch("github_mud_bridge.urllib.request.urlopen")
    def test_with_since_parameter(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"[]"
        mock_urlopen.return_value = mock_resp

        github_mud_bridge.get_recent_commits("test-repo", since="2026-01-01T00:00:00Z")
        call_args = mock_urlopen.call_args
        url = call_args[0][0].full_url
        assert "since=2026-01-01" in url


# ===================== activity_to_mud_events =====================

class TestActivityToMudEvents:
    def test_empty_activity_returns_empty(self):
        events = github_mud_bridge.activity_to_mud_events({})
        assert events == []

    def test_fix_commit_classified_as_repair(self):
        activity = {
            "holodeck-rust": [
                {"sha": "abc1234", "message": "fix: resolve crash on startup", "author": "A", "date": "2026-04-13T10:00:00Z"}
            ]
        }
        events = github_mud_bridge.activity_to_mud_events(activity)
        assert len(events) == 1
        assert events[0]["type"] == "repair"

    def test_feat_commit_classified_as_construction(self):
        activity = {
            "flux-runtime": [
                {"sha": "def5678", "message": "feat: add new warp core simulation", "author": "B", "date": "2026-04-13T10:00:00Z"}
            ]
        }
        events = github_mud_bridge.activity_to_mud_events(activity)
        assert events[0]["type"] == "construction"

    def test_test_commit_classified_as_training(self):
        activity = {
            "seed-mcp-v2": [
                {"sha": "ghi9012", "message": "test: verify bridge connections", "author": "C", "date": "2026-04-13T10:00:00Z"}
            ]
        }
        events = github_mud_bridge.activity_to_mud_events(activity)
        assert events[0]["type"] == "training"

    def test_doc_commit_classified_as_log(self):
        activity = {
            "lighthouse-keeper": [
                {"sha": "jkl3456", "message": "docs: update README for clarity", "author": "D", "date": "2026-04-13T10:00:00Z"}
            ]
        }
        events = github_mud_bridge.activity_to_mud_events(activity)
        assert events[0]["type"] == "log"

    def test_refactor_commit_classified_as_maintenance(self):
        activity = {
            "fleet-agent-api": [
                {"sha": "mno7890", "message": "refactor: clean up auth module", "author": "E", "date": "2026-04-13T10:00:00Z"}
            ]
        }
        events = github_mud_bridge.activity_to_mud_events(activity)
        assert events[0]["type"] == "maintenance"

    def test_generic_commit_classified_as_duty(self):
        activity = {
            "holodeck-c": [
                {"sha": "pqr1234", "message": "update submodule reference", "author": "F", "date": "2026-04-13T10:00:00Z"}
            ]
        }
        events = github_mud_bridge.activity_to_mud_events(activity)
        assert events[0]["type"] == "duty"

    def test_hotfix_commit_classified_as_repair(self):
        activity = {
            "holodeck-cuda": [
                {"sha": "stu5678", "message": "hotfix: patch memory leak in renderer", "author": "G", "date": "2026-04-13T10:00:00Z"}
            ]
        }
        events = github_mud_bridge.activity_to_mud_events(activity)
        assert events[0]["type"] == "repair"

    def test_bug_commit_classified_as_repair(self):
        activity = {
            "holodeck-go": [
                {"sha": "vwx9012", "message": "bug: handle nil pointer in parser", "author": "H", "date": "2026-04-13T10:00:00Z"}
            ]
        }
        events = github_mud_bridge.activity_to_mud_events(activity)
        assert events[0]["type"] == "repair"

    def test_build_commit_classified_as_construction(self):
        activity = {
            "holodeck-zig": [
                {"sha": "yza3456", "message": "build: add cross-compilation for ARM", "author": "I", "date": "2026-04-13T10:00:00Z"}
            ]
        }
        events = github_mud_bridge.activity_to_mud_events(activity)
        assert events[0]["type"] == "construction"

    def test_events_sorted_newest_first(self):
        activity = {
            "repo1": [
                {"sha": "aaa", "message": "old commit", "author": "A", "date": "2026-04-10T10:00:00Z"},
                {"sha": "bbb", "message": "new commit", "author": "B", "date": "2026-04-13T10:00:00Z"},
            ]
        }
        events = github_mud_bridge.activity_to_mud_events(activity)
        assert events[0]["sha"] == "bbb"  # newest first
        assert events[1]["sha"] == "aaa"

    def test_multiple_repos_preserved(self):
        activity = {
            "repo1": [
                {"sha": "a1", "message": "fix: thing", "author": "A", "date": "2026-04-13T10:00:00Z"},
            ],
            "repo2": [
                {"sha": "b1", "message": "feat: thing2", "author": "B", "date": "2026-04-13T11:00:00Z"},
            ],
        }
        events = github_mud_bridge.activity_to_mud_events(activity)
        assert len(events) == 2
        repos = {e["repo"] for e in events}
        assert repos == {"repo1", "repo2"}

    def test_spec_commit_classified_as_training(self):
        activity = {
            "fleet-liaison-tender": [
                {"sha": "cde1234", "message": "spec: define tender protocol v2", "author": "J", "date": "2026-04-13T10:00:00Z"}
            ]
        }
        events = github_mud_bridge.activity_to_mud_events(activity)
        assert events[0]["type"] == "training"


# ===================== generate_activity_report =====================

class TestGenerateActivityReport:
    def test_empty_events_returns_no_activity_message(self):
        report = github_mud_bridge.generate_activity_report([])
        assert "No recent" in report

    def test_report_contains_total_count(self):
        events = [
            {"type": "repair", "repo": "r1", "sha": "abc", "message": "fix stuff", "time": "2026-04-13T10:00:00Z"},
            {"type": "construction", "repo": "r2", "sha": "def", "message": "add things", "time": "2026-04-13T11:00:00Z"},
        ]
        report = github_mud_bridge.generate_activity_report(events)
        assert "Total commits: 2" in report

    def test_report_shows_type_counts(self):
        events = [
            {"type": "repair", "repo": "r1", "sha": "a", "message": "m", "time": "2026-04-13T10:00:00Z"},
            {"type": "repair", "repo": "r1", "sha": "b", "message": "m2", "time": "2026-04-13T11:00:00Z"},
            {"type": "construction", "repo": "r2", "sha": "c", "message": "m3", "time": "2026-04-13T12:00:00Z"},
        ]
        report = github_mud_bridge.generate_activity_report(events)
        assert "repair: 2" in report
        assert "construction: 1" in report

    def test_report_shows_recent_commits(self):
        events = [
            {"type": "duty", "repo": "holodeck-rust", "sha": "abc1234", "message": "update deps", "time": "2026-04-13T10:00:00Z"},
        ]
        report = github_mud_bridge.generate_activity_report(events)
        assert "holodeck-rust" in report
        assert "abc1234" in report
