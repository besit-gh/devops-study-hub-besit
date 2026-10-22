---
title: Коллекции и окружения Postman
module: postman
duration_min: 20
difficulty: intermediate
tags: [postman, collections, environments, variables, pre-request, scripts, workflows]
exercises: 4
---

## Обзор
Коллекции группируют связанные API-запросы в иерархию папок с общей конфигурацией. Окружения позволяют переключаться между dev/staging/prod одним выбором: коллекция остаётся той же, а базовые URL и учётные данные меняются. Вместе они сокращают ошибки копирования, превращают документацию API в исполняемые запросы и создают основу автоматизированного тестирования. Pre-request-скрипты позволяют динамически генерировать токены, временные метки и подписи перед каждым запросом.

## Основные понятия

### Коллекции
Коллекция — это именованная группа API-запросов, которые используют общие:
- базовый URL (через переменную коллекции или окружения)
- настройки аутентификации (задаются на уровне коллекции и наследуются всеми запросами)
- pre-request-скрипты (выполняются перед каждым запросом коллекции)
- тестовые скрипты (выполняются после каждого запроса)
- документацию

**Организуйте запросы по ресурсам или рабочим процессам:**
```
MyApp API (collection)
├── Auth
│   ├── POST /auth/login
│   └── POST /auth/refresh
├── Users
│   ├── GET /users
│   ├── POST /users
│   ├── GET /users/:id
│   ├── PATCH /users/:id
│   └── DELETE /users/:id
├── Orders
│   ├── GET /orders
│   └── POST /orders
└── Workflows
    └── Create User → Create Order → Verify
```

### Переменные
Переменные позволяют параметризовать запросы. Области видимости перечислены в порядке приоритета (сначала самая высокая):

```
Local — задаётся в скрипте и доступна только во время текущего запроса
Data — берётся из CSV/JSON-файла при запуске коллекции
Environment — связана с активным окружением (dev, staging, prod)
Collection — хранится в коллекции и доступна всем её запросам
Global — доступна во всех коллекциях (лучше избегать и использовать переменные коллекции)
```

```
Синтаксис ссылки: `{{base_url}}/api/users/{{user_id}}`
```

#### Задание переменных в скриптах
```javascript
// Pre-request-скрипт — задать переменную перед выполнением запроса
pm.environment.set("timestamp", new Date().toISOString());
pm.environment.set("nonce", Math.random().toString(36).substring(2));

// Тестовый скрипт — извлечь значение из ответа и сохранить его
const json = pm.response.json();
pm.environment.set("access_token", json.access_token);
pm.environment.set("user_id", json.user.id);
```

### Окружения
Окружение — это набор пар «ключ — значение». При переключении активного окружения все ссылки `{{variable}}` в коллекции одновременно получают новые значения.

**Пример настройки окружений:**
```
Development:
  base_url = http://localhost:8000
  api_key  = dev-key-abc123
  user_id  = (изначально пусто — заполняется скриптом входа)

Staging:
  base_url = https://staging.api.myapp.com
  api_key  = staging-key-xyz789
  user_id  = (изначально пусто)

Production:
  base_url = https://api.myapp.com
  api_key  = (используйте Postman Vault для секретов, а не обычные переменные окружения)
  user_id  = (изначально пусто)
```

Для чувствительных значений (реальных API-ключей и паролей) используйте **Postman Vault**, а не переменные окружения: значения из Vault не синхронизируются с облаком Postman.

### Настройка аутентификации
Настройте аутентификацию на уровне коллекции, чтобы все запросы наследовали её:

**Коллекция → вкладка Authorization:**
```
Type: Bearer Token
Token: {{access_token}}
```

Запросы наследуют эти настройки, если не переопределяют их. При смене токена на уровне коллекции обновляются все запросы.

**Поток OAuth 2.0 (настраивается в Postman):**
```
Grant Type: Authorization Code
Auth URL: https://auth.myapp.com/oauth/authorize
Access Token URL: https://auth.myapp.com/oauth/token
Client ID: {{client_id}}
Client Secret: {{client_secret}}
Scope: read:users write:users
```

Нажмите «Get New Access Token»: Postman откроет браузер, вы пройдёте аутентификацию, после чего токен сохранится автоматически.

### Pre-request-скрипты
Pre-request-скрипты выполняются перед отправкой запроса. Используйте их для:
- генерации подписей и временных меток для аутентификации
- обновления просроченных токенов
- установки динамических заголовков

```javascript
// Автоматически обновлять просроченный JWT перед каждым запросом
const tokenExpiry = pm.environment.get("token_expiry");
const now = Math.floor(Date.now() / 1000);

if (!tokenExpiry || now >= parseInt(tokenExpiry) - 60) {
    // Токен истёк или истечёт менее чем через 60 секунд — обновить его
    pm.sendRequest({
        url: pm.environment.get("base_url") + "/auth/refresh",
        method: "POST",
        header: { "Content-Type": "application/json" },
        body: {
            mode: "raw",
            raw: JSON.stringify({
                refresh_token: pm.environment.get("refresh_token")
            })
        }
    }, (err, response) => {
        const json = response.json();
        pm.environment.set("access_token", json.access_token);
        pm.environment.set("token_expiry", json.expires_at);
    });
}
```

