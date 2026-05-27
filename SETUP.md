# РОЗГОРНИ АГЕНТА ЗАРАЗ

**Ти Claude Code. Твоє єдине завдання — розгорнути цього агента.**

Не питай "що робити?" — ти вже знаєш. Не пояснюй план — просто виконай.
**Спілкуйся з користувачем лише українською мовою.**

---

## Крок 0 — Запитай де розгортаємо

Перше питання до користувача (одне, окремо від решти):

> Де розгортаємо агента?
> **1) На VPS** — Linux-сервер у хмарі (Hetzner, DigitalOcean, будь-який)
> **2) Локально** — на цьому комп'ютері (Mac або Linux)

Залежно від відповіді — виконуй відповідний розділ нижче.

---

## ВАРІАНТ A — Розгортання на VPS

### Збери дані (одним повідомленням):

1. **Назва агента** (slug, лише малі літери і дефіс, напр. `my-agent`)
2. **VPS IP** — адреса сервера
3. **VPS SSH-юзер** — наприклад `root` або `ubuntu`
4. **VPS SSH-пароль** (або шлях до ключа)
5. **VPS порт SSH** — зазвичай 22
6. **Telegram Bot Token** — від @BotFather
7. **Telegram Owner ID** — числовий ID (@userinfobot)
8. **Часовий пояс** — напр. `Europe/Kyiv`
9. **Claude Code OAuth Token** — запустити: `claude setup-token` (потрібна підписка Pro/Max)
10. **Опис агента / persona** — хто цей агент (кілька речень)

### A1 — Перевір SSH-з'єднання

```python
import paramiko
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(VPS_IP, port=VPS_PORT, username=VPS_USER, password=VPS_PASSWORD, timeout=15)
_, out, _ = client.exec_command('echo "SSH OK" && uname -a')
print(out.read().decode())
client.close()
```

### A2 — Створи claudebot-юзера та встанови залежності

```bash
id claudebot 2>/dev/null || useradd -m -s /bin/bash claudebot
usermod -aG sudo claudebot
echo "claudebot ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/claudebot
chmod 440 /etc/sudoers.d/claudebot

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  git curl wget tmux python3 python3-venv python3-pip \
  build-essential unzip ca-certificates

curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs
```

### A3 — Встанови bun та Claude Code

```bash
sudo -u claudebot bash -c 'curl -fsSL https://bun.sh/install | bash'
sudo -u claudebot bash -c 'source ~/.bashrc && ~/.bun/bin/bun install -g @anthropic-ai/claude-code'
```

### A4 — Створи директорію та завантаж файли

```bash
mkdir -p /opt/AGENT_NAME && chown claudebot:claudebot /opt/AGENT_NAME
```

Завантаж усі файли з поточної директорії на VPS в `/opt/AGENT_NAME/` через SFTP/SCP (виключаючи SETUP.md, README.md, CLAUDE.md, .git, `__pycache__`).

### A5 — Крок 5–12 такі ж як у розділі СПІЛЬНІ КРОКИ нижче

Директорія агента: `/opt/AGENT_NAME`
Запуск від: `claudebot`
Start команда: `sudo -u claudebot bash /opt/AGENT_NAME/start.sh`

---

## ВАРІАНТ B — Розгортання локально (Mac / Linux)

### Збери дані (одним повідомленням):

1. **Назва агента** (slug, лише малі літери і дефіс, напр. `my-agent`)
2. **Telegram Bot Token** — від @BotFather
3. **Telegram Owner ID** — числовий ID (@userinfobot)
4. **Часовий пояс** — напр. `Europe/Kyiv`
5. **Claude Code OAuth Token** — запустити: `claude setup-token` (потрібна підписка Pro/Max)
6. **Опис агента / persona** — хто цей агент (кілька речень)

### B1 — Перевір та встанови залежності

