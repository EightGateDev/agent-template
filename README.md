# EightGate Agent Template

> Повністю готовий шаблон персонального AI-агента на базі Claude Code.
> Розроблено командою **[EightGate](https://eightgate.ai)**.

---

## Що це

Шаблон для розгортання персонального Claude-агента на VPS-сервері з підтримкою:

- 💬 **Telegram** — агент спілкується через ваш бот
- 🧠 **Багатошарова пам'ять** — короткострокова (SQLite), довгострокова (MEMORY.md), семантичний пошук (MemPalace)
- 📅 **Google-інтеграції** — Calendar, Gmail, Docs, Sheets
- 🎙️ **Голос** — розпізнавання (Groq Whisper) та синтез мовлення (ElevenLabs)
- 📞 **Дзвінки** — через Vapi
- 🖼️ **Генерація зображень** — Gemini Imagen
- ⏰ **Фонові задачі** — планувальник і нагадування

## Розгортання

Відкрий цю папку в **Claude Code** — він прочитає `SETUP.md` і розгорне агента автоматично.

Що потрібно мати:
- VPS (Ubuntu 22.04+) з SSH-доступом
- Telegram-бот від @BotFather
- Claude Code OAuth токен — отримати командою `claude setup-token` в терміналі

## Структура

```
├── SETUP.md                ← інструкція для Claude Code (головний файл)
├── start.sh.tmpl           ← самовідновлювальний цикл запуску
├── .claude/
│   ├── CLAUDE.md.tmpl      ← правила агента
│   └── settings.json.tmpl  ← дозволи і хуки
├── persona/
│   ├── SOUL.md.tmpl        ← характер і особистість
│   └── MEMORY.md.tmpl      ← пам'ять про власника
├── personas/               ← спеціалізовані персони
├── hooks/
│   └── context_injector.py ← авто-ін'єкція контексту
├── skills/                 ← набір скілів
│   ├── google_calendar/
│   ├── google_gmail/
│   ├── google_docs/
│   ├── google_sheets/
│   ├── tg_voice_input/
│   ├── tg_voice_output/
│   ├── phone_call/
│   ├── nanobanana/
│   ├── schedule_task/
│   ├── tg_file_reader/
│   ├── read_messages/
│   └── mempalace_query/
├── background_tasks/       ← планувальник задач
├── patches/
│   └── telegram_plugin.py  ← патч Telegram-плагіну
└── mempalace_server.py     ← локальний сервер семантичної пам'яті
```

## MemPalace — Семантична пам'ять

**MemPalace** — розробка EightGate. Локальний HTTP-сервер (порт 7766) що індексує всю переписку агента і забезпечує семантичний пошук по контексту.

Архітектура пам'яті трирівнева:
1. **SQLite** — повна історія повідомлень (авто-читається перед кожною відповіддю)
2. **MEMORY.md** — довгострокові факти про власника
3. **MemPalace** — семантичний пошук по контексту розмов

Стартує автоматично разом з агентом. Не потребує зовнішніх API.

## Google-скіли

Потребують OAuth-додатку від Google. Детальна інструкція: `skills/google_calendar/SETUP.md`

## Підтримка

Розроблено і підтримується командою **EightGate**.
Питання та замовлення агентів: [eightgate.ai](https://eightgate.ai)