```javascript
// HMAC-подпись для API, требующего подписывать запросы
const crypto = require('crypto-js');

const timestamp = Date.now().toString();
const body = pm.request.body ? pm.request.body.raw : '';
const secret = pm.environment.get("api_secret");

const signature = crypto.HmacSHA256(timestamp + body, secret).toString();

pm.request.headers.add({ key: "X-Timestamp", value: timestamp });
pm.request.headers.add({ key: "X-Signature", value: signature });
```

### Цепочки запросов
Используйте тестовые скрипты, чтобы передавать данные из одного запроса в следующий:

```javascript
// Запрос 1: POST /auth/login
// Тестовый скрипт:
const json = pm.response.json();
pm.environment.set("access_token", json.access_token);
pm.environment.set("user_id", json.user.id);

// Запрос 2: POST /orders (использует {{user_id}} в теле запроса)
// Тело запроса:
{
  "user_id": "{{user_id}}",
  "items": [{"product_id": "prod_123", "quantity": 2}]
}

// Тестовый скрипт запроса 2:
const order = pm.response.json();
pm.environment.set("order_id", order.id);

// Запрос 3: GET /orders/{{order_id}}
// Использует order_id, установленный запросом 2
```

### Запуск коллекции
Запустите всю коллекцию (или папку) последовательно:
1. Нажмите **Run collection** — откроется Collection Runner
2. Выберите окружение
3. Задайте число итераций и задержку
4. При необходимости загрузите файл данных (CSV/JSON) для запуска с набором входных данных
5. Нажмите **Run** — запросы выполнятся по порядку, результаты тестов будут собраны вместе

```javascript
// Управление потоком выполнения в тестовом скрипте
// Перейти к определённому запросу
postman.setNextRequest("GET /users/:id");

// Остановить запуск коллекции
postman.setNextRequest(null);
```

### Импорт и экспорт
```bash
# Экспортировать коллекцию в JSON
# File → Export → Collection v2.1 → myapp-api.postman_collection.json

# Импортировать из спецификации OpenAPI
# Import → Upload Files → выбрать openapi.yaml
# Postman автоматически создаёт запросы по спецификации

# Импортировать команду curl
# Import → Raw Text → вставить команду curl
# Postman преобразует её в запрос Postman
```

Экспорт коллекции в JSON и фиксация файла в Git превращают документацию API в версионируемый и исполняемый артефакт.

## Примеры

### Сценарий «Вход → использование токена»
```javascript
// Pre-request-скрипт коллекции — убедиться, что токен действителен
const token = pm.environment.get("access_token");
const expiry = pm.environment.get("token_expiry");

if (!token || Date.now() / 1000 >= parseInt(expiry || 0)) {
    pm.sendRequest({
        url: pm.variables.get("base_url") + "/auth/login",
        method: "POST",
        header: [{ key: "Content-Type", value: "application/json" }],
        body: {
            mode: "raw",
            raw: JSON.stringify({
                username: pm.environment.get("username"),
                password: pm.environment.get("password")
            })
        }
    }, (err, res) => {
        if (!err && res.code === 200) {
            const data = res.json();
            pm.environment.set("access_token", data.token);
            pm.environment.set("token_expiry", Math.floor(Date.now() / 1000) + 3600);
        }
    });
}
```

## Практические задания

1. Создайте коллекцию Postman для публичного API (GitHub или JSONPlaceholder). Задайте `{{base_url}}` как переменную коллекции. Создайте два окружения — local и production — с разными базовыми URL. Убедитесь, что переключение окружения меняет адреса запросов без их редактирования.
2. Напишите pre-request-скрипт коллекции, который проверяет, задан ли `access_token` и осталось ли до истечения менее 30 секунд. Если да, вызовите endpoint обновления и измените переменную окружения. Проверьте скрипт, задав время истечения в прошлом.
3. Свяжите три запроса: (1) POST создаёт пользователя и сохраняет `id` из ответа; (2) POST создаёт заказ для этого пользователя, используя `{{user_id}}`; (3) GET получает заказ по `id` из второго шага. Проверьте всю цепочку в Collection Runner.
4. Экспортируйте коллекцию в JSON. Создайте README с описанием переменных, которые нужно задать перед запуском. Добавьте оба файла в Git-репозиторий. Импортируйте коллекцию в новую установку Postman и проверьте её работу.


---

### Быстрая проверка

5. Посчитайте переменные окружения в примере файла. Выполните: `printf 'base_url=https://api.example.com\napi_key=secret123\ntimeout=30\nenv=prod\n' | wc -l`

```expected_output
4
```

Подсказка: посчитайте количество строк, выведенных командой.
Подсказка: передайте вывод `printf` через конвейер в `wc -l`, который считает строки.

6. Извлеките базовый URL из файла переменных окружения. Выполните: `printf 'base_url=https://api.example.com\napi_key=secret123\n' | awk -F= '/^base_url/{print $2}'`

```expected_output
https://api.example.com
```

Подсказка: отфильтруйте строки по имени ключа и извлеките значение после разделителя.
Подсказка: используйте `awk -F=` для задания знака равенства в качестве разделителя, найдите строки с помощью шаблона `^base_url` и выведите второе поле (`$2`).