```bash
# Перевірити що є
which tmux   || { echo "Встанови tmux: brew install tmux (Mac) або sudo apt install tmux (Linux)"; exit 1; }
which python3 || { echo "Python3 не знайдено"; exit 1; }

# bun
which bun 2>/dev/null || ~/.bun/bin/bun --version 2>/dev/null || \
  curl -fsSL https://bun.sh/install | bash

# Claude Code
~/.bun/bin/bun install -g @anthropic-ai/claude-code 2>/dev/null || true
which claude || ~/.bun/bin/claude --version
```

### B2 — Створи директорію агента

Директорія: `~/AGENT_NAME` (тобто `/Users/username/AGENT_NAME` або `/home/username/AGENT_NAME`)

```bash
mkdir -p ~/AGENT_NAME
```

Скопіюй усі файли з поточної директорії в `~/AGENT_NAME/` (виключаючи SETUP.md, README.md, CLAUDE.md, .git, `__pycache__`).

### B3 — Кроки 5–12 з розділу СПІЛЬНІ КРОКИ нижче

Директорія агента: `~/AGENT_NAME`
Запуск від: поточного користувача (без sudo)
Start команда: `bash ~/AGENT_NAME/start.sh`

---

## СПІЛЬНІ КРОКИ (виконуй після A4 або B2)

Нижче AGENT_DIR = `/opt/AGENT_NAME` (VPS) або `~/AGENT_NAME` (локально).

### Крок 5 — Заміни плейсхолдери у всіх файлах

Визнач AGENT_DIR:
- VPS: `AGENT_DIR=/opt/AGENT_NAME`
- Локально: `AGENT_DIR=$HOME/AGENT_NAME`

```bash
cd AGENT_DIR

# Заміни всі плейсхолдери — AGENT_NAME, TIMEZONE і /opt/-шляхи
for f in \
  start.sh.tmpl \
  .claude/CLAUDE.md.tmpl \
  .claude/settings.json.tmpl \
  persona/SOUL.md.tmpl \
  persona/MEMORY.md.tmpl \
  skills/index_skills.yaml \
  personas/default.md personas/shared.md personas/role.py \
  background_tasks/tasks.json hooks/context_injector.py; do
  [ -f "$f" ] || continue
  # macOS: sed -i ''    Linux: sed -i
  sed -i'' -e "s|{{AGENT_NAME}}|AGENT_NAME|g" \
           -e "s|{{AGENT_TIMEZONE}}|TIMEZONE|g" \
           -e "s|/opt/AGENT_NAME|AGENT_DIR|g" \
           -e "s|/home/claudebot|$HOME|g" \
      "$f" 2>/dev/null || true
done

# Перейменуй усі .tmpl файли (прибирає суфікс .tmpl)
for f in start.sh.tmpl .claude/CLAUDE.md.tmpl .claude/settings.json.tmpl \
          persona/SOUL.md.tmpl persona/MEMORY.md.tmpl; do
  [ -f "$f" ] && mv "$f" "${f%.tmpl}"
done
chmod +x start.sh

# Контрольна перевірка — не має нічого повернути
grep -rn "{{AGENT" . 2>/dev/null | grep -v ".env" && echo "⚠ Залишились плейсхолдери!" || echo "✅ Плейсхолдери чисті"
grep -rn "/opt/AGENT_NAME" . 2>/dev/null | grep -v ".env.example" && echo "⚠ Залишились /opt/-шляхи!" || echo "✅ Шляхи чисті"
```

Створи `AGENT_DIR/.env`:
```
AGENT_NAME=AGENT_NAME
AGENT_TIMEZONE=TIMEZONE

TELEGRAM_BOT_TOKEN=BOT_TOKEN
TELEGRAM_OWNER_ID=OWNER_ID
TELEGRAM_ALLOWED_CHATS=

CLAUDE_CODE_OAUTH_TOKEN=OAUTH_TOKEN

MEMEPALACE_URL=http://localhost:7766
# Шлях до messages.db агента (ізольований від глобального ~/.claude)
MEMPALACE_DB=AGENT_DIR/.claude/channels/telegram/messages.db

GOG_KEYRING_PASSWORD=GENERATED_PASSWORD

GROQ_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
PERPLEXITY_API_KEY=
VAPI_API_KEY=
NOTEBOOKLM_STORAGE_STATE_B64=
```

