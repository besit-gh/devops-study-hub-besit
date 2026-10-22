---
title: Cloud Functions
module: gcp
duration_min: 20
difficulty: intermediate
tags: [gcp, cloud-functions, serverless, triggers, pubsub, eventarc, python, gcloud]
exercises: 4
---

## Обзор
Cloud Functions — serverless-платформа функций в GCP. Функции второго поколения (теперь это вариант по умолчанию) работают на базе Cloud Run, обеспечивая более длительные тайм-ауты (до 60 минут), большую параллельность (до 1000 одновременных запросов на экземпляр) и больший объём памяти. Модель программирования похожа на Lambda: напишите обработчик, настройте триггер и выполните развёртывание. Поскольку Cloud Functions 2nd gen работает поверх Cloud Run, для более тонкого контроля можно использовать Cloud Run напрямую.

## Основные понятия

### Типы функций
```
HTTP functions   — invoked by HTTP requests (GET, POST, etc.)
Event functions  — triggered by Pub/Sub, Cloud Storage, Eventarc, Firestore
```

### HTTP-функция на Python
```python
# main.py
import functions_framework
import json

@functions_framework.http
def hello_http(request):
    """HTTP Cloud Function."""
    request_json = request.get_json(silent=True)
    name = request_json.get('name', 'World') if request_json else 'World'
    return json.dumps({'message': f'Hello, {name}!'})
```

```
# requirements.txt
functions-framework==3.*
```

```bash
# Локальное тестирование
functions-framework --target hello_http --debug

# Развернуть функцию второго поколения
gcloud functions deploy hello-http \
  --gen2 \
  --runtime python312 \
  --region us-central1 \
  --source . \
  --entry-point hello_http \
  --trigger-http \
  --allow-unauthenticated \
  --memory 256Mi \
  --timeout 60s \
  --min-instances 0 \
  --max-instances 10

# Вызвать функцию
gcloud functions call hello-http \
  --region us-central1 \
  --data '{"name": "Alice"}'
```

### Функция, запускаемая событием Pub/Sub
```python
import functions_framework
import base64
import json

@functions_framework.cloud_event
def process_message(cloud_event):
    """Triggered by a Pub/Sub message."""
    # Данные сообщения Pub/Sub закодированы в Base64
    data = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
    message = json.loads(data)
    print(f"Processing: {message}")
    # Вернуть None (функции Pub/Sub не возвращают ответ)
```

```bash
# Развернуть функцию с триггером Pub/Sub
gcloud functions deploy process-message \
  --gen2 \
  --runtime python312 \
  --region us-central1 \
  --source . \
  --entry-point process_message \
  --trigger-topic my-topic \
  --memory 512Mi

# Отправить тестовое сообщение
gcloud pubsub topics publish my-topic \
  --message '{"key": "value"}'
```

### Функция, запускаемая событием Cloud Storage
```python
import functions_framework
from google.cloud import storage

@functions_framework.cloud_event
def on_file_upload(cloud_event):
    """Triggered when a file is uploaded to GCS."""
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]

    print(f"File uploaded: gs://{bucket_name}/{file_name}")

    # Обработать файл
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    content = blob.download_as_text()
    # ...
```

```bash
# Развернуть функцию с триггером Cloud Storage через Eventarc
gcloud functions deploy on-file-upload \
  --gen2 \
  --runtime python312 \
  --region us-central1 \
  --source . \
  --entry-point on_file_upload \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=my-trigger-bucket" \
  --trigger-location us-central1
```

### Переменные окружения и секреты
```bash
# Задать переменные окружения при развёртывании
gcloud functions deploy myfunction \
  --set-env-vars API_URL=https://api.example.com,APP_ENV=production

# Подключить секреты Secret Manager (рекомендуется для чувствительных данных)
gcloud functions deploy myfunction \
  --set-secrets DB_PASSWORD=projects/my-project/secrets/db-password:latest
```

```python
import os
import functions_framework

@functions_framework.http
def handler(request):
    api_url = os.environ['API_URL']
    db_password = os.environ['DB_PASSWORD']   # injected from Secret Manager
```

### Сервисные аккаунты и IAM
```bash
# Развернуть с определённым сервисным аккаунтом
gcloud functions deploy myfunction \
  --service-account myfunction-sa@my-project.iam.gserviceaccount.com \
  ...

# Предоставить сервисному аккаунту функции доступ к GCS
gcloud projects add-iam-policy-binding my-project \
  --member serviceAccount:myfunction-sa@my-project.iam.gserviceaccount.com \
  --role roles/storage.objectAdmin
```

