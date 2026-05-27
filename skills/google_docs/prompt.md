# Google Docs via gog CLI

Manage Google Docs through the `gog` CLI tool
(https://github.com/steipete/gogcli). Use `bash_exec` to run commands.

## Quick usage

If the user asked to create/read/edit a document, skip setup.
First check auth is alive:

```bash
gog auth list 2>/dev/null || true
```

If it shows an account with `docs` in services — **use it
immediately**. Proceed directly with commands below.

**If no account is authorized, gog is missing, or a command returns an
auth error** — load the shared setup protocol:

```bash
cat skills/google_calendar/SETUP.md
```

## Common commands

### Read a document
```bash
gog docs cat <docId>                    # plain text
gog docs info <docId>                   # metadata (title, dates, owner)
gog docs structure <docId>              # numbered paragraphs
```

### Create a document
```bash
gog docs create "My Document"
gog docs create "My Document" --parent <folderId>   # in specific folder
```

### Write / edit content
```bash
gog docs write <docId> --text "Full content here"
gog docs insert <docId> "text to insert" --index 1      # insert at position
gog docs edit <docId> "old text" "new text"              # find and replace
gog docs sed <docId> "s/pattern/replacement/g"           # regex replace
gog docs find-replace <docId> "find" "replace"
gog docs delete <docId> --start 10 --end 50              # delete range
gog docs clear <docId>                                   # clear all content
```

### Export / download
```bash
gog docs export <docId> --format pdf      # pdf|docx|txt|md
gog docs export <docId> --format md -o output.md
```

### Copy a document
```bash
gog docs copy <docId> "Copy Title"
```

### Find documents (via Drive)
```bash
gog drive search "name contains 'report'" --type document
gog drive search "modifiedTime > '2026-04-01'" --type document
```

## Best practices

- **Always fetch fresh state.** Docs is a live data source — read before editing.
- For long documents, use `gog docs structure` to see numbered paragraphs first.
- Use `gog docs cat` for reading content, `gog docs info` for metadata.
- Send/delete operations trigger confirmation cards automatically.
- `--no-input` flag prevents interactive prompts (important for batch ops).
- Prefer `gog docs edit` for targeted changes over `gog docs write` which replaces everything.
