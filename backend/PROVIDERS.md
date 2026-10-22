# Настройка ИИ-провайдера

Проект использует OpenAI API. Все вызовы ИИ проходят через `backend/ai_client.py`, поэтому маршруты приложения не зависят напрямую от SDK.

## Настройка

1. Создайте API-ключ в панели OpenAI: https://platform.openai.com/api-keys
2. Скопируйте `backend/.env.example` в `backend/.env`.
3. Укажите `OPENAI_API_KEY`.
4. При необходимости задайте `OPENAI_MODEL` (по умолчанию `gpt-4.1-mini`).
5. Установите зависимости заново: `pip install -r backend/requirements.txt`.

Ключ хранится только на backend. Не добавляйте `.env` в Git и не помещайте секретный ключ во frontend.

## Контракт клиента

- `generate(prompt, max_tokens, timeout)` — синхронная генерация текста.
- `stream_text(system, messages, max_tokens)` — асинхронная потоковая генерация.
- `AITimeoutError` — тайм-аут провайдера.
- `AINotConfiguredError` — отсутствует `OPENAI_API_KEY`.

Для русскоязычного интерфейса системные инструкции и инструкции оценки ответов должны требовать русский язык. Команды, код, идентификаторы API и стандартные технические термины сохраняются в оригинальном написании.
