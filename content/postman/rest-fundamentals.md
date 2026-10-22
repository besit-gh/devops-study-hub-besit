---
title: Основы REST API
module: postman
duration_min: 20
difficulty: beginner
tags: [postman, rest, http, api, request, response, headers, status-codes, curl]
exercises: 4
---

## Обзор

REST (Representational State Transfer) — наиболее распространённый стиль API для веб-сервисов, и его понимание необходимо для работы в DevOps. Современные инфраструктурные инструменты — Kubernetes, Vault, Terraform Cloud, GitHub Actions, PagerDuty и Datadog — предоставляют REST API. Автоматизация развёртывания, интеграции IaC, создание runbook и диагностика production-инцидентов требуют умения читать, формировать и анализировать HTTP-запросы и ответы. Если вы не понимаете ответ API и разницу между `403` и `401`, это будет постоянно мешать работе.

REST — не протокол, а набор архитектурных ограничений, сформулированных Роем Филдингом в 2000 году. Основные принципы: отсутствие состояния на сервере (каждый запрос содержит всё необходимое для обработки и не зависит от серверной сессии), единый интерфейс (ресурсы идентифицируются URL и изменяются через представления) и разделение клиента и сервера. На практике REST API обмениваются данными по HTTP, используют JSON, обозначают ресурсы существительными в путях, а назначение операции выражают HTTP-методами. Эти ограничения делают API предсказуемыми и удобными для кеширования.

В DevOps знание REST API напрямую связано с другими навыками: `curl` для диагностики и shell-скриптов, Postman для изучения API и создания автоматизированных тестов, конвейеры CI/CD для вызова API развёртывания и инструменты наблюдаемости, обращающиеся к базам временных рядов по HTTP. В уроке рассматриваются структура запроса, методы, коды состояния, заголовки и два основных инструмента взаимодействия — `curl` и Postman.

---

## Основные понятия

### Структура HTTP-запроса

Каждое взаимодействие по HTTP состоит из запроса и ответа. Понимание структуры обеих частей помогает правильно формировать запросы и точно диагностировать проблемы.

```
POST /api/users HTTP/1.1
Host: api.example.com
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
Accept: application/json
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000

{
  "name": "Alex Chen",
  "email": "alex@example.com",
  "role": "admin"
}
```

