---
title: AWS Lambda
module: aws
duration_min: 25
difficulty: intermediate
tags: [aws, lambda, serverless, functions, triggers, layers, api-gateway, sam]
exercises: 4
---

## Обзор

AWS Lambda — serverless-сервис вычислений, запускающий код в ответ на события и автоматически управляющий инфраструктурой. Для DevOps он позволяет не заниматься подготовкой, обновлением и масштабированием серверов для событийных или периодических задач. Оплата начисляется только за использованное время вычислений (с шагом в 1 мс), что выгодно для задач, ради которых иначе пришлось бы держать EC2 постоянно включёнными. Автоматическое масштабирование Lambda — от нуля до тысяч параллельных запусков за секунды — снимает значительную часть задач планирования мощности.

Архитектура Lambda основана на трёх принципах: отсутствие состояния (каждый вызов независим, общей памяти между вызовами нет), событийное выполнение (Lambda реагирует на триггеры десятков сервисов AWS) и временные вычислительные окружения (они создаются и удаляются автоматически). Поэтому состояние кэшируют во внешних хранилищах вроде DynamoDB или ElastiCache, код проектируют с учётом идемпотентных повторных запусков, а пакеты делают небольшими, чтобы уменьшить задержку холодного старта. Понимание этих ограничений заранее помогает избежать ошибок, проявляющихся только под production-нагрузкой.

В DevOps-стеке Lambda выполняет сразу несколько ролей: связывает сервисы AWS (S3 → Lambda → DynamoDB), обслуживает HTTP-эндпоинты API Gateway, обрабатывает очереди SQS и потоки Kinesis, запускает задачи по расписанию через EventBridge и выполняет автоматизацию инфраструктуры — ротацию секретов, контроль соответствия требованиям и реакцию на сигналы CloudWatch. Освоить Lambda — значит понимать не только саму функцию, но и событийную инфраструктуру, на которой построен AWS.

## Основные понятия

### Устройство функции

Каждая функция Lambda получает два аргумента: `event` и `context`. `event` содержит данные триггера, структура которых зависит от источника (S3, SQS, API Gateway и т. д.). Объект `context` предоставляет метаданные выполнения: ID запроса, имя функции, оставшееся время выполнения и поток журналов CloudWatch для этого вызова.

```python
# handler.py
import json
import os
import boto3

def handler(event, context):
    """
    event   — the trigger payload (dict); shape varies by trigger source
    context — runtime info: function name, remaining time, request ID, log stream
    """
    print(f"Request ID: {context.aws_request_id}")
    print(f"Function name: {context.function_name}")
    print(f"Remaining time: {context.get_remaining_time_in_millis()}ms")
    print(f"Log stream: {context.log_stream_name}")
    print(f"Event: {json.dumps(event)}")

    bucket = os.environ['BUCKET_NAME']
    key = event.get('key', 'default')

    s3 = boto3.client('s3')
    obj = s3.get_object(Bucket=bucket, Key=key)
    content = obj['Body'].read().decode('utf-8')

    return {
        'statusCode': 200,
        'body': json.dumps({'content': content})
    }
```

**Формат возвращаемого значения:** для интеграции с API Gateway верните словарь с `statusCode`, `headers` и `body`. Для триггеров SQS верните список `batchItemFailures`. Для S3, SNS и EventBridge возвращаемое значение игнорируется — важны побочные эффекты. Неверная структура ответа для API Gateway приводит к `502 Bad Gateway` без понятного сообщения, поэтому всегда проверяйте формат ответа.

**Код на уровне модуля выполняется один раз на вычислительное окружение, а не при каждом вызове.** Окружения повторно используются, пока не будут пересозданы (обычно после нескольких минут или часов бездействия). Используйте это для кэширования SDK-клиентов, разбора конфигурации и установки соединений вне обработчика.

```python
# Good: SDK client and table reference created once, reused across warm invocations
import boto3, os

s3 = boto3.client('s3')
db = boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])

def handler(event, context):
    # s3 and db are already initialized — no per-invocation overhead
    ...
```

### Настройка runtime и памяти

