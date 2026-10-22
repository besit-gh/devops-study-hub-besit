---
title: Автоматизированные тесты API
module: postman
duration_min: 20
difficulty: intermediate
tags: [postman, newman, testing, assertions, ci, contract-testing, api-testing]
exercises: 4
---

## Обзор

Тестовые скрипты Postman превращают ручное исследование API в автоматические регрессионные тесты. Каждый запрос коллекции может содержать JavaScript-проверки, которые выполняются после получения ответа: проверяют статус-код, заголовки, структуру тела, типы полей и задержку. Поскольку скрипты хранятся внутри JSON коллекции, они попадают в систему контроля версий вместе с ней, запускаются в CI-пайплайнах и доступны другим разработчикам без дополнительной настройки инструментов. Так создаётся надёжный регрессионный контроль на уровне API: он проверяет реальный ответ API, а не то, что, по мнению кода приложения, должно вернуться.

Newman — CLI-инструмент для запуска коллекций Postman вне графического интерфейса: в CI-пайплайнах, по расписанию или как контрольный этап перед развёртыванием. Команда `newman run` возвращает ненулевой код, если хотя бы один тест завершился ошибкой. Поэтому её удобно включать в пайплайн: развернуть приложение в staging, запустить Newman и остановить выпуск, если API перестал соответствовать ожиданиям. Newman also supports multiple reporters (CLI, JUnit, HTML) so the same run produces human-readable and machine-readable output simultaneously — one for engineers triaging failures, one for GitHub's test dashboard.

В цепочке DevOps Postman/Newman используется между развёртыванием и продвижением релиза. Модульные и интеграционные тесты выполняются во время сборки, а Newman запускается после развёртывания приложения в реальном окружении. Он может служить проверкой работоспособности после релиза, проверкой соответствия API спецификации OpenAPI или набором регрессионных тестов. Поэтому он дополняет предыдущие уровни тестирования, а не заменяет их.

---

## Основные понятия

### Основы тестовых скриптов

Тестовые скрипты Postman выполняются после получения ответа. Они находятся на вкладке **Tests** каждого запроса и представляют собой обычный JavaScript, выполняемый в изолированной среде V8. Основная конструкция — `pm.test(name, fn)`: она регистрирует тест с именем, а внутри функции размещаются одна или несколько проверок `pm.expect()` с API в стиле Chai.

```javascript
// Each pm.test() is an independent test case — one failure does not skip others
pm.test("Status code is 200", () => {
    pm.response.to.have.status(200);
});

pm.test("Response time is under 500ms", () => {
    pm.expect(pm.response.responseTime).to.be.below(500);
});

pm.test("Response is JSON", () => {
    pm.response.to.be.json;         // shorthand — checks Content-Type header
});

pm.test("Response has required fields", () => {
    const json = pm.response.json();
    pm.expect(json).to.have.property("id");
    pm.expect(json).to.have.property("email");
    pm.expect(json.email).to.be.a("string").and.include("@");
});
```

**Подводный камень:** `pm.response.to.be.json` проверяет заголовок `Content-Type`, а не возможность разобрать тело ответа как JSON. Если API возвращает JSON с заголовком `Content-Type: text/plain`, проверка даст неверное представление о формате. Чтобы проверить фактический разбор, используйте `pm.response.json()` внутри `try/catch`.

**Важно:** `pm.test` не прерывает выполнение при ошибке — он записывает результат и продолжает работу. Если ошибка одного утверждения должна останавливать остальные проверки, объедините утверждения одного логического блока в один вызов `pm.test`.

---

### Проверки статуса и ответа

Postman предоставляет метаданные ответа через `pm.response`. Ниже приведены наиболее часто используемые проверки:

```javascript
// Status code — by number or reason phrase
pm.response.to.have.status(201);
pm.response.to.have.status("Created");
pm.expect(pm.response.code).to.be.oneOf([200, 201]);   // acceptable range

// Headers — existence and value
pm.response.to.have.header("Content-Type");
pm.expect(pm.response.headers.get("Content-Type")).to.include("application/json");
pm.response.to.have.header("Location");
pm.expect(pm.response.headers.get("Location")).to.match(/\/api\/users\/\d+/);

// Cache and security headers — useful for contract hardening
pm.expect(pm.response.headers.get("Cache-Control")).to.include("no-store");
pm.expect(pm.response.headers.get("X-Content-Type-Options")).to.eql("nosniff");

// Timing
pm.expect(pm.response.responseTime).to.be.below(1000);

// Body — raw text contains
pm.response.to.have.body;                                // body is non-empty
pm.expect(pm.response.text()).to.include("success");
```

