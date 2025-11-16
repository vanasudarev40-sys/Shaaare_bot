# Telegram Booking Bot

Этот репозиторий содержит простой Telegram-бот для записи к специалистам, с админ-панелью и уведомлениями.

Что добавлено/подготовлено для деплоя:
- `requirements.txt` — зависимости
- `Dockerfile` — сборка контейнера
- `.env.example` — пример переменных окружения
- `bot.py` читаeт `TOKEN` из переменных окружения (с fallback)

Быстрый запуск локально

1. Создайте виртуальное окружение и установите зависимости:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Создайте `.env` (или установите переменную окружения `TOKEN`):

```text
TOKEN=ваш_токен_бота
DATA_FILE=data.json
```

3. Запустите бота:

```powershell
python .\bot.py
```

Docker (локально)

```powershell
docker build -t telegram-booking-bot .
docker run -d --restart unless-stopped -e TOKEN="ваш_токен" -v ${PWD}:/app telegram-booking-bot
```

Деплой на Render (рекомендация для 24/7)

1. Создайте репозиторий на GitHub и загрузите проект.
2. Зарегистрируйтесь на https://render.com и подключите репозиторий.
3. Создайте новый Background Worker или Web Service (Background Worker предпочтительнее для процесса, неслушающего HTTP).
4. В разделе Environment укажите переменную `TOKEN` (значение — ваш токен).
5. Build Command: `pip install -r requirements.txt`
6. Start Command: `python bot.py`

Render будет автоматически держать процесс живым и перезапускать при падении.

Если нужна помощь с деплоем на Render/Railway или настройкой GitHub Actions — напишите, помогу настроить шаги и добавлю пример workflow.