| Runtime | Холодный старт (обычно) | Примечания |
|---------|---------------------|-------|
| Python 3.12 | 100–300 мс | Быстрый runtime с развитой экосистемой |
| Node.js 20.x | 100–250 мс | Один из самых быстрых для небольших функций |
| Java 21 (SnapStart) | 1–3 с (200 мс с SnapStart) | Прогрев JVM дорогой; SnapStart сохраняет снимок инициализированного состояния |
| .NET 8 | 300 мс – 1 с | AOT-компиляция существенно сокращает холодный старт |
| Go (provided.al2023) | 50–150 мс | Скомпилированный бинарник, минимальные накладные расходы |
| Образ контейнера | 1–5 с | Зависит от размера образа; используйте slim-образы |

Память — **главный параметр настройки производительности**. Lambda выделяет CPU пропорционально объёму памяти: при 1769 МБ доступно ровно одно vCPU, при 3538 МБ — два. Для задач, ограниченных CPU, увеличение памяти часто настолько сокращает длительность выполнения, что общая стоимость снижается, хотя цена за ГБ-секунду остаётся постоянной.

```bash
# Update memory and test billed duration at multiple settings
# Try 128, 256, 512, 1024 and compare cost = (billed_ms / 1000) * (memory_gb) * $0.0000166667
aws lambda update-function-configuration \
  --function-name myapp-processor \
  --memory-size 512

# AWS Lambda Power Tuning (open source Step Functions state machine) automates this
# https://github.com/alexcasalboni/aws-lambda-power-tuning
```

**Настройка тайм-аута:** по умолчанию он равен 3 секундам, максимум — 900 секунд (15 минут). Устанавливайте значение немного выше 99-го перцентиля фактической длительности: слишком большой тайм-аут увеличивает стоимость при зависании на сетевом вводе-выводе. Всегда задавайте тайм-аут явно — значение по умолчанию может незаметно завершить функцию, ожидающую медленный внешний сервис.

**Хранилище `/tmp`:** по умолчанию Lambda предоставляет 512 МБ временного пространства `/tmp` (можно увеличить до 10 ГБ). Данные сохраняются между вызовами в тёплом окружении, но не разделяются между параллельными экземплярами и исчезают при пересоздании окружения. Используйте `/tmp` для кэширования загруженных файлов внутри одного окружения, но не для постоянного хранения.

### Развёртывание через AWS CLI

Процесс развёртывания: упаковать код → создать или обновить функцию → проверить результат. В production используйте SAM или Terraform, но понимание базового процесса через CLI необходимо для отладки и скриптов.

```bash
# Package handler and any local modules into a ZIP
zip function.zip handler.py utils.py

# Create function (first deploy)
aws lambda create-function \
  --function-name myapp-processor \
  --runtime python3.12 \
  --handler handler.handler \           # filename.function_name
  --role arn:aws:iam::123456789012:role/lambda-execution-role \
  --zip-file fileb://function.zip \
  --timeout 30 \
  --memory-size 256 \
  --environment Variables='{BUCKET_NAME=my-bucket,ENV=production}'

# Update code only (subsequent deploys)
aws lambda update-function-code \
  --function-name myapp-processor \
  --zip-file fileb://function.zip

# Update configuration separately — code and config are independent operations
aws lambda update-function-configuration \
  --function-name myapp-processor \
  --timeout 60 \
  --memory-size 512

# Invoke synchronously and capture the response payload
aws lambda invoke \
  --function-name myapp-processor \
  --payload '{"key": "test.txt"}' \
  --cli-binary-format raw-in-base64-out \
  output.json

cat output.json

# Invoke with log tail — returns last 4KB of logs, base64-encoded
aws lambda invoke \
  --function-name myapp-processor \
  --payload '{"key": "test.txt"}' \
  --cli-binary-format raw-in-base64-out \
  --log-type Tail \
  output.json | jq -r '.LogResult' | base64 -d
```

**Особенность ошибки вызова:** `aws lambda invoke` возвращает код 0 даже при необработанном исключении функции. HTTP-статус будет 200, но в теле ответа появится `"FunctionError": "Unhandled"`. Всегда проверяйте `output.json` и поле `FunctionError` в CI, иначе неудачный вызов может выглядеть как успешный.

```bash
# In CI: fail the pipeline if the function errored
aws lambda invoke --function-name myapp-processor \
  --payload '{"key":"test.txt"}' \
  --cli-binary-format raw-in-base64-out \
  output.json

if jq -e '.FunctionError' output.json > /dev/null 2>&1; then
  echo "Function invocation failed"
  cat output.json
  exit 1
fi
```

### Триггеры

Lambda взаимодействует с сервисами AWS по двум моделям: **push** (источник напрямую вызывает Lambda) и **pull/poll** (Lambda опрашивает источник и вызывает функцию с пакетом записей).