| Assertion style | When to use |
|---|---|
| `pm.response.to.have.status(200)` | Readability; Chai-BDD style |
| `pm.expect(pm.response.code).to.eql(200)` | When you need to compose or reuse the value |
| `pm.expect(code).to.be.oneOf([200,201])` | Endpoint returns different codes by path |
| `pm.response.to.have.header("X")` | Just checking presence |
| `pm.response.headers.get("X")` | Checking the actual value |

---

### Проверки JSON

Проверка JSON-ответов — основа большинства наборов API-тестов. `pm.response.json()` разбирает тело ответа; сохраните результат в переменную, прежде чем выполнять несколько проверок.

```javascript
const json = pm.response.json();

// Type checks
pm.expect(json).to.be.an("object");
pm.expect(json.users).to.be.an("array");
pm.expect(json.users.length).to.be.above(0);
pm.expect(json.users).to.have.lengthOf.above(0);       // equivalent, more readable

// Value checks
pm.expect(json.status).to.eql("active");               // deep equality
pm.expect(json.count).to.be.a("number").and.be.above(0);
pm.expect(json.tags).to.include("admin");              // array includes value
pm.expect(json.created_at).to.match(/^\d{4}-\d{2}-\d{2}T/);  // ISO date format

// Nested fields
pm.expect(json.user.address.country).to.eql("IL");

// Array item validation — fails on first bad item; add label for diagnosis
json.users.forEach((user, index) => {
    pm.expect(user, `users[${index}] missing id`).to.have.property("id");
    pm.expect(user, `users[${index}] missing email`).to.have.property("email");
    pm.expect(user.role, `users[${index}].role invalid`).to.be.oneOf(["admin", "viewer", "editor"]);
});
```

**Проверка схемы с Ajv (предпочтительнее tv4):** Postman включает `tv4` для совместимости со старым кодом, но `tv4` не поддерживает JSON Schema draft-07 и новее. Для `format: "email"`, `nullable` или `anyOf` используйте Ajv, который также входит в комплект.

```javascript
// Ajv is available as a global in Postman sandbox
const Ajv = require("ajv");
const ajv = new Ajv();

const schema = {
    type: "object",
    required: ["id", "name", "email"],
    properties: {
        id:    { type: "integer", minimum: 1 },
        name:  { type: "string", minLength: 1 },
        email: { type: "string", format: "email" },
        role:  { type: "string", enum: ["admin", "viewer", "editor"] }
    },
    additionalProperties: false   // fail if API adds undocumented fields
};

pm.test("Response matches schema", () => {
    const valid = ajv.validate(schema, pm.response.json());
    pm.expect(valid, ajv.errorsText()).to.be.true;
});
```

**`additionalProperties: false` — решение на уровне контракта.** Проверка завершится ошибкой, если API добавит новые, не описанные в схеме поля. Включайте её в контрактных тестах; в smoke-тестах, где важнее обратная совместимость, строгую проверку можно отключить.

---

### Проверка ошибочных сценариев

Тесты ошибочных сценариев не менее важны, чем проверки успешного пути. Они подтверждают, что API возвращает структурированные ошибки (а не HTML-страницы 500 или трассировки стека), правильные коды статуса и полезные сообщения.

```javascript
// --- In a request with a missing required field ---

pm.test("Returns 400 for missing email", () => {
    pm.response.to.have.status(400);
});

pm.test("Error body is JSON, not an HTML error page", () => {
    // APIs under frameworks sometimes return HTML on unhandled errors
    pm.expect(pm.response.headers.get("Content-Type")).to.include("application/json");
    const json = pm.response.json();           // will throw if body is not valid JSON
    pm.expect(json).to.have.property("message");
    pm.expect(json.message).to.be.a("string").and.have.length.above(0);
});

pm.test("Error message references the missing field", () => {
    const json = pm.response.json();
    pm.expect(json.message.toLowerCase()).to.include("email");
});

// --- In a request with a duplicate resource ---

pm.test("Returns 409 for duplicate email", () => {
    pm.response.to.have.status(409);
});

pm.test("409 body has error code field", () => {
    const json = pm.response.json();
    pm.expect(json).to.have.property("error_code");
    pm.expect(json.error_code).to.eql("DUPLICATE_EMAIL");
});
```

