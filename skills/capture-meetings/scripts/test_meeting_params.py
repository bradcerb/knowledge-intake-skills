#!/usr/bin/env python3
"""Tests for capture-meetings parameter resolution and raw JSON Lines."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import meeting_params


TODAY = date(2026, 10, 8)
SCRIPT = Path(__file__).with_name("meeting_params.py")
SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"
RAW_DOC = Path(__file__).resolve().parents[1] / "references" / "raw-output.md"
README = Path(__file__).resolve().parents[3] / "README.md"


def run_cli(args: list[str], stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )


class ResolveTests(unittest.TestCase):
    def test_omitted_parameters_keep_capture_defaults(self) -> None:
        payload = meeting_params.resolve_query(today=TODAY)
        self.assertEqual(
            payload,
            {
                "today": "2026-10-08",
                "date_range_applied": False,
                "date_start": None,
                "date_end": None,
                "date_inclusive": None,
                "person": None,
                "output": "capture",
                "write_raw": True,
                "write_notion": True,
                "mark_handled": True,
                "include_already_handled": False,
                "return_raw": False,
            },
        )

    def test_last_seven_days_is_inclusive_through_today(self) -> None:
        payload = meeting_params.resolve_query(date_range="last 7 days", today=TODAY)
        self.assertEqual(payload["date_start"], "2026-10-02")
        self.assertEqual(payload["date_end"], "2026-10-08")
        self.assertEqual(payload["date_inclusive"], True)

    def test_last_two_weeks_and_number_words(self) -> None:
        payload = meeting_params.resolve_query(date_range="last two weeks", today=TODAY)
        self.assertEqual(payload["date_start"], "2026-09-25")
        self.assertEqual(payload["date_end"], "2026-10-08")
        same = meeting_params.resolve_query(date_range="Last 1 week", today=TODAY)
        week = meeting_params.resolve_query(date_range="last 7 days", today=TODAY)
        self.assertEqual(same["date_start"], week["date_start"])
        self.assertEqual(same["date_end"], week["date_end"])

    def test_explicit_window_from_range_or_start_end(self) -> None:
        from_range = meeting_params.resolve_query(date_range="2026-09-01..2026-09-14", today=TODAY)
        from_flags = meeting_params.resolve_query(start="2026-09-01", end="2026-09-14", today=TODAY)
        self.assertEqual(from_range["date_start"], "2026-09-01")
        self.assertEqual(from_range["date_end"], "2026-09-14")
        self.assertEqual(from_flags["date_start"], from_range["date_start"])
        self.assertEqual(from_flags["date_end"], from_range["date_end"])

    def test_invalid_windows_fail(self) -> None:
        with self.assertRaises(meeting_params.QueryError):
            meeting_params.resolve_query(date_range="yesterday", today=TODAY)
        with self.assertRaises(meeting_params.QueryError):
            meeting_params.resolve_query(date_range="last 7 months", today=TODAY)
        with self.assertRaises(meeting_params.QueryError):
            meeting_params.resolve_query(start="2026-09-14", end="2026-09-01", today=TODAY)
        with self.assertRaises(meeting_params.QueryError):
            meeting_params.resolve_query(date_range="last 7 days", start="2026-09-01", today=TODAY)
        with self.assertRaises(meeting_params.QueryError):
            meeting_params.resolve_query(output="transcript", today=TODAY)

    def test_output_modes(self) -> None:
        raw = meeting_params.resolve_query(output="raw", today=TODAY)
        both = meeting_params.resolve_query(output="BOTH", person="  name@example.com  ", today=TODAY)
        self.assertFalse(raw["write_raw"])
        self.assertFalse(raw["write_notion"])
        self.assertFalse(raw["mark_handled"])
        self.assertTrue(raw["include_already_handled"])
        self.assertTrue(raw["return_raw"])
        self.assertTrue(both["write_raw"])
        self.assertTrue(both["write_notion"])
        self.assertTrue(both["mark_handled"])
        self.assertFalse(both["include_already_handled"])
        self.assertTrue(both["return_raw"])
        self.assertEqual(both["person"], "name@example.com")


class FilterTests(unittest.TestCase):
    def test_email_match_is_case_insensitive_and_ignores_display_name(self) -> None:
        meetings = [
            {
                "external_id": "keep",
                "attendees": [{"name": "Other Name", "email": "Name@Example.com"}],
            },
            {
                "external_id": "drop-name-only",
                "attendees": [{"name": "Teammate"}],
            },
            {
                "external_id": "drop-unmapped",
                "attendees": [{"displayName": "Teammate", "mail": "name@example.com"}],
            },
        ]
        selected = meeting_params.filter_meetings(meetings, "Teammate <name@example.com>")
        self.assertEqual([item["external_id"] for item in selected], ["keep"])

    def test_name_match_collapses_case_and_whitespace(self) -> None:
        meetings = [
            {"external_id": "keep", "attendees": ["Teammate   Name <name@example.com>"]},
            {"external_id": "email-only", "attendees": ["name@example.com"]},
        ]
        selected = meeting_params.filter_meetings(meetings, "teammate name")
        self.assertEqual([item["external_id"] for item in selected], ["keep"])

    def test_omitted_person_returns_every_meeting(self) -> None:
        meetings = [{"external_id": "a", "attendees": []}, {"external_id": "b"}]
        self.assertEqual(meeting_params.filter_meetings(meetings, None), meetings)
        self.assertEqual(meeting_params.filter_meetings(meetings, "   "), meetings)

    def test_string_email_form_matches(self) -> None:
        meetings = [{"external_id": "keep", "attendees": ["Teammate <name@example.com>"]}]
        selected = meeting_params.filter_meetings(meetings, "name@example.com")
        self.assertEqual(len(selected), 1)


class FormatTests(unittest.TestCase):
    def test_jsonl_is_stable_sorted_and_one_line_per_meeting(self) -> None:
        later = {
            "title": "Later",
            "occurred_at": "2026-10-02T19:00:00Z",
            "timezone": "Etc/UTC",
            "attendees": [
                {"name": "Teammate", "email": "name@example.com"},
                "Teammate <name@example.com>",
            ],
            "external_id": "evt_b:art_b",
            "source_url": "https://example.com/meet/b",
            "transcript": 'Teammate said "hello".\nNext line.',
        }
        earlier = {
            "title": "Earlier",
            "occurred_at": "2026-10-01T15:00:00-04:00",
            "timezone": "",
            "attendees": ["name@example.com"],
            "external_id": "evt_a:art_a",
            "source_url": "",
            "transcript": "café notes",
            "ignored": "drop me",
        }
        text = meeting_params.format_raw_jsonl([later, earlier])
        lines = text.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(text.endswith("\n"))
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        self.assertEqual(first["external_id"], "evt_a:art_a")
        self.assertEqual(second["external_id"], "evt_b:art_b")
        self.assertEqual(
            list(first.keys()),
            [
                "title",
                "occurred_at",
                "timezone",
                "attendees",
                "external_id",
                "source_url",
                "transcript",
            ],
        )
        self.assertEqual(first["attendees"], ["name@example.com"])
        self.assertEqual(second["attendees"], ["Teammate <name@example.com>"])
        self.assertIn("café", lines[0])
        self.assertNotIn("\n", lines[1])
        self.assertIn("\\n", lines[1])
        self.assertNotIn("ignored", lines[0])

    def test_rejects_missing_timezone_offset_and_empty_transcript(self) -> None:
        base = {
            "title": "Sync",
            "occurred_at": "2026-10-01T19:00:00",
            "timezone": "Etc/UTC",
            "attendees": [],
            "external_id": "evt:art",
            "source_url": "",
            "transcript": "notes",
        }
        with self.assertRaises(meeting_params.QueryError):
            meeting_params.format_raw_jsonl([base])
        base["occurred_at"] = "2026-10-01T19:00:00Z"
        base["transcript"] = "   "
        with self.assertRaises(meeting_params.QueryError):
            meeting_params.format_raw_jsonl([base])

    def test_empty_input_is_an_empty_payload(self) -> None:
        self.assertEqual(meeting_params.format_raw_jsonl([]), "")


class CliTests(unittest.TestCase):
    def test_resolve_cli_default_and_relative(self) -> None:
        omitted = run_cli(["resolve", "--today", "2026-10-08"])
        self.assertEqual(omitted.returncode, 0, omitted.stderr)
        payload = json.loads(omitted.stdout)
        self.assertFalse(payload["date_range_applied"])
        self.assertEqual(payload["output"], "capture")
        ranged = run_cli(["resolve", "--date-range", "last two weeks", "--today", "2026-10-08"])
        self.assertEqual(ranged.returncode, 0, ranged.stderr)
        self.assertEqual(json.loads(ranged.stdout)["date_start"], "2026-09-25")

    def test_filter_and_format_cli(self) -> None:
        meetings = [
            {
                "title": "Sync",
                "occurred_at": "2026-10-01T19:00:00Z",
                "timezone": "Etc/UTC",
                "attendees": [{"name": "Teammate", "email": "name@example.com"}],
                "external_id": "evt:art",
                "source_url": "https://example.com/meet/evt",
                "transcript": "Hello",
            }
        ]
        encoded = json.dumps(meetings)
        filtered = run_cli(["filter", "--person", "name@example.com"], stdin=encoded)
        self.assertEqual(filtered.returncode, 0, filtered.stderr)
        self.assertEqual(json.loads(filtered.stdout)[0]["external_id"], "evt:art")
        formatted = run_cli(["format"], stdin=encoded)
        self.assertEqual(formatted.returncode, 0, formatted.stderr)
        expected = meetings[0] | {"attendees": ["Teammate <name@example.com>"]}
        self.assertEqual(json.loads(formatted.stdout), expected)

    def test_cli_rejects_unknown_output(self) -> None:
        result = run_cli(["resolve", "--output", "dump"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("output must be capture, raw, or both", result.stderr)


class DocsContractTests(unittest.TestCase):
    def test_skill_documents_parameters_and_default_window(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        for phrase in (
            "date_range",
            "person",
            "output",
            "configured lookback window",
            "output=raw",
            "both",
            "meeting_params.py",
            "does not fetch",
            "last 7 days",
            "last two weeks",
        ):
            self.assertIn(phrase, text)

    def test_readme_has_an_example_call_for_each_parameter(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn('date_range: "last two weeks"', text)
        self.assertIn('person: "name@example.com"', text)
        self.assertIn("output: raw", text)
        self.assertIn("last 7 days", text)

    def test_raw_output_doc_lists_the_payload_fields(self) -> None:
        text = RAW_DOC.read_text(encoding="utf-8")
        for field in (
            "title",
            "occurred_at",
            "timezone",
            "attendees",
            "external_id",
            "source_url",
            "transcript",
        ):
            self.assertIn(field, text)
        self.assertIn("jsonl", text.casefold())


if __name__ == "__main__":
    unittest.main()