| Триггер | Модель | Повторные попытки | Масштабирование |
|---------|-------|---------------|---------|
| API Gateway / ALB | Push (синхронный) | Повторные попытки выполняет вызывающая сторона | Один параллельный вызов на запрос |
| S3 | Push (асинхронный) | Lambda повторяет дважды, затем DLQ | Для каждого события объекта |
| SNS | Push (асинхронный) | Lambda повторяет дважды, затем DLQ | Для каждого сообщения |
| EventBridge | Push (асинхронный) | Lambda повторяет дважды, затем DLQ | Для каждого совпадения правила |
| SQS (standard) | Pull | При ошибке сообщения возвращаются в очередь; после maxReceiveCount отправляются в DLQ | Масштабируется по длине очереди |
| SQS (FIFO) | Pull | То же; порядок сохраняется внутри MessageGroupId | Ограничено количеством групп сообщений |
| Kinesis / DynamoDB Streams | Pull | Повторяет до успеха или истечения TTL; блокирует shard | По умолчанию один параллельный вызов на shard |

**Повторные попытки при асинхронном вызове:** для источников push-async (S3, SNS, EventBridge) Lambda повторяет вызов дважды при ошибке. Если все три попытки неудачны, событие будет потеряно, если не настроена Dead Letter Queue или назначение событий при сбое. Для асинхронной обработки важных данных всегда настраивайте DLQ.

```bash
# Add a DLQ for async invocation failures
aws lambda update-function-configuration \
  --function-name myapp-processor \
  --dead-letter-config TargetArn=arn:aws:sqs:us-east-1:123456789012:myapp-dlq
```

#### Триггер S3

S3 асинхронно вызывает Lambda при создании, удалении или восстановлении объектов. Payload события содержит массив `Records`; теоретически одно уведомление может содержать несколько записей, но на практике S3 отправляет одну запись на событие.

```bash
# Step 1: grant S3 permission to invoke the function
aws lambda add-permission \
  --function-name myapp-processor \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::my-bucket \
  --source-account 123456789012 \   # prevents confused deputy — always include this
  --statement-id s3-trigger

# Step 2: configure the bucket notification
aws s3api put-bucket-notification-configuration \
  --bucket my-bucket \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [{
      "LambdaFunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:myapp-processor",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [{"Name": "suffix", "Value": ".csv"}]
        }
      }
    }]
  }'
```

**Кодирование ключа:** S3 кодирует имена объектов в URL-формате внутри payload события. Имя `my file.csv` превращается в `my+file.csv`. Перед использованием всегда применяйте `unquote_plus`.

```python
import urllib.parse

def handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])
        size = record['s3']['object']['size']
        print(f"Processing s3://{bucket}/{key} ({size} bytes)")
```

#### Триггер SQS

Lambda опрашивает SQS и вызывает функцию с пакетом сообщений. Это предпочтительный шаблон для надёжной обработки с гарантией доставки как минимум один раз.

```bash
# Create event source mapping
aws lambda create-event-source-mapping \
  --function-name myapp-processor \
  --event-source-arn arn:aws:sqs:us-east-1:123456789012:my-queue \
  --batch-size 10 \
  --maximum-batching-window-in-seconds 5 \      # wait up to 5s to fill a batch
  --function-response-types ReportBatchItemFailures  # partial batch success
```

При использовании `ReportBatchItemFailures` верните список `batchItemFailures` с `messageId` каждого неудачно обработанного сообщения. Lambda удалит успешно обработанные сообщения и повторно поставит в очередь только неудачные.

```python
import json

def handler(event, context):
    failures = []
    for record in event['Records']:
        message_id = record['messageId']
        try:
            body = json.loads(record['body'])
            process_message(body)
        except Exception as e:
            print(f"Failed {message_id}: {e}")
            failures.append({'itemIdentifier': message_id})

    return {'batchItemFailures': failures}
```

**Без `ReportBatchItemFailures`:** если функция вызывает исключение, в очередь возвращается весь пакет, включая успешно обработанные сообщения. Это приводит к дубликатам обработки. Для триггеров SQS всегда включайте частичный успех пакета.

**Масштабирование параллельности SQS:** Lambda увеличивает число параллельных вызовов для обработки очереди — примерно один вызов на 60 сообщений стандартной очереди, до 1000 параллельных вызовов в первые 10 минут. Без ограничения reserved concurrency резкий всплеск очереди может занять весь лимит аккаунта и лишить ресурсов другие функции. Задавайте reserved concurrency для потребителей SQS с высокой нагрузкой.