**Не проверяйте ошибки тем же запросом, которым проверяете успешный сценарий.** Создайте в коллекции отдельную папку, например `Error Cases / POST /users`, где каждый запрос заранее настроен на некорректные входные данные. Так коллекция становится самодокументируемой, а Newman может запускать набор ошибочных сценариев отдельно.

---

### Переменные, pre-request-скрипты и цепочки запросов

Реальные наборы API-тестов должны связывать запросы в цепочку: создать ресурс, проверить его, затем удалить. Области видимости переменных и pre-request-скрипты Postman позволяют это реализовать.

| Scope | Set with | Read with | Lifetime |
|---|---|---|---|
| Global | `pm.globals.set()` | `pm.globals.get()` | Until explicitly cleared |
| Environment | `pm.environment.set()` | `pm.environment.get()` | Active environment session |
| Collection | `pm.collectionVariables.set()` | `pm.collectionVariables.get()` | Collection run |
| Local | `pm.variables.set()` | `pm.variables.get()` | Current request only |

```javascript
// In the Tests tab of POST /users — capture the created ID
pm.test("User created successfully", () => {
    pm.response.to.have.status(201);
    const json = pm.response.json();
    pm.expect(json).to.have.property("id");
    // Store for subsequent requests in this run
    pm.collectionVariables.set("created_user_id", json.id);
});

// In the next request (GET /users/{{created_user_id}}) — verify the resource exists
pm.test("Fetched user matches created user", () => {
    const json = pm.response.json();
    pm.expect(json.id).to.eql(pm.collectionVariables.get("created_user_id"));
});
```

**Используйте `collectionVariables`, а не `environment`, для значений, созданных во время тестового запуска**, например ID из ответа POST. Переменные окружения предназначены для конфигурации (базовых URL и учётных данных). Смешивание этих типов создаёт гонку, если несколько экземпляров Newman используют один файл окружения.

---

### Организация тестов и сообщения об ошибках

Группировка утверждений и понятные подписи отличают сообщение `AssertionError: expected 0 to be above 0` от гораздо более полезного `users[3].id: expected 0 to be above 0`.

```javascript
// Use the second argument to pm.expect() as a label — it appears in failure output
pm.test("User object is valid", () => {
    const user = pm.response.json();
    pm.expect(user.id,         "id should be a positive integer").to.be.a("number").above(0);
    pm.expect(user.email,      "email should match RFC format").to.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/);
    pm.expect(user.created_at, "created_at should be ISO 8601").to.match(/^\d{4}-\d{2}-\d{2}T/);
    pm.expect(user.role,       "role should be a known enum value").to.be.oneOf(["admin", "viewer", "editor"]);
});

// Split into multiple pm.test() blocks when the concepts are distinct —
// a failure in one does not mask failures in others
pm.test("Identity fields are present and typed correctly", () => {
    const json = pm.response.json();
    pm.expect(json.id).to.be.a("number").above(0);
    pm.expect(json.email).to.be.a("string");
});

pm.test("Timestamps are ISO 8601", () => {
    const json = pm.response.json();
    pm.expect(json.created_at).to.match(/^\d{4}-\d{2}-\d{2}T/);
    pm.expect(json.updated_at).to.match(/^\d{4}-\d{2}-\d{2}T/);
});
```

---

### Newman — запуск из командной строки

Newman запускает JSON-файл коллекции из командной строки. Если все проверки прошли, он возвращает `0`; при любой ошибке — ненулевой код. Поэтому его удобно использовать как условие прохождения CI.

