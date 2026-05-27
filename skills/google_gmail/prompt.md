# Gmail via gog CLI

Manage Gmail through the `gog` CLI tool (https://github.com/steipete/gogcli).
Use `bash_exec` to run commands.

## Quick usage

If the user asked to read/search/send email, skip setup. First check
auth is alive:

```bash
gog auth list 2>/dev/null || true
```

If it shows an account with `gmail` in services → **use it immediately**,
no confirmation needed. Proceed directly with the commands below.

**If no account is authorized, gog is missing, or a command returns an
auth error** — load the shared setup protocol (it's the same flow for
Calendar and Gmail, one OAuth client covers both):

```bash
cat skills/google_calendar/SETUP.md
```

## Common commands

### Search messages

```bash
# Default returns only 10 — use --all to get all results
gog gmail search 'newer_than:7d' --all
gog gmail search 'is:unread' --all
gog gmail messages search "in:inbox from:alex@example.com" --all
# Use --max N only when you intentionally want a limited sample
gog gmail search 'label:work' --max 20
```

`gog gmail search` = one row per thread. `gog gmail messages search` =
one row per individual message.

Gmail query syntax: `from:x@y.com`, `to:me`, `subject:invoice`,
`is:unread|starred|important`, `has:attachment`, `after:YYYY/MM/DD`,
`before:YYYY/MM/DD`, `label:work`, `in:inbox`, `newer_than:7d`.

### Send an email

Plain, one-line body:
```bash
gog gmail send --to alex@example.com --subject "Hi" --body "Hello"
```

Multi-line via stdin:
```bash
gog gmail send --to alex@example.com --subject "Follow-up" \
  --body-file - <<'EOF'
Hi Alex,

Thanks for meeting. Next steps:
- Item one
- Item two

Best
EOF
```

HTML: `--body-html "<p>...</p>"`. Reply: `--reply-to-message-id <msgId>`.

Note: `--body` does NOT interpret `\n`. For inline newlines use a
heredoc with `--body-file -` or `$'Line 1\nLine 2'`. Prefer plain text
over HTML.

### Drafts

```bash
gog gmail drafts create --to alex@example.com --subject "Hi" --body-file ./msg.txt
gog gmail drafts list --no-input
gog gmail drafts send <draftId> --no-input
gog gmail drafts delete <draftId> --no-input
```

### Delete / trash messages

```bash
gog gmail trash <messageId> --no-input
gog gmail messages delete <messageId> --no-input
```

**Always pass `--no-input`** for any `drafts delete`, `drafts send`,
`trash`, or `messages delete` command. Without it, gog waits on an
interactive TTY prompt and `bash_exec` will time out after 30s.

### JSON output

Append `--json --no-input` for machine-readable output.

## Best practices

- Sending emails, draft sends, draft deletes, and message trash/delete
  all trigger an automatic confirmation card — call `bash_exec`
  normally with `--no-input`, the system shows a preview with
  Confirm/Cancel and re-runs the command on approval.
- For long emails, summarize instead of dumping the full body to the
  user.
- "Reply to John's email" → search first, then construct the reply
  with `--reply-to-message-id`.
- "What's new?" → `is:unread`.