#### Расписание EventBridge

```bash
# Rate expression: every 5 minutes
aws events put-rule \
  --name every-5-minutes \
  --schedule-expression "rate(5 minutes)"

# Cron expression: 8 AM UTC on weekdays
# aws events put-rule --name weekday-morning --schedule-expression "cron(0 8 ? * MON-FRI *)"

# Add Lambda as target with a static input payload
aws events put-targets \
  --rule every-5-minutes \
  --targets '[{
    "Id": "MyLambda",
    "Arn": "arn:aws:lambda:us-east-1:123456789012:function:myapp-processor",
    "Input": "{\"source\": \"scheduled\"}"
  }]'

# Grant EventBridge permission to invoke
aws lambda add-permission \
  --function-name myapp-processor \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:123456789012:rule/every-5-minutes \
  --statement-id eventbridge-schedule
```

**Синтаксис cron в EventBridge отличается от Unix cron.** Шестое поле — год, а не секунды. В поле дня месяца или дня недели нужно использовать `?`, но не в обоих сразу. `cron(0 8 * * MON-FRI *)` неверно; правильно `cron(0 8 ? * MON-FRI *)`.

### Параллельность и ограничение частоты

| Тип параллельности | Что ограничивает |
|-----------------|-----------------|
| **Лимит аккаунта** | Общее число параллельных вызовов всех функций в регионе (по умолчанию 1000; можно запросить увеличение) |
| **Reserved concurrency** | Максимум параллельных вызовов конкретной функции; учитывается в лимите аккаунта, превышение ограничивается (429) |
| **Provisioned concurrency** | Заранее инициализированные окружения, устраняющие холодный старт; оплачиваются даже без вызовов |

```bash
# Reserve 100 concurrent executions for a critical function
# This also guarantees capacity — no other function can consume these slots
aws lambda put-function-concurrency \
  --function-name myapp-api \
  --reserved-concurrent-executions 100

# Remove reserved concurrency limit (function uses account pool again)
aws lambda delete-function-concurrency \
  --function-name myapp-api

# Enable provisioned concurrency on an alias (for latency-sensitive APIs)
aws lambda put-provisioned-concurrency-config \
  --function-name myapp-api \
  --qualifier prod \           # alias name
  --provisioned-concurrent-executions 10
```

**Поведение при ограничении частоты в зависимости от типа вызова:**
- **Синхронный** (API Gateway, ALB): возвращается HTTP 429. Вызывающая сторона должна повторять запросы с экспоненциальной задержкой.
- **Асинхронный** (S3, SNS, EventBridge): Lambda помещает событие во внутреннюю очередь и повторяет попытки до 6 часов перед отправкой в DLQ.
- **Опрос** (SQS, Kinesis): сообщения остаются в очереди или потоке; Lambda повторяет попытку, когда появляется свободная мощность.

**Установка reserved concurrency в 0** фактически отключает функцию. Это полезно для аварийной остановки неконтролируемой функции без её удаления.

### Переменные окружения и секреты

Переменные окружения подходят для несекретной конфигурации (URL, имена таблиц, feature flags, регион). Для чувствительных значений используйте AWS Secrets Manager или SSM Parameter Store и получайте их при холодном старте.

```python
import os
import boto3
import json

# Module-level cache — fetched once per execution environment
_secret_cache = {}

def get_secret(secret_arn: str) -> dict:
    if secret_arn not in _secret_cache:
        client = boto3.client('secretsmanager')
        response = client.get_secret_value(SecretId=secret_arn)
        _secret_cache[secret_arn] = json.loads(response['SecretString'])
    return _secret_cache[secret_arn]

# Pre-load at cold start — not inside the handler
_db_secret = get_secret(os.environ['DB_SECRET_ARN'])

def handler(event, context):
    api_url = os.environ['API_URL']          # non-sensitive: env var is fine
    db_password = _db_secret['password']     # sensitive: Secrets Manager
```

**Особенность шифрования:** Lambda шифрует переменные окружения в состоянии покоя с помощью KMS (по умолчанию ключом AWS). Однако значения видны в открытом виде в консоли Lambda и вызовах `GetFunctionConfiguration` в CloudTrail. Любой, у кого есть разрешение IAM `lambda:GetFunctionConfiguration`, может их прочитать. Не храните обычные учётные данные и API-ключи в переменных окружения — используйте Secrets Manager или SSM SecureString.