```bash
# Install globally (or as a local devDependency — prefer local in CI)
npm install -g newman
npm install -g newman-reporter-htmlextra   # richer HTML output

# Minimal run
newman run myapp-api.postman_collection.json

# With environment file (staging config: base_url, api_key, etc.)
newman run myapp-api.postman_collection.json \
  -e staging.postman_environment.json

# Override a single env variable at runtime — useful for feature branch URLs
newman run myapp-api.postman_collection.json \
  -e staging.postman_environment.json \
  --env-var "base_url=https://pr-142.staging.myapp.com"

# Multiple reporters: CLI for terminal, JUnit for CI, HTML for humans
newman run myapp-api.postman_collection.json \
  -e staging.postman_environment.json \
  --reporters cli,junit,htmlextra \
  --reporter-junit-export results/newman.xml \
  --reporter-htmlextra-export results/report.html

# Run only a specific folder (e.g., smoke tests)
newman run myapp-api.postman_collection.json \
  --folder "Smoke Tests"

# Data-driven: iterate each row of a CSV as a separate variable set
newman run myapp-api.postman_collection.json \
  -d test-users.csv \
  --iteration-count 5

# Stop on first failure — useful as a deployment gate
newman run myapp-api.postman_collection.json \
  -e staging.postman_environment.json \
  --bail

# Check exit code explicitly in shell scripts
newman run myapp-api.postman_collection.json -e staging.postman_environment.json
if [ $? -ne 0 ]; then
  echo "API tests failed — blocking promotion" && exit 1
fi
```

| Newman flag | Purpose |
|---|---|
| `-e` | Environment file |
| `-d` | Data file (CSV or JSON) for data-driven runs |
| `--folder` | Run only a named folder |
| `--env-var` | Override a single variable at runtime |
| `--bail` | Stop after first test failure |
| `--timeout-request` | Per-request timeout in ms |
| `--iteration-count` | How many times to iterate the collection |
| `--reporters` | Comma-separated list: `cli`, `junit`, `htmlextra` |

**Newman не сохраняет изменения переменных обратно в файл окружения.** Переменные, заданные через `pm.environment.set()` во время запуска, существуют только в памяти текущего процесса. Если нужно передать значение (например, токен) следующему шагу после `newman run`, сохраните его в файл подходящим способом или используйте pre-request-скрипт, который получает новый токен при старте.

---

### Newman в CI (GitHub Actions)

```yaml
# .github/workflows/api-tests.yml
name: API regression tests

on:
  push:
    branches: [main, staging]
  workflow_dispatch:          # allow manual trigger

jobs:
  api-tests:
    runs-on: ubuntu-24.04
    needs: deploy             # gate: run after deployment completes

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install Newman and reporters
        # Install locally so the version is pinned via package.json
        run: |
          npm ci
          # Or globally if no package.json:
          # npm install -g newman newman-reporter-htmlextra

      - name: Run API tests
        run: |
          npx newman run postman/myapp-api.postman_collection.json \
            -e postman/staging.postman_environment.json \
            --env-var "base_url=${{ vars.STAGING_URL }}" \
            --reporters cli,junit,htmlextra \
            --reporter-junit-export results/newman.xml \
            --reporter-htmlextra-export results/report.html \
            --timeout-request 5000 \
            --bail
        # Non-zero exit from Newman will fail this step and the job

      - name: Publish JUnit results to GitHub test dashboard
        uses: mikepenz/action-junit-report@v4
        if: always()          # report even when tests fail
        with:
          report_paths: results/newman.xml
          check_name: "Newman API Tests"

      - name: Upload HTML report as artifact
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: newman-report-${{ github.run_id }}
          path: results/report.html
          retention-days: 14
```

**`if: always()` обязателен для шагов публикации отчётов.** Без него GitHub Actions пропустит загрузку и публикацию, если Newman завершится с ненулевым кодом. В итоге отчёт будет недоступен именно тогда, когда он особенно нужен.

---

### Контрактное тестирование API

Контрактное тестирование проверяет соответствие развёрнутого API спецификации OpenAPI. Оно обнаруживает расхождения реализации с описанным контрактом: переименование поля, удаление обязательного свойства или изменение типа.

```bash
# portman generates a Postman collection with contract tests from an OpenAPI spec
npm install -g @apideck/portman

portman \
  --oasFile openapi.yaml \
  --localPostmanCollection myapp.postman_collection.json \
  --cliOptionsFile portman-config.yml

# Run the generated contract collection
newman run myapp.postman_collection.json \
  -e staging.postman_environment.json
```

Ручная проверка контракта с Ajv: добавьте этот скрипт к любому запросу, чтобы проверять схему развёрнутого API:

```javascript
// This pattern is useful for endpoints not covered by portman
const Ajv = require("ajv");
const ajv = new Ajv({ allErrors: true });   // report all violations, not just the first

const userListSchema = {
    type: "array",
    items: {
        type: "object",
        required: ["id", "name", "email"],
        properties: {
            id:    { type: "integer", minimum: 1 },
            name:  { type: "string",  minLength: 1 },
            email: { type: "string" }
        },
        additionalProperties: false   // strict: undocumented fields fail the contract
    }
};

pm.test("GET /users response matches OpenAPI schema", () => {
    const valid = ajv.validate(userListSchema, pm.response.json());
    // ajv.errorsText() gives a human-readable list of all violations
    pm.expect(valid, ajv.errorsText()).to.be.true;
});
```

