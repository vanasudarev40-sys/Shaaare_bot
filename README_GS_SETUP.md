Как быстро проверить интеграцию Google Sheets для этого бота

1) Получите ID таблицы (из URL между /d/ и /edit). Пример: `1puzIf0-...`

2) Создайте сервисный аккаунт в Google Cloud и скачайте JSON-ключ.

3) Поделитесь вашей таблицей (Share) с `client_email` из JSON (право Editor).

4) Установите переменные окружения (PowerShell):

```powershell
#$ Вариант A: передаём путь к файлу с ключом
$env:GOOGLE_APPLICATION_CREDENTIALS = 'C:\path\to\gs_creds.json'
$env:GSHEET_ID = 'ВАШ_SPREADSHEET_ID'
# Запуск теста
python test_gs.py
```

```powershell
#$ Вариант B: передаём JSON целиком в переменную окружения
$env:GS_CREDS_JSON = Get-Content 'C:\path\to\gs_creds.json' -Raw
$env:GSHEET_ID = 'ВАШ_SPREADSHEET_ID'
python test_gs.py
```

5) `test_gs.py` попробует открыть таблицу, создать лист `Test` (если его нет) и добавить строку. В консоли будет вывод об успехе или ошибке.

6) Если тест успешен, запустите `bot.py` с теми же переменными окружения — бот будет автоматически пытаться добавлять записи в листы `Bookings` и `Messages`.

7) В Render (если используете) добавьте переменные `GSHEET_ID` и `GS_CREDS_JSON` (или другой способ хранения ключа). Render не даёт загружать файлы напрямую, поэтому `GS_CREDS_JSON` удобнее — просто вставьте содержимое JSON в секрет.

Если хотите, могу подготовить и выполнить коммит с этими файлами и сформировать команды Git для PowerShell.