```bash
# Store the ARN in env vars, not the secret value
aws lambda update-function-configuration \
  --function-name myapp-processor \
  --environment 'Variables={
    API_URL=https://api.example.com,
    TABLE_NAME=myapp-events,
    DB_SECRET_ARN=arn:aws:secretsmanager:us-east-1:123456789012:secret:myapp/db-xK3p2q
  }'
```

### Слои

Слои — это версионируемые ZIP-архивы, которые можно использовать в нескольких функциях. Они монтируются в режиме только для чтения в `/opt`. Пакеты Python размещаются в `/opt/python/`, Node.js — в `/opt/nodejs/node_modules/`, бинарные файлы — в `/opt/bin/` (Lambda добавляет этот путь в `PATH`).

```bash
# Build a Python dependency layer — directory structure must match the runtime import path
mkdir -p python
pip install requests psycopg2-binary -t python/
zip -r deps-layer.zip python/

# Publish
aws lambda publish-layer-version \
  --layer-name myapp-deps \
  --description "requests + psycopg2-binary" \
  --zip-file fileb://deps-layer.zip \
  --compatible-runtimes python3.12 python3.11

# Attach to a function — use the full ARN including the version number
aws lambda update-function-configuration \
  --function-name myapp-processor \
  --layers arn:aws:lambda:us-east-1:123456789012:layer:myapp-deps:3

# Multiple layers (up to 5; applied in order — last wins on file conflicts)
aws lambda update-function-configuration \
  --function-name myapp-processor \
  --layers \
    arn:aws:lambda:us-east-1:123456789012:layer:myapp-deps:3 \
    arn:aws:lambda:us-east-1:123456789012:layer:datadog-extension:45
```

**Ограничения размера слоя:** ZIP-архив слоя может занимать до 50 МБ в сжатом виде и до 250 МБ после распаковки. Общий распакованный размер кода функции и всех слоёв должен быть меньше 250 МБ. Для больших наборов зависимостей (например, ML-инференса с numpy/scipy/torch) используйте развёртывание из образа контейнера — лимит составляет 10 ГБ.

Слои также используются для развёртывания Lambda Extensions — агентов, работающих в том же окружении, что и функция, для сбора телеметрии, передачи секретов или проксирования сетевого трафика (например, расширения Datadog и AWS AppConfig).

### Роль выполнения IAM

При вызове каждая функция Lambda принимает **роль выполнения**. Это идентичность, от имени которой Lambda обращается к другим сервисам AWS. В политике доверия роли principal должен быть `lambda.amazonaws.com`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

```bash
# Minimum permissions: write logs to CloudWatch
# AWSLambdaBasicExecutionRole is the AWS managed policy for this
aws iam attach-role-policy \
  --role-name lambda-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Add S3 read access for specific bucket
aws iam put-role-policy \
  --role-name lambda-execution-role \
  --policy-name s3-read-my-bucket \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::my-bucket/*"
    }]
  }'
```

**Принцип минимальных привилегий:** никогда не назначайте `AdministratorAccess` или `AmazonS3FullAccess` роли выполнения Lambda в production. Ограничивайте права конкретными действиями и ресурсами, которые нужны функции. Скомпрометированная функция с широкими правами может стать точкой дальнейшего проникновения в аккаунт AWS.

### Наблюдаемость

Lambda автоматически отправляет журналы в CloudWatch Logs. Для каждой функции создаётся группа `/aws/lambda/<function-name>`, а каждое вычислительное окружение создаёт новый поток журнала.

```bash
# Tail logs in real time (requires CloudWatch Logs Insights or awslogs tool)
aws logs tail /aws/lambda/myapp-processor --follow

# Query logs with CloudWatch Logs Insights
aws logs start-query \
  --log-group-name /aws/lambda/myapp-processor \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message
    | filter @message like /ERROR/
    | sort @timestamp desc
    | limit 20'
```

Каждый вызов автоматически создаёт строку журнала `REPORT` с длительностью выполнения, оплаченной длительностью, использованной памятью и максимальным потреблением памяти:

```
REPORT RequestId: abc-123  Duration: 142.73 ms  Billed Duration: 143 ms
       Memory Size: 256 MB  Max Memory Used: 89 MB  Init Duration: 312.14 ms
```

