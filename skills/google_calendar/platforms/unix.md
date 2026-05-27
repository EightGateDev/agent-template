# Google setup — Linux / macOS

## Canonical paths

- OAuth client JSON → `~/.config/agent-mvp/google-client.json`
- gog tokens → `~/.config/gog/` (managed by gog)

## Step 1 — Install gog

Detect architecture:

```bash
uname -s && uname -m
```

**Linux x86_64:**
```bash
curl -L https://github.com/steipete/gogcli/releases/download/v0.12.0/gogcli_0.12.0_linux_amd64.tar.gz | tar -xz -C /usr/local/bin && chmod +x /usr/local/bin/gog
```

**Linux arm64:**
```bash
curl -L https://github.com/steipete/gogcli/releases/download/v0.12.0/gogcli_0.12.0_linux_arm64.tar.gz | tar -xz -C /usr/local/bin && chmod +x /usr/local/bin/gog
```

**macOS (any arch):**
```bash
brew install steipete/tap/gogcli
```

Verify:
```bash
gog --help | head
```

## Step 3a — Move JSON to canonical path

```bash
mkdir -p ~/.config/agent-mvp
mv "<upload_path>" ~/.config/agent-mvp/google-client.json
gog auth credentials ~/.config/agent-mvp/google-client.json
```