**Контрактные и smoke-тесты по-разному относятся к `additionalProperties`.** Smoke-тесты должны быть гибкими и допускать новые поля, если они не нарушают совместимость. Контрактные тесты должны быть строгими и падать при появлении неописанных полей, поскольку это указывает на расхождение со спецификацией. Используйте для этих режимов разные папки или коллекции.

---

### Базовые показатели производительности

Скрипты Postman могут отслеживать динамику времени ответа между запусками, сохраняя скользящее среднее в переменных окружения.

```javascript
// Assert against a fixed SLA — simplest form
pm.test("Response time within SLA (300ms)", () => {
    pm.expect(pm.response.responseTime).to.be.below(300);
});

// Assert against a dynamic baseline — detects regressions relative to history
pm.test("Response time has not regressed by more than 50%", () => {
    const baseline = pm.environment.get("baseline_response_time");
    if (baseline) {
        // 1.5× the rolling average is the regression threshold
        const threshold = parseInt(baseline) * 1.5;
        pm.expect(pm.response.responseTime,
            `Regression: ${pm.response.responseTime}ms vs baseline ${baseline}ms`)
            .to.be.below(threshold);
    }
});

// Update the rolling average (last 10 samples) — runs regardless of the test above
(function updateBaseline() {
    const raw = pm.environment.get("response_time_samples") || "[]";
    const samples = JSON.parse(raw);
    samples.push(pm.response.responseTime);
    if (samples.length > 10) samples.shift();   // keep window at 10
    const avg = Math.ceil(samples.reduce((a, b) => a + b, 0) / samples.length);
    pm.environment.set("response_time_samples", JSON.stringify(samples));
    pm.environment.set("baseline_response_time", avg);
})();
```

**Проверки производительности в Newman — не нагрузочные тесты.** Newman отправляет по одному запросу за раз. Используйте эти проверки для обнаружения десятикратного ухудшения (например, из-за запроса N+1 после развёртывания), а не для измерения пропускной способности при параллельной нагрузке. Для нагрузочного тестирования подойдут k6 или Gatling.

---

## Примеры

### Пример 1. Полный набор CRUD-тестов для `/api/users`

**Подготовка:** экспортируйте коллекцию Postman с четырьмя запросами в папке `Users CRUD`: `POST /users`, `GET /users/:id`, `PUT /users/:id`, `DELETE /users/:id`. Каждый запрос использует `{{base_url}}` из файла окружения.

**staging.postman_environment.json:**
```json
{
  "id": "env-staging",
  "name": "staging",
  "values": [
    { "key": "base_url", "value": "https://staging.myapp.com", "enabled": true },
    { "key": "api_key",  "value": "test-api-key-abc123",         "enabled": true }
  ]
}
```

**POST /users — вкладка Tests:**
```javascript
pm.test("201 Created", () => pm.response.to.have.status(201));

pm.test("Location header points to new resource", () => {
    pm.response.to.have.header("Location");
    pm.expect(pm.response.headers.get("Location")).to.match(/\/api\/users\/\d+/);
});

pm.test("Response body has id, name, email", () => {
    const json = pm.response.json();
    pm.expect(json.id).to.be.a("number").above(0);
    pm.expect(json.name).to.be.a("string").and.have.length.above(0);
    pm.expect(json.email).to.include("@");
    // Persist for downstream requests
    pm.collectionVariables.set("user_id", json.id);
    pm.collectionVariables.set("user_email", json.email);
});
```

**GET /users/{{user_id}} — вкладка Tests:**
```javascript
pm.test("200 OK and email matches created user", () => {
    pm.response.to.have.status(200);
    const json = pm.response.json();
    pm.expect(json.email).to.eql(pm.collectionVariables.get("user_email"));
});
```

**DELETE /users/{{user_id}} — вкладка Tests:**
```javascript
pm.test("204 No Content on delete", () => pm.response.to.have.status(204));
pm.test("Body is empty after delete", () => {
    pm.expect(pm.response.text()).to.have.lengthOf(0);
});
```