**`Init Duration` в строке REPORT указывает на холодный старт.** Если он появляется регулярно, рассмотрите provisioned concurrency или оптимизацию инициализации. `Max Memory Used` помогает подобрать подходящий объём памяти.

Для структурированной наблюдаемости используйте AWS Lambda Powertools (Python, Java, TypeScript): библиотека предоставляет структурированные JSON-журналы, трассировку через X-Ray и пользовательские метрики с минимальным объёмом шаблонного кода.

```python
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger()     # structured JSON logs with request_id, function_name auto-injected
tracer = Tracer()     # X-Ray tracing
metrics = Metrics(namespace="MyApp", service="processor")

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def handler(event, context):
    logger.info("Processing event", extra={"record_count": len(event.get("Records", []))})
    metrics.add_metric(name="RecordsProcessed", unit=MetricUnit.Count, value=1)
    ...
```

---

## Примеры

### Пример 1: обработчик CSV по событию S3

Обрабатывать CSV-файлы, загруженные в S3, проверять строки и записывать результаты в DynamoDB.

```bash
# --- Setup ---

# 1. Create the DynamoDB table
aws dynamodb create-table \
  --table-name csv-records \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# 2. Create the IAM role
aws iam create-role \
  --role-name csv-processor-role \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }'

aws iam attach-role-policy \
  --role-name csv-processor-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam put-role-policy \
  --role-name csv-processor-role \
  --policy-name csv-processor-perms \
  --policy-document '{
    "Version":"2012-10-17",
    "Statement":[
      {"Effect":"Allow","Action":["s3:GetObject"],"Resource":"arn:aws:s3:::my-csv-bucket/*"},
      {"Effect":"Allow","Action":["dynamodb:PutItem","dynamodb:BatchWriteItem"],"Resource":"arn:aws:dynamodb:us-east-1:123456789012:table/csv-records"}
    ]
  }'
```

```python
# handler.py
import boto3, csv, io, os, urllib.parse, uuid

s3 = boto3.client('s3')
table = boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])

def handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])

        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')

        reader = csv.DictReader(io.StringIO(content))
        items = []
        for row in reader:
            if not row.get('email'):    # basic validation
                continue
            items.append({
                'PutRequest': {
                    'Item': {
                        'id': str(uuid.uuid4()),
                        'email': row['email'],
                        'name': row.get('name', ''),
                        'source_key': key
                    }
                }
            })

        # BatchWriteItem accepts up to 25 items per call
        for i in range(0, len(items), 25):
            table.meta.client.batch_write_item(
                RequestItems={os.environ['TABLE_NAME']: items[i:i+25]}
            )

        print(f"Wrote {len(items)} records from {key}")
```

```bash
# Deploy
zip function.zip handler.py

aws lambda create-function \
  --function-name csv-processor \
  --runtime python3.12 \
  --handler handler.handler \
  --role arn:aws:iam::123456789012:role/csv-processor-role \
  --zip-file fileb://function.zip \
  --timeout 60 \
  --memory-size 256 \
  --environment Variables='{TABLE_NAME=csv-records}'

# Grant S3 permission and configure trigger
aws lambda add-permission \
  --function-name csv-processor \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::my-csv-bucket \
  --source-account 123456789012 \
  --statement-id s3-csv-trigger

aws s3api put-bucket-notification-configuration \
  --bucket my-csv-bucket \
  --notification-configuration '{
    "LambdaFunctionConfigurations":[{
      "LambdaFunctionArn":"arn:aws:lambda:us-east-1:123456789012:function:csv-processor",
      "Events":["s3:ObjectCreated:*"],
      "Filter":{"Key":{"FilterRules":[{"Name":"suffix","Value":".csv"}]}}
    }]
  }'

# --- Verify ---
# Upload a test file and watch logs
echo "email,name
alice@example.com,Alice
bob@example.com,Bob" > test.csv

aws s3 cp test.csv s3://my-csv-bucket/test.csv

# Poll logs for output
aws logs tail /aws/lambda/csv-processor --follow --since 2m

# Verify DynamoDB records were written
aws dynamodb scan --table-name csv-records --max-items 5
```

---

### Пример 2: обработчик SQS с частичной обработкой ошибок пакета

Process order events from an SQS queue with reliable partial failure semantics.