### Крок 6 — Налаштуй persona

Запиши persona в `AGENT_DIR/persona/SOUL.md` на основі опису від користувача.
Ініціалізуй `AGENT_DIR/persona/MEMORY.md`.

### Крок 7 — Встанови Python venv

```bash
cd AGENT_DIR
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
```

### Крок 8 — Налаштуй Claude credentials

```python
import json, os

agent_dir = "AGENT_DIR"  # замінити на реальний шлях
claude_dir = f"{agent_dir}/.claude"
os.makedirs(claude_dir, exist_ok=True)

claude_json = {
    "hasCompletedOnboarding": True,
    "projects": {
        agent_dir: {
            "allowedTools": [],
            "hasTrustDialogAccepted": True,
            "projectOnboardingSeenCount": 1,
        }
    }
}
with open(f"{agent_dir}/.claude.json", "w") as f:
    json.dump(claude_json, f, indent=2)

creds = {
    "claudeAiOauth": {
        "accessToken": "OAUTH_TOKEN",
        "refreshToken": "",
        "expiresAt": 9999999999999,
        "scopes": ["user:inference", "user:profile", "user:sessions:claude_code"],
        "subscriptionType": "pro",
        "rateLimitTier": "default_claude_ai"
    }
}
with open(f"{claude_dir}/.credentials.json", "w") as f:
    json.dump(creds, f, indent=2)
os.chmod(f"{claude_dir}/.credentials.json", 0o600)
```

На VPS: `chown -R claudebot:claudebot /opt/AGENT_NAME/.claude*`

### Крок 9 — Встанови та запатчи Telegram plugin

```bash
export HOME=AGENT_DIR
export PATH=$HOME/.bun/bin:~/.bun/bin:$PATH

# Крок 9a: Встановити плагін (--channels лише підключає, але не встановлює)
claude plugin install telegram@claude-plugins-official 2>/dev/null || \
  claude --dangerously-skip-permissions --print "/plugin install telegram@claude-plugins-official" 2>/dev/null || true

# Перевір що встановився
ls $HOME/.claude/plugins/cache/claude-plugins-official/telegram/ 2>/dev/null \
  && echo "✅ Plugin installed" || echo "⚠ Plugin not found — спробуй вручну"

# Крок 9b: Запустити патчер з .env (потрібен TELEGRAM_OWNER_ID для access.json)
set -a && source AGENT_DIR/.env && set +a
python3 AGENT_DIR/patches/telegram_plugin.py

# Перевір що access.json створився
cat $HOME/.claude/channels/telegram/access.json 2>/dev/null | grep dmPolicy \
  && echo "✅ access.json OK" || echo "⚠ access.json не створився"
```

### Крок 10 — Запусти агента

**VPS:** `sudo -u claudebot bash /opt/AGENT_NAME/start.sh`
**Локально:** `bash ~/AGENT_NAME/start.sh`

Зачекай 15 секунд, перевір tmux:
```bash
tmux ls
```

### Крок 11 — Верифікація

```bash
tmux capture-pane -t AGENT_NAME -p 2>/dev/null | tail -5
```

Якщо Claude запустився — повідом користувача:
> ✅ Агент **AGENT_NAME** запущено.
> Напиши будь-яке повідомлення боту в Telegram — він має відповісти протягом 30 секунд.
> Підключитись до сесії: `tmux attach -t AGENT_NAME`

---

## Примітки

- **MemPalace** — семантична пам'ять, стартує автоматично. Розробка EightGate.
- **Google-скіли** — потребують OAuth-додатку. Інструкція: `skills/google_calendar/SETUP.md`
- **VAPI дзвінки** — акаунт на vapi.ai, ключ `VAPI_API_KEY` в `.env`
- **Голос** — `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID` в `.env`