**Run it:**
```bash
newman run users-crud.postman_collection.json \
  -e staging.postman_environment.json \
  --reporters cli,junit \
  --reporter-junit-export results/users-crud.xml

# Verify: exit 0 = all pass
echo "Exit code: $?"
```

---

### Пример 2. Коллекция ошибочных сценариев для `POST /users`

**Подготовка:** создайте папку `POST /users — Error Cases` с тремя запросами, каждый из которых заранее настроен на своё некорректное тело.

**Запрос 1: отсутствует email — вкладка Tests:**
```javascript
pm.test("400 for missing email", () => pm.response.to.have.status(400));
pm.test("Error body is JSON with message field referencing email", () => {
    pm.expect(pm.response.headers.get("Content-Type")).to.include("application/json");
    const json = pm.response.json();
    pm.expect(json.message).to.be.a("string").and.include("email");
});
```

**Запрос 2: повторяющийся email — вкладка Tests:**
```javascript
pm.test("409 Conflict for duplicate email", () => pm.response.to.have.status(409));
pm.test("error_code is DUPLICATE_EMAIL", () => {
    pm.expect(pm.response.json().error_code).to.eql("DUPLICATE_EMAIL");
});
```

**Запрос 3: некорректное тело JSON — вкладка Tests:**
```javascript
pm.test("400 for unparseable body", () => pm.response.to.have.status(400));
pm.test("Response is JSON even for malformed input", () => {
    pm.expect(pm.response.headers.get("Content-Type")).to.include("application/json");
});
```

**Запуск только ошибочных сценариев:**
```bash
newman run users-api.postman_collection.json \
  -e staging.postman_environment.json \
  --folder "POST /users — Error Cases" \
  --reporters cli
```

---

### Пример 3. Тесты входа с данными из CSV

**test-credentials.csv:**
```csv
username,password,expected_status
admin@myapp.com,correct-password,200
admin@myapp.com,wrong-password,401
nonexistent@myapp.com,any-password,401
admin@myapp.com,,400
```

**POST /auth/login — вкладка Tests:**
```javascript
// pm.iterationData accesses the current CSV row
pm.test(`Status is ${pm.iterationData.get("expected_status")}`, () => {
    pm.response.to.have.status(parseInt(pm.iterationData.get("expected_status")));
});

// Only validate token presence on expected 200s
if (pm.iterationData.get("expected_status") === "200") {
    pm.test("Token is returned on successful login", () => {
        const json = pm.response.json();
        pm.expect(json).to.have.property("token");
        pm.expect(json.token).to.be.a("string").and.have.length.above(10);
    });
}
```

**Run:**
```bash
newman run auth.postman_collection.json \
  -e staging.postman_environment.json \
  -d test-credentials.csv \
  --reporters cli,htmlextra \
  --reporter-htmlextra-export results/auth-report.html
```

**Проверка:** HTML-отчёт показывает 4 итерации. Для строки с ответом 200 отображается проверка токена, для остальных она пропускается.

---

### Пример 4. Newman как условие допуска к развёртыванию в GitHub Actions

```yaml
# .github/workflows/deploy-and-test.yml
name: Deploy to staging and run API tests

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to staging
        run: ./scripts/deploy.sh staging
        env:
          DEPLOY_KEY: ${{ secrets.DEPLOY_KEY }}

  api-tests:
    runs-on: ubuntu-24.04
    needs: deploy     # only run after successful deploy

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install Newman
        run: npm install -g newman newman-reporter-htmlextra

      - name: Run smoke tests
        run: |
          newman run postman/myapp-api.postman_collection.json \
            -e postman/staging.postman_environment.json \
            --env-var "base_url=${{ vars.STAGING_URL }}" \
            --folder "Smoke Tests" \
            --reporters cli,junit,htmlextra \
            --reporter-junit-export results/smoke.xml \
            --reporter-htmlextra-export results/smoke-report.html \
            --timeout-request 5000 \
            --bail
        # newman exits non-zero on failure → job fails → no promotion

      - name: Publish test results
        uses: mikepenz/action-junit-report@v4
        if: always()
        with:
          report_paths: results/smoke.xml
          check_name: "Staging API Smoke Tests"
          fail_on_failure: true   # mark the check as failed in the PR UI

      - name: Upload HTML report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: smoke-report-${{ github.run_id }}
          path: results/smoke-report.html
          retention-days: 7
```

