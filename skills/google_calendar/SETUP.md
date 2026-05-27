# Google (Calendar + Gmail + Docs + Sheets) — setup protocol

OAuth клиент уже установлен на сервере. НЕ проси пользователя создавать
OAuth client, скачивать JSON или что-то настраивать в Google Cloud Console.
От пользователя нужны только ДВЕ вещи: email и redirect URL после авторизации.

## Шаг 1 — Проверка (Discovery)

Запусти через bash_exec:

```bash
gog auth list 2>/dev/null || true
```

Если показывает аккаунт с gmail и calendar:
- Проверь: `gog calendar list --account <email>`
- Если работает — скажи пользователю: "Google подключён, аккаунт <email>."
- Если токен протух — переходи к Шагу 2.
- Вызови `link_google_account` с email.

Если аккаунтов нет — переходи к Шагу 2.

## Шаг 2 — Спроси email

Спроси у пользователя: "Какой Gmail подключаем?"

Дождись ответа с email.

## Шаг 3 — Авторизация (remote flow)

**3a** — Запусти авторизацию:

```bash
gog auth add <email> --services gmail,calendar,docs,sheets,drive --remote --step 1
```

Из вывода достань URL (начинается с `https://accounts.google.com/...`).
Отправь его пользователю как кликабельную ссылку:

"Открой ссылку, войди в Google и разреши доступ.
После этого тебя перекинет на страницу, которая не откроется — это нормально.
Скопируй полный URL из адресной строки браузера и пришли его мне сюда."

**Жди пока пользователь пришлёт redirect URL.**

**3b** — Обмен кода на токен:

```bash
gog auth add <email> --services gmail,calendar,docs,sheets,drive --remote --step 2 --auth-url "<pasted_url>"
```

Проверь:

```bash
gog auth list
```

**3c** — Привязка аккаунта:

Вызови `link_google_account` с email пользователя.
Скажи: "Google подключён."

## Ошибки

- "invalid state" / "code already used" — код одноразовый, начни с Шага 3a заново
- "invalid_client" — проблема с OAuth клиентом на сервере, сообщи администратору
- "no TTY available for keyring" — нужен GOG_KEYRING_PASSWORD в окружении

## Важные правила

- НИКОГДА не проси пользователя создавать OAuth client в Google Cloud
- НИКОГДА не проси пользователя скачивать или присылать JSON файл
- НИКОГДА не упоминай gog, OAuth, tokens, JSON, credentials в сообщениях
- Говори простым языком: "открой ссылку", "пришли URL", "Google подключён"
