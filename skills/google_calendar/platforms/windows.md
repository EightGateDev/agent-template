# Google setup — Windows

## Canonical paths (Windows)

- OAuth client JSON → `$APPDATA/agent-mvp/google-client.json`
- gog tokens → `$APPDATA/gog/`

## Step 1 — Install gog (Windows)

Detect architecture:

```bash
uname -m
```

**x86_64 / AMD64:**
```bash
mkdir -p "$HOME/bin"
curl -L -o /tmp/gog.zip https://github.com/steipete/gogcli/releases/download/v0.12.0/gogcli_0.12.0_windows_amd64.zip
unzip -o /tmp/gog.zip -d "$HOME/bin"
rm /tmp/gog.zip
```

**arm64 / aarch64:**
```bash
mkdir -p "$HOME/bin"
curl -L -o /tmp/gog.zip https://github.com/steipete/gogcli/releases/download/v0.12.0/gogcli_0.12.0_windows_arm64.zip
unzip -o /tmp/gog.zip -d "$HOME/bin"
rm /tmp/gog.zip
```

Then tell the user to ensure `~/bin` is in their PATH (or move `gog.exe`
to a directory already in PATH).

Verify:
```bash
gog --help | head
```

## Step 3a — Move JSON to canonical path (Windows)

```bash
mkdir -p "$APPDATA/agent-mvp"
mv "<upload_path>" "$APPDATA/agent-mvp/google-client.json"
gog auth credentials "$APPDATA/agent-mvp/google-client.json"
```
