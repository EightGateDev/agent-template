# Google Calendar via gog CLI

Manage Google Calendar through the `gog` CLI tool
(https://github.com/steipete/gogcli). Use `bash_exec` to run commands.

## Quick usage

If the user asked to view/create/update/delete events, skip setup.
First check auth is alive:

```bash
gog auth list 2>/dev/null || true
```

If it shows an account with `calendar` in services → **use it
immediately**, no confirmation needed. Proceed directly with the user's
request via the commands below.

**If no account is authorized, gog is missing, or a command returns an
auth error** — load the full setup protocol by running:

```bash
cat skills/google_calendar/SETUP.md
```

This loads the one-time onboarding (install, OAuth client, headless
auth flow) on demand, keeping this reference short for the common case
where everything is already wired.

## Common commands

### List events

```bash
# Events on a specific day — the offset MUST match the owner's timezone
# ($AGENT_TIMEZONE; e.g. +03:00 for Europe/Kyiv in summer). Do not use +04:00 blindly.
gog calendar events primary --from 2026-04-17T00:00:00+03:00 --to 2026-04-17T23:59:59+03:00

# Upcoming events this week (a UTC range is fine for a multi-day window)
gog calendar events primary --from 2026-04-13T00:00:00Z --to 2026-04-20T00:00:00Z
```

`primary` is the default calendar — **read ONLY `primary`** unless the user
explicitly names another. Do NOT iterate `gog calendar list` and merge other
calendars into the answer: shared / subscribed / holiday calendars contain events
the user did NOT create (e.g. someone else's "training"), and surfacing them as
"your events" is a bug. If you ever do read a non-primary calendar, label the
source explicitly. `gog calendar list` is only for picking a calendar on request.

### Create an event

```bash
gog calendar create primary \
  --summary "Meeting with Alex" \
  --from 2026-04-15T14:00:00+03:00 \
  --to   2026-04-15T15:00:00+03:00
```

With a color (IDs 1–11, see `gog calendar colors`):
`--event-color 7`

### Update / delete

```bash
gog calendar update primary <eventId> --summary "New title" --event-color 4
gog calendar delete primary <eventId>
```

### Colors

Event color IDs:
- 1 #a4bdfc · 2 #7ae7bf · 3 #dbadff · 4 #ff887c · 5 #fbd75b · 6 #ffb878
- 7 #46d6db · 8 #e1e1e1 · 9 #5484ed · 10 #51b749 · 11 #dc2127

## Time format

ISO 8601: `2026-04-15T14:00:00+03:00` or `...Z`. Date-only (all-day):
`2026-04-15`.

Get the current local time. The agent process runs with `TZ=$AGENT_TIMEZONE`
(set in `.env`), so the system clock is already in the owner's timezone — no
manual offset math, and no hard-coded `hours=4`:

```bash
# TZ-aware "now" — offset matches the owner's timezone automatically:
python3 -c "from datetime import datetime; print(datetime.now().astimezone().isoformat())"
# or simply:
date --iso-8601=seconds
```

## Best practices

- **Always fetch fresh state.** Calendar is a live data source — the
  user can add, edit, or delete events outside the bot between turns.
  On any read query ("что у меня в пятницу?", "какие события на этой
  неделе?", "покажи расписание"), **always run `gog calendar events`**
  against the real calendar, even if the conversation history already
  contains mentions of events. Never answer calendar questions from
  memory alone. The same goes for "did I already create X?" — check
  with a real query, don't trust the conversation log.
- Update/delete triggers an automatic confirmation card — call
  `bash_exec` normally, the system shows a preview with Confirm/Cancel.
- Creating an event does NOT pop a confirmation card, but you MUST state the
  resolved weekday + date you used in your reply, so the user can catch a slip.
- Use `primary` by default — read ONLY primary (see "List events" above).
- Timezone: the process runs with `TZ=$AGENT_TIMEZONE`, so local time is already
  correct. Cross-check the owner's MEMORY timezone if unsure. Never assume UTC.

## Date & weekday discipline (READ BEFORE CREATING) — critical

A real bug happened here: the user said "Saturday the 20th"; the agent wrote the
events on Sunday the 21st. Prevent it:

1. **Resolve the absolute date yourself, every time.** Never trust a weekday→date
   mapping from memory or guesswork — compute it in the owner's timezone:
   ```bash
   date --iso-8601=seconds                       # today, local TZ
   python3 -c "import datetime; d=datetime.date(2026,6,20); print(d.isoformat(), d.strftime('%A'))"
   ```
2. **If the user names BOTH a weekday and a day-number** ("субота 20-е"), verify
   they agree. If the 20th is actually a Friday, STOP and ask — do not silently
   pick one.
3. **Echo it back.** Your reply must name the weekday AND the date you wrote
   ("Записав на суботу, 20 червня"), so any mistake is visible immediately.
4. Build `--from`/`--to` with the explicit local offset (e.g. `+03:00` for Kyiv),
   never a bare time the box might read as UTC.