### HTTP-функции с аутентификацией
```bash
# Deploy without --allow-unauthenticated (requires Identity Token to call)
gcloud functions deploy secure-function \
  --gen2 \
  --runtime python312 \
  --trigger-http
  # no --allow-unauthenticated

# Вызвать с identity token
TOKEN=$(gcloud auth print-identity-token)
curl -H "Authorization: Bearer $TOKEN" \
  https://us-central1-my-project.cloudfunctions.net/secure-function
```

### Параллельная обработка (только 2-е поколение)
```bash
# 2nd gen: one instance can handle multiple requests simultaneously
gcloud functions deploy myfunction \
  --gen2 \
  --concurrency 80 \
  --cpu 1 \
  --memory 512Mi
```

В отличие от Lambda, где один экземпляр обрабатывает один запрос за раз, функции второго поколения могут обрабатывать несколько запросов параллельно на одном экземпляре. При умеренной нагрузке это значительно сокращает количество холодных запусков.

### Журналы и мониторинг
```bash
# Просмотреть журналы функции
gcloud functions logs read hello-http \
  --region us-central1 \
  --limit 50

# Следить за журналами в реальном времени
gcloud functions logs read hello-http \
  --region us-central1 \
  --limit 50 \
  --format json | jq '.[]'

# Просмотреть через gcloud logging
gcloud logging read 'resource.type=cloud_function AND resource.labels.function_name=hello-http' \
  --limit 20 \
  --format 'value(timestamp, textPayload)'
```

### Локальная разработка
```bash
# Установить Functions Framework
pip install functions-framework

# Локально протестировать HTTP-функцию
functions-framework --target hello_http --port 8080

# Отправить тестовый запрос
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{"name": "test"}'

# Локально протестировать функцию обработки событий
functions-framework --target process_message \
  --signature-type cloudevent
```

## Примеры

### Конвейер обработки изображений
```python
# main.py — запускается при загрузке изображения в исходный бакет
import functions_framework
from google.cloud import storage
from PIL import Image
import io

@functions_framework.cloud_event
def resize_image(cloud_event):
    data = cloud_event.data
    source_bucket = data["bucket"]
    source_blob = data["name"]

    if not source_blob.lower().endswith(('.jpg', '.jpeg', '.png')):
        return

    client = storage.Client()
    src = client.bucket(source_bucket).blob(source_blob)
    img_bytes = src.download_as_bytes()

    img = Image.open(io.BytesIO(img_bytes))
    img.thumbnail((800, 800))

    output = io.BytesIO()
    img.save(output, format=img.format)
    output.seek(0)

    dest_bucket = client.bucket('my-processed-images')
    dest_bucket.blob(source_blob).upload_from_file(output, content_type=src.content_type)
    print(f"Resized {source_blob}")
```

## Практические задания

1. Напишите и разверните HTTP Cloud Function второго поколения на Python, которая принимает JSON с полем `text` и возвращает перевёрнутую строку. Проверьте её через `gcloud functions call` и `curl`.
2. Создайте тему Pub/Sub и разверните Cloud Function, запускаемую сообщениями этой темы. Функция должна записывать декодированное содержимое сообщения в журнал. Опубликуйте пять тестовых сообщений и проверьте, что все они появились в журнале функции.
3. Разверните функцию, запускаемую событиями Cloud Storage, которая записывает в журнал имя и размер каждого файла, загруженного в заданный бакет. Загрузите несколько файлов и проверьте журналы.
4. Разверните защищённую HTTP-функцию, требующую аутентификацию. Напишите скрипт Python, который вызывает её с действительным токеном идентификации, полученным через `gcloud auth print-identity-token`. Убедитесь, что тот же URL возвращает 403 без токена.


---

### Быстрая проверка

5. Извлеките тип триггера из примера конфигурации Cloud Function. Выполните: `printf 'trigger:\n  type: http\n  allowUnauthenticated: true\n' | awk '/^  type:/{print $2}'`

```expected_output
http
```

Подсказка: найдите нужную строку в структурированном тексте по шаблону и извлеките определённое поле.
Подсказка: используйте `awk` с шаблоном `/^  type:/`, чтобы найти строку `type:` с отступом, а затем выведите второе поле через `{print $2}`.

6. Переведите максимальный тайм-аут функции (9 минут) в секунды. Выполните: `python3 -c "print(9 * 60)"`

```expected_output
540
```

Подсказка: используйте параметр Python для выполнения короткого арифметического выражения прямо в терминале.
Подсказка: используйте `python3 -c` и `print`, чтобы перемножить два целых числа оператором `*`.
