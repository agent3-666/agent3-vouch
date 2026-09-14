"""The job itself: a school newsletter goes in, calendar entries come out.

This is what the hired agent actually does for the money. It is deterministic on purpose, so the
demo produces the same openable file every time and needs no model and no account.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
    )
}

# "Tuesday 23 September, 6.30pm - Year 4 parents evening (school hall)"
LINE = re.compile(
    r"^\s*(?:mon|tues|wednes|thurs|fri|satur|sun)day\s+(?P<day>\d{1,2})\s+(?P<month>[a-z]+)"
    r"(?:\s*,\s*(?P<hour>\d{1,2})(?:[.:](?P<minute>\d{2}))?\s*(?P<ampm>am|pm))?"
    r"\s*[-–]\s*(?P<title>[^(]+?)\s*(?:\((?P<location>[^)]*)\))?\s*$",
    re.IGNORECASE,
)


@dataclass
class Event:
    title: str
    start: datetime
    minutes: int
    location: str

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.minutes)


def parse(text: str, year: int) -> list[Event]:
    events: list[Event] = []
    for raw in text.splitlines():
        match = LINE.match(raw.strip())
        if not match:
            continue
        month = MONTHS.get(match.group("month").lower())
        if not month:
            continue
        hour = int(match.group("hour") or 9)
        minute = int(match.group("minute") or 0)
        ampm = (match.group("ampm") or "").lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        all_day = match.group("hour") is None
        events.append(
            Event(
                title=" ".join(match.group("title").split()),
                start=datetime(year, month, int(match.group("day")), hour, minute),
                minutes=24 * 60 if all_day else 60,
                location=" ".join((match.group("location") or "").split()),
            )
        )
    return events


def to_ics(events: list[Event], calendar_name: str = "School") -> str:
    stamp = "20260914T000000Z"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Agent3 Vouch//School calendar//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{calendar_name}",
    ]
    for i, event in enumerate(events, start=1):
        lines += [
            "BEGIN:VEVENT",
            f"UID:vouch-{i}-{event.start:%Y%m%dT%H%M%S}@agent3",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{event.start:%Y%m%dT%H%M%S}",
            f"DTEND:{event.end:%Y%m%dT%H%M%S}",
            f"SUMMARY:{event.title}",
        ]
        if event.location:
            lines.append(f"LOCATION:{event.location}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def do_the_job(newsletter_path: str | Path, out_path: str | Path, year: int = 2026) -> list[Event]:
    text = Path(newsletter_path).read_text()
    events = parse(text, year)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(to_ics(events))
    return events