```python
# handler.py
import boto3, json, os

orders_table = boto3.resource('dynamodb').Table(os.environ['ORDERS_TABLE'])

def process_order(order: dict):
    if not order.get('order_id') or not order.get('amount'):
        raise ValueError(f"Invalid order payload: {order}")

    orders_table.put_item(Item={
        'order_id': order['order_id'],
        'amount': str(order['amount']),    # DynamoDB requires Decimal for floats; use str for simplicity
        'status': 'received',
        'customer_id': order.get('customer_id', 'unknown')
    })

def handler(event, context):
    failures = []
    for record in event['Records']:
        try:
            order = json.loads(record['body'])
            process_order(order)
            print(f"Processed order {order.get('order_id')}")
        except Exception as e:
            print(f"ERROR processing message {record['messageId']}: {e}")
            failures.append({'itemIdentifier': record['messageId']})

    return {'batchItemFailures': failures}
```

```bash
# Create SQS queue with a DLQ
aws sqs create-queue --queue-name orders-dlq
DLQ_ARN=$(aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/orders-dlq \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' --output text)

aws sqs create-queue \
  --queue-name orders \
  --attributes "{
    \"RedrivePolicy\": \"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"
  }"

# Deploy
zip function.zip handler.py

aws lambda create-function \
  --function-name order-worker \
  --runtime python3.12 \
  --handler handler.handler \
  --role arn:aws:iam::123456789012:role/lambda-execution-role \
  --zip-file fileb://function.zip \
  --timeout 30 \
  --memory-size 256 \
  --environment Variables='{ORDERS_TABLE=orders}'

# Create event source mapping with partial batch success
QUEUE_ARN=$(aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/orders \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' --output text)

aws lambda create-event-source-mapping \
  --function-name order-worker \
  --event-source-arn $QUEUE_ARN \
  --batch-size 10 \
  --maximum-batching-window-in-seconds 5 \
  --function-response-types ReportBatchItemFailures

# --- Verify ---
# Send test messages (one valid, one invalid)
aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/orders \
  --message-body '{"order_id":"ord-001","amount":99.99,"customer_id":"cust-42"}'

aws sqs send-message \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/orders \
  --message-body '{"broken":"payload"}'    # missing order_id — will fail

# Check logs: should show one success and one failure
aws logs tail /aws/lambda/order-worker --follow --since 2m

# Check DLQ for the failed message after maxReceiveCount retries
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/orders-dlq \
  --attribute-names ApproximateNumberOfMessages
```

---

### Example 3: Scheduled Cleanup Job with EventBridge

Run a nightly DynamoDB TTL cleanup report using EventBridge Scheduler.

```python
# handler.py
import boto3, os, json
from datetime import datetime, timezone

table = boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])
sns = boto3.client('sns')

def handler(event, context):
    source = event.get('source', 'unknown')
    run_time = datetime.now(timezone.utc).isoformat()

    # Scan for expired-but-not-yet-deleted items (TTL is eventually consistent)
    response = table.scan(
        FilterExpression='#ttl < :now AND attribute_exists(#ttl)',
        ExpressionAttributeNames={'#ttl': 'ttl'},
        ExpressionAttributeValues={':now': int(datetime.now(timezone.utc).timestamp())}
    )

    stale_count = response['Count']
    print(f"Found {stale_count} stale items at {run_time}")

    if stale_count > 100:   # alert if TTL cleanup is falling behind
        sns.publish(
            TopicArn=os.environ['ALERT_TOPIC_ARN'],
            Subject='Lambda TTL Cleanup Alert',
            Message=json.dumps({
                'table': os.environ['TABLE_NAME'],
                'stale_items': stale_count,
                'timestamp': run_time
            })
        )

    return {'stale_items': stale_count, 'run_time': run_time}
```

```bash
zip function.zip handler.py

aws lambda create-function \
  --function-name nightly-cleanup \
  --runtime python3.12 \
  --handler handler.handler \
  --role arn:aws:iam::123456789012:role/lambda-execution-role \
  --zip-file fileb://function.zip \
  --timeout 300 \    # 5 minutes for large table scans
  --memory-size 512 \
  --environment Variables='{TABLE_NAME=myapp-events,ALERT_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:alerts}'

# Schedule to run at 2 AM UTC daily
aws events put-rule \
  --name nightly-cleanup-schedule \
  --schedule-expression "cron(0 2 * * ? *)" \
  --state ENABLED

aws events put-targets \
  --rule nightly-cleanup-schedule \
  --targets '[{
    "Id": "NightlyCleanup",
    "Arn": "arn:aws:lambda:us-east-1:123456789012:function:nightly-cleanup",
    "Input": "{\"source\": \"eventbridge-scheduled\"}"
  }]'

aws lambda add-permission \
  --function-name nightly-cleanup \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:123456789012:rule/nightly-cleanup-schedule \
  --statement-id eventbridge-nightly

# --- Verify: invoke manually to test before waiting for the schedule ---
aws lambda invoke \
  --function-name nightly-cleanup \
  --payload '{"source": "manual-test"}' \
  --cli-binary-format raw-in-base64-out \
  output.json

cat output.json   # should show {"stale_items": N, "run_time": "..."}

# Confirm scheduled rule is active
aws events describe-rule --name nightly-cleanup-schedule \
  | jq '{State: .State, ScheduleExpression: .ScheduleExpression}'
```

