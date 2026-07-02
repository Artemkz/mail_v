# Mail Client Server

Сервер почтового клиента на FastAPI с поддержкой IMAP и веб-интерфейсом.

## Возможности

- **Авторизация** — вход по логину и паролю, защита API и веб-интерфейса
- **Веб-интерфейс** — почтовый клиент в браузере на http://localhost:8000
- **IMAP** — подключение внешних почтовых ящиков и загрузка писем
- **Сборщик** — автоматический сбор с нескольких ящиков (фоновый процесс каждые 5 минут + ручной запуск)
- **Поиск** — по первым 3 символам каждого слова в теме, теле, email и имени отправителя
- **Автопапки** — если от отправителя больше 1 письма, создаётся папка и все его письма перемещаются туда

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Запуск

```bash
python run.py
```

API: http://localhost:8000/docs  
Веб-интерфейс: http://localhost:8000  
Логин по умолчанию: `admin` / `admin` (задаётся в `.env`)

## Авторизация

Скопируйте `.env.example` в `.env` и задайте:

```env
APP_USERNAME=admin
APP_PASSWORD=your-secure-password
SECRET_KEY=long-random-secret
COOKIE_PATH=/mail
```

Для локального запуска используйте `COOKIE_PATH=/`.

## Примеры

### Добавить ящик

```bash
curl -X POST http://localhost:8000/api/mailboxes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Gmail",
    "email": "user@gmail.com",
    "imap_host": "imap.gmail.com",
    "imap_port": 993,
    "username": "user@gmail.com",
    "password": "app-password",
    "source_folder": "INBOX"
  }'
```

### Собрать письма

```bash
curl -X POST "http://localhost:8000/api/collect"
```

### Поиск (минимум 3 символа на слово)

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "счет оплата"}'
```

### Список папок по отправителям

```bash
curl http://localhost:8000/api/folders
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `SEARCH_PREFIX_LENGTH` | 3 | Длина префикса для поиска |
| `COLLECTOR_INTERVAL_SECONDS` | 300 | Интервал фонового сборщика |
| `DATABASE_URL` | sqlite+aiosqlite:///./mail_client.db | URL базы данных |
| `APP_USERNAME` | admin | Логин для входа |
| `APP_PASSWORD` | admin | Пароль для входа |
| `SECRET_KEY` | change-me-in-production | Секрет для JWT |
| `COOKIE_PATH` | / | Путь cookie (на сервере: `/mail`) |