| Part | Location | Purpose |
|------|----------|---------|
| **Method** | First line | What action to perform (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`) |
| **Path** | First line | Which resource (`/api/users`, `/api/users/123`) |
| **HTTP version** | First line | Protocol version (`HTTP/1.1`, `HTTP/2`) |
| **Headers** | Before blank line | Metadata: auth, content negotiation, tracing |
| **Body** | After blank line | Data payload — only present on `POST`, `PUT`, `PATCH` |
| **Query params** | Appended to path | Filters, sorting, pagination (`?role=admin&limit=10`) |

Ответ имеет аналогичную структуру: строка статуса (`HTTP/1.1 201 Created`), заголовки ответа, пустая строка и необязательное тело.

**Пустая строка между заголовками и телом обязательна.** По ней сервер определяет конец заголовков. Отсутствующий или некорректный `Content-Type` — одна из частых причин `400 Bad Request` в скриптах: сервер получает JSON, но не понимает, что его нужно разбирать как JSON.

**Параметры запроса и сегменты пути:** сегменты пути указывают конкретный ресурс (`/users/123`), а параметры запроса фильтруют, сортируют или разбивают коллекцию на страницы (`/users?role=admin&limit=10&page=2`). Если перепутать их, маршрутизатор сервера может не найти соответствующий путь и вернуть `404`.

---

### HTTP-методы

HTTP-методы задают намерение запроса. REST сопоставляет CRUD-операции с методами, но их семантика не сводится только к «создать/прочитать/обновить/удалить».

| Method | Meaning | Has Body | Idempotent | Safe |
|--------|---------|----------|------------|------|
| `GET` | Read a resource | No | Yes | Yes |
| `POST` | Create a resource | Yes | No | No |
| `PUT` | Replace a resource (full update) | Yes | Yes | No |
| `PATCH` | Partial update | Yes | No | No |
| `DELETE` | Delete a resource | No | Yes | No |
| `HEAD` | Like GET, returns headers only | No | Yes | Yes |
| `OPTIONS` | List allowed methods (used in CORS) | No | Yes | Yes |

**Idempotent** means calling the operation N times produces the same server state as calling it once. `PUT /users/1` with the same body always results in the same user record — the second call is a no-op. `POST /users` creates a new user on every call, so it is not idempotent. This distinction matters in retry logic: it is safe to auto-retry idempotent methods; retrying `POST` blindly can create duplicate records.

**Безопасный метод** не изменяет состояние сервера. Все безопасные методы идемпотентны, но обратное неверно. `DELETE` идемпотентен (повторное удаление уже удалённого ресурса оставляет то же состояние — ресурс отсутствует), но не является безопасным.

**`PUT` и `PATCH`:** `PUT` требует передавать полное представление ресурса. Если отправить объект пользователя через `PUT` без поля `email`, корректная реализация может установить `email` в `null`. `PATCH` передаёт только изменяемые поля. Используйте `PATCH` для частичных обновлений: это снижает риск случайно обнулить данные в объектах с большим числом полей.

**`DELETE` возвращает `404` при повторном вызове:** некоторые API отвечают `404`, если ресурс уже удалён. Формально это нарушает идемпотентность. В логике повторных попыток можно считать `404` для `DELETE` успешным результатом, чтобы избежать ложных ошибок в конвейере.

---

### Коды состояния HTTP

Коды состояния — машиночитаемый сигнал API о результате запроса. Быстрее всего оценить ситуацию можно по классу кода.

```
1xx — Informational (rarely seen in practice)
  100 Continue         — server received request headers, client should send body

2xx — Success
  200 OK               — request succeeded; body contains the result
  201 Created          — resource was created (POST); Location header has its URL
  204 No Content       — success but no body (common for DELETE, sometimes PUT)

3xx — Redirection
  301 Moved Permanently — URL has changed; update your scripts/configs
  304 Not Modified      — cached copy is still valid (conditional GET with ETag)

4xx — Client Errors (you sent something wrong)
  400 Bad Request       — malformed JSON, missing required field, invalid value
  401 Unauthorized      — not authenticated (no token, expired token, wrong scheme)
  403 Forbidden         — authenticated but not authorized for this resource/action
  404 Not Found         — resource does not exist at this path
  405 Method Not Allowed — valid path, wrong HTTP method
  409 Conflict          — resource already exists, or state conflict (e.g., duplicate key)
  422 Unprocessable     — valid JSON format but semantic validation failed
  429 Too Many Requests — rate limited; check Retry-After header

5xx — Server Errors (the server failed)
  500 Internal Server Error — unhandled exception, bug in the server code
  502 Bad Gateway           — reverse proxy got an invalid response from upstream
  503 Service Unavailable   — server temporarily overloaded or in maintenance
  504 Gateway Timeout       — upstream service took too long to respond
```

**`401` и `403`:** это различие важно при диагностике. `401` означает, что сервер не распознал вас: проверьте токен, срок его действия и формат заголовка `Authorization`. `403` означает, что сервер знает вашу личность, но у вас нет разрешения: проверьте роли RBAC, области доступа и владение ресурсом. Путаница между этими кодами тратит время на диагностику.

**`502` и `504`:** оба кода указывают на проблему между прокси и вышестоящим сервисом. `502` означает, что upstream вернул некорректный ответ или неожиданно закрыл соединение. `504` означает, что ответ не поступил за отведённое время. В Kubernetes они часто указывают на аварийно завершающийся Pod (`502`) или перегруженный/недоступный сервис (`504`).

**`422` и `400`:** `400` обычно означает структурную проблему (неразбираемый JSON или неверный Content-Type), а `422` — семантическую (JSON корректен, но значение `"age": -5` не проходит бизнес-проверку). Не все API соблюдают это различие и могут использовать `400` для обоих случаев. В API-клиентах обрабатывайте оба кода одинаково: показывайте оператору сообщение из тела ответа.

**Обработка `429` в автоматизации:** получив `429`, прочитайте заголовок `Retry-After` перед повторной попыткой. Немедленный повтор без паузы снова активирует ограничитель частоты и задержит восстановление. В скриптах, многократно вызывающих API, используйте экспоненциальную задержку со случайным разбросом.

---

### Важные заголовки

Заголовки передают метаданные для аутентификации, кэширования, согласования формата содержимого и наблюдаемости. В DevOps-автоматизации они часто становятся источником трудно диагностируемых ошибок.

```
# Request headers
Authorization: Bearer <token>          # Auth — most common for APIs
Authorization: Basic <base64(user:pw)> # Basic auth (legacy, avoid over plain HTTP)
Content-Type: application/json         # Format of the request body you are sending
Accept: application/json               # Formats you will accept in the response
X-Request-ID: <uuid>                   # Trace a single request across distributed logs
If-None-Match: "abc123"                # Conditional GET — only return if ETag changed

# Response headers
Content-Type: application/json         # Format of the response body
Location: /api/users/123               # URL of newly created resource (on 201)
X-RateLimit-Limit: 100                 # Total requests allowed in window
X-RateLimit-Remaining: 95             # Requests left in current window
X-RateLimit-Reset: 1716700000         # Unix timestamp when the window resets
ETag: "abc123"                         # Version fingerprint for caching
Cache-Control: max-age=3600, public    # Cache directives
Retry-After: 30                        # Seconds to wait before retrying (429, 503)
```

**`Authorization: Bearer` и `Authorization: Token`:** это разные схемы. GitHub использует `token <value>` для персональных токенов доступа и `Bearer <value>` для OAuth-токенов. Неверная схема приведёт к `401`, даже если сам токен действителен. Всегда проверяйте точный формат в документации API: копирование заголовка от другого API часто вызывает ошибки аутентификации.

**`Content-Type` в ответах:** если сервер возвращает `Content-Type: text/html` вместе с ошибкой `500`, возможно, вы получили страницу ошибки балансировщика, а не приложения. В скриптах проверяйте `Content-Type` до передачи ответа в `jq`: на HTML `jq` выдаст малопонятную ошибку разбора, скрывающую настоящую проблему.

**Схема кэширования на основе ETag:**
1. Первый запрос возвращает заголовок `ETag: "v1"`.
2. Следующий запрос отправляет `If-None-Match: "v1"`.
3. Если ресурс не изменился, сервер отвечает `304 Not Modified` — тело не передаётся.
4. Клиент использует сохранённую копию.

Так CI-конвейеры избегают повторной загрузки больших артефактов при каждом запуске. Аналогичный подход помогает инструментам вроде `kubectl` не создавать лишнюю нагрузку на API-сервер при опросе состояния ресурсов.

**`X-Request-ID` и трассировка:** всегда создавайте и передавайте `X-Request-ID` (или `X-Correlation-ID`) в автоматизированных скриптах, обращающихся к production API. При сбое можно найти UUID в журналах API-сервера и восстановить цепочку вызовов. Без идентификатора связать запрос скрипта с записью журнала в загруженной системе почти невозможно.

---

### Основы curl

`curl` — универсальный HTTP-клиент для shell-скриптов и диагностики. Небольшого набора хорошо освоенных параметров достаточно для большинства задач DevOps.

```bash
# Basic GET
curl https://api.example.com/users

# Silence the progress meter, pipe to jq for pretty output
curl -s https://api.example.com/users | jq .

# GET with auth and query parameters
curl -s \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.example.com/users?role=admin&limit=10" | jq .

# POST — create a resource
curl -s -X POST https://api.example.com/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Alex", "email": "alex@example.com", "role": "admin"}' \
  | jq '{id, name, created_at}'

# POST from a file (useful for large bodies or reusable payloads)
curl -s -X POST https://api.example.com/users \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d @payload.json

# PATCH — partial update
curl -s -X PATCH https://api.example.com/users/123 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"role": "viewer"}' | jq .

# DELETE — capture status code, discard body
curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/users/123

# Inspect response headers only (HEAD request)
curl -sI https://api.example.com/health

# Verbose mode — prints request headers, response headers, and body
# Use this when debugging auth or SSL issues
curl -v https://api.example.com/health 2>&1 | less

# Dump response headers to stdout AND show the body
# Useful for capturing ETag, Location, or rate-limit headers
curl -D - -s https://api.example.com/users/123

# Timing breakdown — diagnose slow endpoints
curl -w "\nDNS:     %{time_namelookup}s\nConnect: %{time_connect}s\nTLS:     %{time_appconnect}s\nTTFB:    %{time_starttransfer}s\nTotal:   %{time_total}s\n" \
  -o /dev/null -s https://api.example.com/health

# Follow redirects automatically (301, 302)
curl -L https://api.example.com/old-path

# Store cookies to file and send them on subsequent requests
curl -c cookies.txt -b cookies.txt https://api.example.com/session
```

| Flag | Meaning |
|------|---------|
| `-s` | Silent — suppress progress meter |
| `-S` | Show errors even when silent (use with `-s`) |
| `-v` | Verbose — show full request and response headers |
| `-I` | HEAD request — headers only |
| `-D -` | Dump response headers to stdout |
| `-X METHOD` | Set HTTP method |
| `-H "Key: Value"` | Add a request header |
| `-d 'body'` | Request body (string or `@filename`) |
| `-o /dev/null` | Discard the response body |
| `-w "format"` | Print timing/status info after request |
| `-L` | Follow redirects |
| `-f` / `--fail` | Exit non-zero on 4xx/5xx responses |

**`--fail` в CI-скриптах:** всегда используйте `curl --fail` (или `-f`) в CI-конвейерах. Без него `curl` возвращает `0` даже при ошибке `500`, и конвейер может ошибочно считаться успешным. Сочетайте с `-s` и `-S`, чтобы скрыть индикатор прогресса, но продолжать выводить сообщения об ошибках в stderr.

```bash
# CI-safe curl: fail on HTTP error, show errors, silent progress
curl -fsSL \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -X POST https://api.example.com/deploy \
  -d '{"version": "1.2.3"}' \
  || { echo "ERROR: Deployment API call failed"; exit 1; }
```

**Кавычки и специальные символы в `-d`:** если JSON содержит специальные для оболочки символы, заключайте всё тело в одинарные кавычки или читайте его из файла через `@payload.json`. Подстановка переменных внутри одинарных кавычек не работает. Если нужно вставить переменные оболочки в JSON, используйте двойные кавычки или соберите тело с помощью `printf`.

```bash
# Wrong — $USER is not expanded inside single quotes on some shells
curl -d '{"user": "$USER"}' ...

# Correct — use double quotes and escape inner quotes
curl -d "{\"user\": \"$USER\"}" ...

# Better — build the body cleanly with jq
BODY=$(jq -n --arg user "$USER" '{"user": $user}')
curl -d "$BODY" ...
```

---

### Основы Postman

Postman предоставляет графический интерфейс для создания, сохранения и организации API-запросов. Он полезен при изучении незнакомого API и создании общей коллекции, которой команда пользуется для тестирования и документации.

#### Выполнение запросов

1. **Method + URL** — выберите метод в списке и введите URL в адресную строку.
2. **Вкладка Params** — добавьте параметры запроса в виде пар «ключ — значение»; Postman автоматически добавит их к URL и выполнит URL-кодирование.
3. **Вкладка Authorization** — выберите тип аутентификации (`Bearer Token`, `Basic Auth`, `API Key`). Postman автоматически добавит нужный заголовок. Не добавляйте его вручную во вкладке Headers, иначе он будет отправлен дважды.
4. **Вкладка Headers** — добавьте пользовательские заголовки (`X-Request-ID`, `Accept`, переопределение `Content-Type`).
5. **Вкладка Body** — для `POST`/`PUT`/`PATCH` выберите `raw → JSON`. В этом режиме Postman автоматически задаёт `Content-Type: application/json`.
6. **Send** — отправьте запрос; результаты появятся в нижней панели.

#### Чтение ответов

| Panel | What to look for |
|-------|-----------------|
| **Status** | Code + label, color-coded (green = 2xx, orange = 3xx, red = 4xx/5xx) |
| **Body → Pretty** | Auto-formatted JSON; use this for readability |
| **Body → Raw** | Exact bytes received — use when Pretty rendering looks wrong or content is not JSON |
| **Headers** | All response headers: `ETag`, `Location`, `X-RateLimit-*`, `Content-Type` |
| **Test Results** | Pass/fail output of any test scripts attached to the request |

#### Окружения и переменные

Окружения позволяют переключаться между `dev`, `staging` и `prod`, не редактируя каждый запрос. Задайте переменную один раз и ссылайтесь на неё везде через синтаксис `{{variable_name}}`.

```
# Define in Environment (Postman → Environments → New):
base_url   = https://api.staging.example.com
token      = eyJhbGci...
user_id    = 42

# Use in requests:
URL:     {{base_url}}/users/{{user_id}}
Header:  Authorization: Bearer {{token}}
Body:    {"notify_url": "{{base_url}}/webhooks/callback"}
```

Переключайте окружения в раскрывающемся списке в правом верхнем углу Postman. Все запросы во всех коллекциях сразу используют новые значения — искать и заменять вручную не нужно.

**Переменные окружения и глобальные переменные Postman:** используйте переменные окружения для значений, меняющихся между средами (`base_url`, `token`). Глобальные переменные применяйте редко: они доступны во всех рабочих пространствах и окружениях и могут незаметно загрязнять тесты и вызывать различия в поведении у участников команды.

**Динамическое задание переменных из ответа:** после запроса входа часто нужно сохранить полученный токен для следующих запросов. Извлеките его автоматически с помощью тестового скрипта:

```javascript
// In the Tests tab of your login request:
const json = pm.response.json();
pm.environment.set("token", json.access_token);
// Now {{token}} is populated for all subsequent requests in this session
```

#### Collections

Коллекция — это сохранённый набор запросов, организованный по папкам. В DevOps-процессах коллекции решают три задачи:

1. **Документация команды** — актуальное исполняемое описание API-эндпоинтов с примерами тел запросов и ожидаемыми ответами. Оно надёжнее wiki, которая со временем устаревает.
2. **Автоматизированное регрессионное тестирование** — к каждому запросу можно добавить JavaScript-проверки кодов статуса, структуры ответа и значений. Вся коллекция запускается одним нажатием или через CLI.
3. **Ввод в работу** — новый участник импортирует коллекцию и окружение, задаёт токен и сразу может обращаться ко всем API, не изучая документацию заранее.

#### Написание тестов в Postman

Тестовые скрипты Postman запускаются после каждого ответа. Они используют встроенную в песочницу Postman библиотеку утверждений JavaScript (`pm.test`, `pm.expect`).

```javascript
// Assert status code
pm.test("Status is 201", () => {
  pm.response.to.have.status(201);
});

// Assert response body shape
pm.test("Response has an id field", () => {
  const json = pm.response.json();
  pm.expect(json).to.have.property("id");
  pm.expect(json.id).to.be.a("number");
});

// Assert a specific header is present
pm.test("Location header is set", () => {
  pm.response.to.have.header("Location");
});

// Assert response time is acceptable
pm.test("Response time under 500ms", () => {
  pm.expect(pm.response.responseTime).to.be.below(500);
});
```

**Запуск коллекций в CI:** экспортируйте коллекцию и окружение в JSON, а затем запустите их через Newman — CLI-инструмент Postman:

```bash
# Install Newman
npm install -g newman

# Run collection against staging, output JUnit XML for CI reporting
newman run my-api-collection.json \
  --environment staging.postman_environment.json \
  --reporters cli,junit \
  --reporter-junit-export results.xml
```

Так коллекции Postman напрямую интегрируются в Jenkins, GitHub Actions или GitLab CI: запросы, которые команда выполняла вручную, становятся автоматизированным набором регрессионных тестов API.

---

## Примеры

### Пример 1. Запрос к GitHub API с помощью curl

В примере показаны аутентификация, чтение заголовков ответа для контроля лимитов запросов и извлечение нужных полей с помощью `jq`.

```bash
# Store your token in an environment variable — never hardcode tokens
export GITHUB_TOKEN="ghp_your_personal_access_token"

# List repositories for an org, extract just names and visibility
curl -fsSL \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/orgs/hashicorp/repos?type=public&per_page=5" \
  | jq '.[] | {name, visibility, language, stargazers_count}'

# Verify it worked: you should see a JSON array of repo objects
# Expected output (truncated):
# {
#   "name": "terraform",
#   "visibility": "public",
#   "language": "Go",
#   "stargazers_count": 40123
# }

# Check rate limit headers before running bulk operations
curl -fsSI \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/rate_limit \
  | grep -i "x-ratelimit"
# X-RateLimit-Limit: 5000
# X-RateLimit-Remaining: 4987
# X-RateLimit-Reset: 1716700000

# Convert the reset timestamp to a human-readable time (macOS/Linux)
date -d @1716700000   # Linux
date -r 1716700000    # macOS
```

### Пример 2. Создание и обновление ресурса (полный цикл CRUD)

В примере используется публичный API JSONPlaceholder (аутентификация не нужна), чтобы последовательно показать POST, GET, PATCH и DELETE.

```bash
BASE="https://jsonplaceholder.typicode.com"

# 1. CREATE — POST returns 201 and the new object with an assigned id
NEW_POST=$(curl -fsS -X POST "$BASE/posts" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "DevOps API Testing",
    "body": "curl is the best debugging tool",
    "userId": 1
  }')
echo "$NEW_POST" | jq .
# Capture the id for subsequent requests
POST_ID=$(echo "$NEW_POST" | jq -r '.id')
echo "Created post with id: $POST_ID"

# 2. READ — GET the resource we just created
curl -fsS "$BASE/posts/$POST_ID" | jq '{id, title}'

# 3. PARTIAL UPDATE — PATCH only the title, leave body unchanged
curl -fsS -X PATCH "$BASE/posts/$POST_ID" \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated Title"}' \
  | jq '{id, title, body}'
# body should still be present — PATCH does not remove fields you did not send

# 4. DELETE — expect 200 with empty body {} from JSONPlaceholder
STATUS=$(curl -fsS -o /dev/null -w "%{http_code}" \
  -X DELETE "$BASE/posts/$POST_ID")
echo "Delete status: $STATUS"
# Should print: Delete status: 200
```

### Пример 3. Запуск workflow GitHub Actions через API

Это реалистичный сценарий DevOps: запуск конвейера развёртывания из скрипта и последующий опрос для подтверждения старта.

```bash
export GITHUB_TOKEN="ghp_your_personal_access_token"
OWNER="my-org"
REPO="my-app"
WORKFLOW="deploy.yml"
REF="main"

# Trigger the workflow with an input parameter
RESPONSE=$(curl -fsS -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/$OWNER/$REPO/actions/workflows/$WORKFLOW/dispatches" \
  -d "{\"ref\": \"$REF\", \"inputs\": {\"environment\": \"staging\"}}")

# workflow_dispatch returns 204 No Content on success — empty body
# If $RESPONSE is empty and exit code was 0, the trigger succeeded
echo "Trigger exit code: $?"

# Poll for the most recently created run to confirm it started
# Wait a few seconds for GitHub to register the run
sleep 5

curl -fsS \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/$OWNER/$REPO/actions/runs?event=workflow_dispatch&per_page=1" \
  | jq '.workflow_runs[0] | {id, status, conclusion, created_at, head_branch}'
# Expected:
# {
#   "id": 9876543210,
#   "status": "queued",
#   "conclusion": null,
#   "created_at": "2024-05-26T10:00:00Z",
#   "head_branch": "main"
# }
```

### Пример 4. Запуск коллекции Postman в CI через Newman

Пример показывает полный процесс: коллекция Postman проверяет эндпоинт состояния и сценарий создания пользователя, экспортируется и запускается в конвейере GitHub Actions.

```yaml
# .github/workflows/api-tests.yml
name: API Integration Tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  api-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Newman
        run: npm install -g newman newman-reporter-htmlextra

      - name: Run Postman Collection (Staging)
        env:
          API_TOKEN: ${{ secrets.STAGING_API_TOKEN }}
        run: |
          # Inject the secret token into the environment file at runtime
          # so the token is never stored in the exported environment JSON
          cat postman/staging.environment.json \
            | jq --arg token "$API_TOKEN" \
              '(.values[] | select(.key == "token")).value = $token' \
            > /tmp/staging-injected.json

          newman run postman/api-tests.collection.json \
            --environment /tmp/staging-injected.json \
            --reporters cli,junit,htmlextra \
            --reporter-junit-export results/junit.xml \
            --reporter-htmlextra-export results/report.html \
            --bail  # stop collection run on first test failure

      - name: Upload Test Results
        if: always()   # upload even if tests failed
        uses: actions/upload-artifact@v4
        with:
          name: api-test-results
          path: results/
```

```
# Postman collection test script on the POST /users request:
pm.test("User created with correct role", () => {
  pm.response.to.have.status(201);
  const json = pm.response.json();
  pm.expect(json.role).to.eql("admin");
  pm.environment.set("created_user_id", json.id);  // pass id to next request
});
```

---

## Практические задания

### Задание 1. Диагностируйте неработающий вызов API

Следующая команда `curl` содержит две ошибки. Не запуская её, найдите обе проблемы, затем исправьте команду и убедитесь, что она возвращает `200` и тело в формате JSON.

```bash
curl -X GET https://jsonplaceholder.typicode.com/posts/1
  -H 'Content-Type: application/json'
  -H 'Accept: text/html'
  -d '{"limit": 10}'
```

**What to find:**
- Почему заголовок `Accept` неверен для JSON API?
- Почему тело запроса у `GET` семантически некорректно?
- Почему команда завершится ошибкой ещё до обращения к серверу?
- Напишите исправленную команду и передайте ответ в `jq`, чтобы извлечь только поле `title`.

---

### Задание 2. Изучите заголовки лимитов и обработайте `429`

Многократно вызывайте публичный API GitHub в цикле и напишите скрипт, который корректно обрабатывает ограничение частоты запросов.

```bash
# Starting point — run this and observe what happens after many calls
for i in $(seq 1 10); do
  curl -s https://api.github.com/repos/torvalds/linux | jq '.stargazers_count'
done
```

**Задача:**
1. Измените цикл так, чтобы HTTP-код статуса сохранялся отдельно от тела ответа.
2. If the status code is `429` or `403` (GitHub uses `403` for rate limits on unauthenticated requests), read the `X-RateLimit-Reset` header, calculate how many seconds until reset, sleep that long, then retry the request.
3. Add a `X-Request-ID` header with a unique UUID to each request (use `uuidgen` or `cat /proc/sys/kernel/random/uuid`).

---

### Exercise 3: Build and Test a Postman Collection

Using Postman with the JSONPlaceholder API (`https://jsonplaceholder.typicode.com`):

1. Create an environment with a variable `base_url = https://jsonplaceholder.typicode.com`.
2. Build a collection with three requests in order:
   - `POST /posts` — create a post, extract the `id` from the response and save it to an environment variable `post_id` in the Tests tab.
   - `GET /posts/{{post_id}}` — fetch the post you just created; assert the status is `200` and the `id` matches `{{post_id}}`.
   - `DELETE /posts/{{post_id}}` — delete it; assert the status is `200`.
3. Write a test on the `POST` request that fails if the response time exceeds `1000ms`.
4. Export the collection and environment as JSON files. Verify you can run the exported collection with `newman run` from the terminal.

---

### Exercise 4: Debug a `403` vs `401` in the Wild

Use the GitHub API to explore the difference between unauthenticated and unauthorized requests.

```bash
# Request 1 — no token
curl -sI https://api.github.com/user

# Request 2 — invalid token
curl -sI -H "Authorization: Bearer invalidtoken123" https://api.github.com/user

# Request 3 — valid token but accessing a private resource you do not own
# (substitute a real org name you are not a member of)
curl -sI \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/orgs/some-private-org/members
```

**Задача:**
1. Run all three requests and record the status code and the `WWW-Authenticate` or `X-GitHub-Media-Type` response headers.
2. Write a one-paragraph explanation of why each request failed differently, referencing the specific HTTP semantics of `401` vs `403`.
3. Write a `curl` command that correctly authenticates and retrieves your own user profile (`GET /user`), then extracts your `login`, `public_repos`, and `created_at` fields using `jq`.

---

### Быстрая проверка

4. Extract the HTTP method from a `curl` command. Run: `echo "curl -X POST https://api.example.com/users" | awk '{for(i=1;i<=NF;i++) if ($i=="-X") print $(i+1)}'`

```expected_output
POST
```

hint: Think about how awk can loop through all fields in a line to search for a specific flag like -X and then print the value that follows it.
hint: Use a for loop in awk over NF fields, check if the current field equals "-X", and print the next field using $(i+1).

5. Classify an HTTP status code by family. Run: `python3 -c "code=201; print('2xx' if 200 <= code < 300 else '4xx')"`

```expected_output
2xx
```

hint: Think about how you can use a conditional expression in Python to check which numeric range an HTTP status code falls into.
hint: Use Python's inline ternary syntax with a chained comparison like `200 <= code < 300` to determine the status code family.