---

## Практические задания

### Exercise 1: Deploy and Debug an Intentionally Broken Function

Write a Lambda function that reads an environment variable `REQUIRED_VAR` and raises a `ValueError` if it is missing. Deploy it twice: first **without** the environment variable set, invoke it, and capture the error output. Then update the configuration to add the variable and confirm the function succeeds.

The goal is to practice the full CLI deploy-invoke-debug loop and to understand why `aws lambda invoke` returning status 0 is not a success signal. Your solution must parse `output.json` to detect the `FunctionError` field programmatically.

**Hints:**
- Use `--log-type Tail` on the broken invocation and decode the base64 log to see the traceback.
- Write a small bash `if` block that exits non-zero when `FunctionError` is present.

---

### Exercise 2: SQS Fan-Out with Concurrency Limit

Create an SQS queue, deploy an SQS-triggered Lambda that simulates slow processing (use `time.sleep(2)`), and send 50 messages to the queue in a loop. Then:

1. Observe how many concurrent executions Lambda scales to using CloudWatch metrics (`ConcurrentExecutions`).
2. Set reserved concurrency to 5 on the function and re-send 50 messages.
3. Measure how long the queue takes to drain in each scenario and explain the tradeoff.

**What to compare:** total drain time with unrestricted concurrency vs. reserved concurrency of 5. Explain in one paragraph when you would choose to limit concurrency on an SQS consumer.

---

### Exercise 3: Dependency Layer for a Third-Party Package

Your Lambda function needs the `httpx` package, which is not included in the Python 3.12 runtime. Package `httpx` into a layer, publish it, attach it to a function, and verify the import works at invocation time.

Requirements:
- The function's deployment ZIP must contain **only** your handler code — no `httpx` files.
- The layer must be published with `--compatible-runtimes python3.12`.
- Confirm success by having the handler print `httpx.__version__` and checking the log output.

**Extension:** check the size of your layer ZIP. What is the maximum compressed size a single layer can be? What would you do if your ML inference dependencies (numpy, scipy, torch) exceeded that limit?

---

### Exercise 4: End-to-End Async Event Pipeline with DLQ

Build a pipeline: EventBridge rule (rate 1 minute) → Lambda → intentional failure → DLQ.

1. Write a Lambda function that always raises an exception (simulating a broken processor).
2. Configure an SQS DLQ on the function's async failure destination.
3. Create an EventBridge rule that triggers the function every minute.
4. Wait 10–15 minutes, then inspect the DLQ to confirm failed invocation records are arriving.
5. Read one DLQ message and decode its body — document what fields Lambda includes in the async failure record.

**What you're learning:** async retry behavior (Lambda retries 2×, then routes to the DLQ), the structure of Lambda's async failure payload, and the difference between a function-level DLQ and an event source DLQ. Disable the EventBridge rule when you're done to avoid ongoing charges.

---

### Быстрая проверка

6. Extract the handler function name from a Lambda config stub. Run: `printf 'Handler: index.handler\nRuntime: nodejs20.x\n' | awk '/^Handler:/{split($2, a, "."); print a[2]}'`

```expected_output
handler
```

hint: Think about how awk can match a specific line and then split a field on a delimiter to isolate one part of it.
hint: Use awk's pattern /^Handler:/ to select the right line, then apply split($2, a, ".") to break the value on the dot and print the second element a[2].

7. Calculate Lambda memory after doubling from 512 MB. Run: `python3 -c "print(512 * 2)"`

```expected_output
1024
```

hint: Think about how Python's print function can evaluate a mathematical expression directly from the command line using the -c flag.
hint: Use python3 -c with print() and the multiplication operator * to calculate the result of 512 doubled.
