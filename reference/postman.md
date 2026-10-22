# Postman и тестирование API — краткая справка

## CLI Newman

| Command | Description |
|---------|-------------|
| `newman run collection.json` | Запустить коллекцию |
| `newman run collection.json -e environment.json` | С указанием окружения |
| `newman run collection.json -d data.json` | Запуск с использованием набора данных |
| `newman run collection.json -n 3` | Выполнить 3 итерации |
| `newman run collection.json --bail` | Остановиться при первой ошибке |
| `newman run collection.json -r html,cli --reporter-html-export report.html` | Создать HTML-отчёт |
| `newman run url` | Запустить по URL Postman |
| `newman run collection.json --timeout 10000` | Тайм-аут запроса 10 секунд |

## Окружения и переменные

| Context | Set | Get |
|---------|-----|-----|
| Global | `pm.globals.set("key", val)` | `pm.globals.get("key")` |
| Environment | `pm.environment.set("key", val)` | `pm.environment.get("key")` |
| Collection | `pm.collectionVariables.set("key", val)` | `pm.collectionVariables.get("key")` |
| Local (request) | `pm.variables.set("key", val)` | `pm.variables.get("key")` |

## Шаблоны pre-request-скриптов

```javascript
// Set dynamic timestamp
pm.environment.set("timestamp", Date.now());

// Generate random ID
pm.environment.set("userId", Math.floor(Math.random() * 10000));

// Set auth header from env variable
pm.request.headers.add({ key: "Authorization", value: "Bearer " + pm.environment.get("token") });
```

## Test Script Patterns

```javascript
// Status code
pm.test("Status is 200", () => pm.response.to.have.status(200));

// Response time
pm.test("Under 500ms", () => pm.expect(pm.response.responseTime).to.be.below(500));

// Body contains
pm.test("Has id field", () => {
  const body = pm.response.json();
  pm.expect(body).to.have.property("id");
});

// Save token from response
const body = pm.response.json();
pm.environment.set("token", body.access_token);

// Chain requests — set next request
postman.setNextRequest("Get User");

// Skip rest of collection
postman.setNextRequest(null);
```

## Common Assertions

| Assertion | Code |
|-----------|------|
| Status code | `pm.response.to.have.status(200)` |
| Status range | `pm.expect(pm.response.code).to.be.within(200, 299)` |
| Header present | `pm.response.to.have.header("Content-Type")` |
| Header value | `pm.expect(pm.response.headers.get("Content-Type")).to.include("json")` |
| Body string | `pm.expect(pm.response.text()).to.include("success")` |
| JSON field | `pm.expect(pm.response.json().name).to.eql("Alice")` |
| Array length | `pm.expect(pm.response.json().items).to.have.lengthOf(3)` |
| Schema valid | `pm.response.to.have.jsonSchema(schema)` |

## curl Equivalents

| Postman concept | curl equivalent |
|----------------|-----------------|
| GET request | `curl -X GET url` |
| POST JSON | `curl -X POST -H "Content-Type: application/json" -d '{"k":"v"}' url` |
| Auth header | `curl -H "Authorization: Bearer TOKEN" url` |
| Query params | `curl "url?key=val&key2=val2"` |
| Follow redirect | `curl -L url` |
| Verbose | `curl -v url` |
