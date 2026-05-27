# Google Sheets via gog CLI

Manage Google Sheets through the `gog` CLI tool
(https://github.com/steipete/gogcli). Use `bash_exec` to run commands.

## Quick usage

If the user asked to read/edit a spreadsheet, skip setup.
First check auth is alive:

```bash
gog auth list 2>/dev/null || true
```

If it shows an account with `sheets` in services — **use it
immediately**. Proceed directly with commands below.

**If no account is authorized, gog is missing, or a command returns an
auth error** — load the shared setup protocol:

```bash
cat skills/google_calendar/SETUP.md
```

## Common commands

### Read data
```bash
gog sheets get <spreadsheetId> "Sheet1!A1:D10"       # read range
gog sheets get <spreadsheetId> "Sheet1"               # read entire sheet
gog sheets metadata <spreadsheetId>                   # sheet info, tab names
```

### Write data
```bash
gog sheets update <spreadsheetId> "Sheet1!A1" "val1" "val2" "val3"   # single row
gog sheets update <spreadsheetId> "Sheet1!A1:C2" '["r1c1","r1c2","r1c3"],["r2c1","r2c2","r2c3"]'
gog sheets append <spreadsheetId> "Sheet1!A:D" "val1" "val2" "val3" "val4"  # append row
```

### Clear data
```bash
gog sheets clear <spreadsheetId> "Sheet1!A1:D10"
```

### Create a spreadsheet
```bash
gog sheets create "My Spreadsheet"
```

### Tab management
```bash
gog sheets add-tab <spreadsheetId> "New Tab"
gog sheets rename-tab <spreadsheetId> "Old Name" "New Name"
gog sheets delete-tab <spreadsheetId> "Tab Name" --force
```

### Formatting
```bash
gog sheets format <spreadsheetId> "Sheet1!A1:D1" --bold --bg-color "#4285f4" --fg-color white
gog sheets number-format <spreadsheetId> "Sheet1!B2:B100" --pattern "#,##0.00"
gog sheets freeze <spreadsheetId> --rows 1 --cols 1
gog sheets merge <spreadsheetId> "Sheet1!A1:D1"
gog sheets resize-columns <spreadsheetId> "A:D" --width 150
```

### Find and replace
```bash
gog sheets find-replace <spreadsheetId> "old value" "new value"
```

### Notes
```bash
gog sheets notes <spreadsheetId> "Sheet1!A1:A10"
gog sheets update-note <spreadsheetId> "Sheet1!A1" --note "This is a note"
```

### Export
```bash
gog sheets export <spreadsheetId> --format csv
gog sheets export <spreadsheetId> --format xlsx
```

### Find spreadsheets (via Drive)
```bash
gog drive search "name contains 'budget'" --type spreadsheet
gog drive search "modifiedTime > '2026-04-01'" --type spreadsheet
```

## Best practices

- **Always read before writing.** Check current data with `get` before `update`.
- Use `append` to add rows without overwriting existing data.
- Range format: `Sheet1!A1:D10` or just `Sheet1` for entire tab.
- For batch writes, pass multiple values: `"val1" "val2" "val3"`.
- `metadata` shows all tab names — use to verify tab exists before writing.
- Delete-tab triggers confirmation card automatically.
- `--no-input` flag prevents interactive prompts.