**Verify it worked:**
- Успешный запуск: задача `api-tests` отмечена зелёным; проверка JUnit отображается в PR; артефакт можно скачать.
- Неуспешный запуск: Newman возвращает ненулевой код; задача отмечена красным; проверка JUnit показывает упавшие тесты; HTML-артефакт всё равно загружается благодаря `if: always()`.

---

## Практические задания

**Задание 1. Напишите полный тестовый скрипт для `POST /users`**

Используя реальный или тестовый API (например, `https://jsonplaceholder.typicode.com/users` или локально запущенный сервис), напишите тестовый скрипт Postman, который проверяет все перечисленные условия. Не копируйте готовый код из раздела «Основные понятия»:
- Код статуса равен 201 (или 200, если используемый API возвращает этот код для POST).
- Заголовок `Content-Type` содержит `application/json`.
- Тело ответа содержит `id` (положительное целое число), `name` (непустую строку) и `email` (с символом `@`).
- Время ответа меньше 800 мс.
- Сохраните полученный `id` в переменную коллекции `created_id`.

Запустите запрос в интерфейсе Postman и убедитесь, что все тесты пройдены в панели результатов.

---

**Задание 2. Проверьте ошибочные сценарии для `POST /users`**

Создайте в той же коллекции два дополнительных запроса для проверки ошибок:
1. Отправьте POST без поля `email`. Проверьте, что статус равен 400, тело имеет формат JSON и содержит непустое строковое поле `message`.
2. Отправьте POST с некорректным форматом `email` (например, `"email": "notanemail"`). Проверьте, что статус равен 400 или 422 и ответ не является HTML-страницей (проверьте `Content-Type`).

Затем одним предложением объясните, *почему* нужно проверять `Content-Type: application/json` и в ошибочных ответах, а не только в успешных.

---

**Задание 3. Запустите коллекцию через Newman и проверьте код завершения**

1. Экспортируйте коллекцию и окружение из Postman в файлы JSON.
2. Установите Newman глобально: `npm install -g newman`.
3. Запустите коллекцию с нужным окружением. Изучите вывод CLI и найдите количество успешных и неуспешных проверок.
4. Намеренно сломайте одно утверждение (например, замените `below(800)` на `below(1)`). Повторно экспортируйте и запустите коллекцию. Убедитесь, что код завершения ненулевой: `echo $?`.
5. Добавьте `--reporters cli,junit --reporter-junit-export results/test.xml` и изучите созданный XML. Найдите элемент `<testcase>` для упавшего теста.

**Цель:** понять значение кода завершения Newman для CI-конвейера и изучить структуру JUnit XML.

---

**Задание 4. Добавьте Newman в workflow GitHub Actions**

В существующий файл workflow с задачей `deploy` добавьте задачу `api-tests`, которая:
1. Depend on `deploy` using `needs`
2. Устанавливает Newman.
3. Запускает коллекцию с отчётчиком JUnit и сохраняет результат в `results/api.xml`.
4. Публикует результаты через `mikepenz/action-junit-report@v4` с `if: always()`.
5. Загружает XML как артефакт через `actions/upload-artifact@v4` с `if: always()`.

Отправьте коммит, который намеренно проваливает тест (например, проверяет несуществующее поле). В интерфейсе GitHub Actions убедитесь, что задача отмечена красным, отчёт о тестах появился во вкладке проверок PR, а артефакт загружен несмотря на ошибку.

---

### Быстрая проверка

6. Посчитайте проверки в примере скрипта Postman. Выполните: `printf 'pm.test("Status 200", fn1);\npm.test("Has id", fn2);\npm.test("Content-Type", fn3);\n' | grep -c 'pm.test'`

```expected_output
3
```

Подсказка: найдите в тексте нужный шаблон и подсчитайте число совпадающих строк.
Подсказка: используйте `grep -c`, чтобы посчитать строки с `pm.test` в тексте, переданном через конвейер.

7. Извлеките ожидаемый код статуса из фрагмента теста. Выполните: `echo 'pm.response.to.have.status(201);' | sed 's/.*status(\([0-9]*\)).*/\1/'`

```expected_output
201
```

Подсказка: используйте потоковый редактор, чтобы найти шаблон и извлечь из совпадения только нужную часть.
Подсказка: используйте в `sed` группу захвата `\([0-9]*\)`: она захватывает цифры внутри `status()`, а `\1` в замене ссылается на захваченную группу.
