#!/usr/bin/env python3
"""Google Calendar — DEPRECATED direct handler (intentionally disabled).

This old service-account / python path created events with a hard-coded
`timeZone: "UTC"`, which shifted dates for non-UTC owners — a real bug.

Google Calendar is driven ONLY through the `gog` CLI. See prompt.md / SETUP.md:
  List:   gog calendar events primary --from <ISO+offset> --to <ISO+offset>
  Create: gog calendar create  primary --summary "..." --from <ISO+offset> --to <ISO+offset>
Always use the owner's timezone offset (the process runs with TZ=$AGENT_TIMEZONE),
NEVER UTC.
"""
import sys

sys.stderr.write(
    "google_calendar/handler.py is DISABLED — use the gog CLI instead "
    "(see skills/google_calendar/prompt.md). Example:\n"
    "  gog calendar create primary --summary \"Title\" "
    "--from 2026-06-20T11:00:00+03:00 --to 2026-06-20T12:00:00+03:00\n"
)
sys.exit(1)
