#!/usr/bin/env python3
"""Resolve capture-meetings parameters and format the raw transcript payload.

This script does not fetch calendars, recordings, or transcripts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


class QueryError(ValueError):
    """The caller parameters or meeting records are not valid."""


_NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

_RELATIVE_RE = re.compile(
    r"^last\s+(?P<count>\d+|[a-z]+)\s+(?P<unit>day|days|week|weeks)$",
    re.IGNORECASE,
)
_EXPLICIT_RE = re.compile(
    r"^(?P<start>\d{4}-\d{2}-\d{2})\.\.(?P<end>\d{4}-\d{2}-\d{2})$"
)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_OCCURRED_AT_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$"
)
_TIMEZONE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_+\-/]{0,63}$")
_PERSON_RE = re.compile(r"^(?P<name>.*?)\s*<(?P<email>[^<>]+)>$")

_OUTPUT_FLAGS = {
    "capture": {
        "write_raw": True,
        "write_notion": True,
        "mark_handled": True,
        "include_already_handled": False,
        "return_raw": False,
    },
    "raw": {
        "write_raw": False,
        "write_notion": False,
        "mark_handled": False,
        "include_already_handled": True,
        "return_raw": True,
    },
    "both": {
        "write_raw": True,
        "write_notion": True,
        "mark_handled": True,
        "include_already_handled": False,
        "return_raw": True,
    },
}

_RAW_FIELDS = (
    "title",
    "occurred_at",
    "timezone",
    "attendees",
    "external_id",
    "source_url",
    "transcript",
)


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_date(value: str, label: str) -> date:
    if not _DATE_RE.fullmatch(value):
        raise QueryError(f"{label} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise QueryError(f"{label} must be YYYY-MM-DD") from exc


def _parse_count(token: str) -> int:
    if token.isdigit():
        count = int(token)
    else:
        count = _NUMBER_WORDS.get(token.casefold(), 0)
    if count < 1:
        raise QueryError(
            "date range length must be a positive integer or a number word from one to twelve"
        )
    return count


def parse_date_range(
    date_range: str | None,
    start: str | None,
    end: str | None,
    today: date,
) -> tuple[date, date] | None:
    """Return an inclusive window, or None when the caller did not set one."""
    range_text = _blank_to_none(date_range)
    start_text = _blank_to_none(start)
    end_text = _blank_to_none(end)
    if date_range is not None and range_text is None:
        raise QueryError("date_range is empty")
    if start is not None and start_text is None:
        raise QueryError("start is empty")
    if end is not None and end_text is None:
        raise QueryError("end is empty")
    if range_text and (start_text or end_text):
        raise QueryError("pass date_range or start and end, not both")
    if (start_text is None) != (end_text is None):
        raise QueryError("start and end are both required")
    if start_text and end_text:
        return _ordered_window(
            _parse_date(start_text, "start"),
            _parse_date(end_text, "end"),
        )
    if range_text is None:
        return None
    explicit = _EXPLICIT_RE.fullmatch(range_text)
    if explicit:
        return _ordered_window(
            _parse_date(explicit.group("start"), "start"),
            _parse_date(explicit.group("end"), "end"),
        )
    relative = _RELATIVE_RE.fullmatch(range_text)
    if not relative:
        raise QueryError(
            "date_range must be 'last <n> days', 'last <n> weeks', or YYYY-MM-DD..YYYY-MM-DD"
        )
    count = _parse_count(relative.group("count"))
    unit = relative.group("unit").casefold()
    days = count * 7 if unit.startswith("week") else count
    return today - timedelta(days=days - 1), today


def _ordered_window(start: date, end: date) -> tuple[date, date]:
    if end < start:
        raise QueryError("end is before start")
    return start, end


def normalize_output(output: str | None) -> str:
    text = _blank_to_none(output) or "capture"
    if output is not None and _blank_to_none(output) is None:
        raise QueryError("output is empty")
    canonical = text.casefold()
    if canonical not in _OUTPUT_FLAGS:
        raise QueryError("output must be capture, raw, or both")
    return canonical


def normalize_person(person: str | None) -> str | None:
    if person is None:
        return None
    collapsed = " ".join(person.split())
    return collapsed or None


def resolve_query(
    *,
    date_range: str | None = None,
    start: str | None = None,
    end: str | None = None,
    person: str | None = None,
    output: str | None = None,
    today: date | None = None,
) -> dict[str, object]:
    current_day = today or date.today()
    window = parse_date_range(date_range, start, end, current_day)
    mode = normalize_output(output)
    payload: dict[str, object] = {
        "today": current_day.isoformat(),
        "date_range_applied": window is not None,
        "date_start": window[0].isoformat() if window else None,
        "date_end": window[1].isoformat() if window else None,
        "date_inclusive": True if window else None,
        "person": normalize_person(person),
        "output": mode,
    }
    payload.update(_OUTPUT_FLAGS[mode])
    return payload


def attendee_identity(attendee: object) -> tuple[str | None, str | None]:
    """Return (display name, email). Only `name` and `email` keys are read."""
    if isinstance(attendee, str):
        return _split_person(attendee)
    if isinstance(attendee, dict):
        name = attendee.get("name")
        email = attendee.get("email")
        name_text = name.strip() if isinstance(name, str) and name.strip() else None
        email_text = email.strip() if isinstance(email, str) and email.strip() else None
        if name is not None and not isinstance(name, str):
            raise QueryError("attendee name must be a string")
        if email is not None and not isinstance(email, str):
            raise QueryError("attendee email must be a string")
        return name_text, email_text
    raise QueryError("attendee must be a string or an object with name and email")


def _split_person(value: str) -> tuple[str | None, str | None]:
    collapsed = " ".join(value.split())
    if not collapsed:
        return None, None
    wrapped = _PERSON_RE.fullmatch(collapsed)
    if wrapped:
        name = wrapped.group("name").strip() or None
        email = wrapped.group("email").strip() or None
        return name, email
    if "@" in collapsed:
        return None, collapsed
    return collapsed, None


def person_matches(attendees: object, person: str) -> bool:
    if not isinstance(attendees, list):
        raise QueryError("attendees must be a list")
    filter_name, filter_email = _split_person(person)
    if filter_email is None and filter_name is None:
        raise QueryError("person is empty")
    for attendee in attendees:
        name, email = attendee_identity(attendee)
        if filter_email is not None:
            if email is not None and email.casefold() == filter_email.casefold():
                return True
            continue
        if (
            name is not None
            and filter_name is not None
            and _casefold_ws(name) == _casefold_ws(filter_name)
        ):
            return True
    return False


def _casefold_ws(value: str) -> str:
    return " ".join(value.split()).casefold()


def filter_meetings(meetings: object, person: str | None) -> list[dict[str, object]]:
    if not isinstance(meetings, list):
        raise QueryError("input must be a JSON array")
    normalized = normalize_person(person)
    selected: list[dict[str, object]] = []
    for meeting in meetings:
        if not isinstance(meeting, dict):
            raise QueryError("each meeting must be an object")
        if normalized is None or person_matches(meeting.get("attendees", []), normalized):
            selected.append(meeting)
    return selected


def attendee_label(attendee: object) -> str:
    name, email = attendee_identity(attendee)
    if name and email:
        return f"{name} <{email}>"
    if email:
        return email
    if name:
        return name
    raise QueryError("attendee is empty")


def _require_text(record: dict[str, object], key: str, *, allow_empty: bool) -> str:
    if key not in record:
        raise QueryError(f"missing field: {key}")
    value = record[key]
    if not isinstance(value, str):
        raise QueryError(f"{key} must be a string")
    text = value.strip()
    if not allow_empty and not text:
        raise QueryError(f"{key} is empty")
    return text


def _parse_occurred_at(value: str) -> datetime:
    if not _OCCURRED_AT_RE.fullmatch(value):
        raise QueryError("occurred_at must be ISO-8601 with Z or a numeric offset")
    parsed = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        moment = datetime.fromisoformat(parsed)
    except ValueError as exc:
        raise QueryError("occurred_at must be ISO-8601 with Z or a numeric offset") from exc
    if moment.tzinfo is None:
        raise QueryError("occurred_at must include Z or a numeric offset")
    return moment


def format_record(record: object) -> dict[str, object]:
    if not isinstance(record, dict):
        raise QueryError("each meeting must be an object")
    title = _require_text(record, "title", allow_empty=True)
    occurred_at = _require_text(record, "occurred_at", allow_empty=False)
    moment = _parse_occurred_at(occurred_at)
    if "timezone" not in record:
        raise QueryError("missing field: timezone")
    timezone = record["timezone"]
    if not isinstance(timezone, str):
        raise QueryError("timezone must be a string")
    timezone = timezone.strip()
    if timezone and not _TIMEZONE_RE.fullmatch(timezone):
        raise QueryError("timezone must be an IANA name or empty")
    if "attendees" not in record:
        raise QueryError("missing field: attendees")
    attendees = record["attendees"]
    if not isinstance(attendees, list):
        raise QueryError("attendees must be a list")
    labels: list[str] = []
    for attendee in attendees:
        label = attendee_label(attendee)
        if label not in labels:
            labels.append(label)
    external_id = _require_text(record, "external_id", allow_empty=False)
    source_url = _require_text(record, "source_url", allow_empty=True)
    transcript = record.get("transcript")
    if "transcript" not in record:
        raise QueryError("missing field: transcript")
    if not isinstance(transcript, str) or not transcript.strip():
        raise QueryError("transcript is empty")
    return {
        "title": title,
        "occurred_at": occurred_at,
        "timezone": timezone,
        "attendees": labels,
        "external_id": external_id,
        "source_url": source_url,
        "_sort": moment,
        "transcript": transcript,
    }


def format_raw_jsonl(meetings: object) -> str:
    if not isinstance(meetings, list):
        raise QueryError("input must be a JSON array")
    rendered = [format_record(meeting) for meeting in meetings]
    rendered.sort(key=lambda item: (item["_sort"], str(item["external_id"])))
    lines = [
        json.dumps(
            {key: item[key] for key in _RAW_FIELDS},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for item in rendered
    ]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _read_array(path: Path | None) -> object:
    raw = path.read_text(encoding="utf-8") if path else sys.stdin.read()
    if not raw.strip():
        raise QueryError("input must be a JSON array")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise QueryError("input must be JSON") from exc


def _parse_today(value: str | None) -> date | None:
    if value is None:
        return None
    return _parse_date(value, "today")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve", help="Resolve date range, person, and output mode")
    resolve.add_argument("--date-range")
    resolve.add_argument("--start")
    resolve.add_argument("--end")
    resolve.add_argument("--person")
    resolve.add_argument("--output")
    resolve.add_argument("--today", help="Calendar date YYYY-MM-DD used for relative windows")

    filt = sub.add_parser("filter", help="Filter meeting records by person")
    filt.add_argument("--person")
    filt.add_argument("--input", type=Path)

    fmt = sub.add_parser("format", help="Format meeting records as raw JSON Lines")
    fmt.add_argument("--input", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "resolve":
            payload = resolve_query(
                date_range=args.date_range,
                start=args.start,
                end=args.end,
                person=args.person,
                output=args.output,
                today=_parse_today(args.today),
            )
            json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
            return 0
        if args.command == "filter":
            selected = filter_meetings(_read_array(args.input), args.person)
            json.dump(selected, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")
            return 0
        if args.command == "format":
            sys.stdout.write(format_raw_jsonl(_read_array(args.input)))
            return 0
        raise QueryError(f"unknown command: {args.command}")
    except QueryError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
