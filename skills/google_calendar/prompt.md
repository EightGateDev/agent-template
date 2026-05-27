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
# Events on a specific day (use the user's timezone)
gog calendar events primary --from 2026-04-17T00:00:00+04:00 --to 2026-04-17T23:59:59+04:00

# Upcoming events this week
gog calendar events primary --from 2026-04-13T00:00:00Z --to 2026-04-20T00:00:00Z
```

`primary` is the default calendar. `gog calendar list` lists calendars.

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

Get current time in the user's timezone (cross-platform, no pytz):

```bash
python3 -c "from datetime import datetime, timezone, timedelta; print(datetime.now(timezone(timedelta(hours=4))).isoformat())"
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
- Creating events does NOT need confirmation.
- Use `primary` by default unless user specifies another calendar.
- Timezone: read from owner MEMORY or derive from the Current date block
  in the system prompt.
