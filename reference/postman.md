# Postman и тестирование API — краткая справка

## CLI Newman

| Команда | Описание |
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

| Контекст | Установить | Получить |
|---------|-----|-----|
| Global | `pm.globals.set("key", val)` | `pm.globals.get("key")` |
| Environment | `pm.environment.set("key", val)` | `pm.environment.get("key")` |
| Collection | `pm.collectionVariables.set("key", val)` | `pm.collectionVariables.get("key")` |
| Local (request) | `pm.variables.set("key", val)` | `pm.variables.get("key")` |

## Шаблоны pre-request-скриптов

```javascript
// Установить dynamic timestamp
pm.environment.set("timestamp", Date.now());

// Сгенерировать случайный ID
pm.environment.set("userId", Math.floor(Math.random() * 10000));

// Установить auth header from env variable
pm.request.headers.add({ key: "Authorization", value: "Bearer " + pm.environment.get("token") });
```

## Шаблоны тестовых скриптов

```javascript
// Код состояния
pm.test("Status is 200", () => pm.response.to.have.status(200));

// Время ответа
pm.test("Under 500ms", () => pm.expect(pm.response.responseTime).to.be.below(500));

// Содержимое тела ответа
pm.test("Has id field", () => {
  const body = pm.response.json();
  pm.expect(body).to.have.property("id");
});

// Сохранить токен из ответа
const body = pm.response.json();
pm.environment.set("token", body.access_token);

// Связать запросы — задать следующий запрос
postman.setNextRequest("Получить User");

// Пропустить оставшуюся часть коллекции
postman.setNextRequest(null);
```

## Common Проверкаs

| Проверка | Code |
|-----------|------|
| Код состояния | `pm.response.to.have.status(200)` |
| Диапазон кодов состояния | `pm.expect(pm.response.code).to.be.within(200, 299)` |
| Наличие заголовка | `pm.response.to.have.header("Content-Type")` |
| Значение заголовка | `pm.expect(pm.response.headers.get("Content-Type")).to.include("json")` |
| Строка в теле ответа | `pm.expect(pm.response.text()).to.include("success")` |
| Поле JSON | `pm.expect(pm.response.json().name).to.eql("Alice")` |
| Длина массива | `pm.expect(pm.response.json().items).to.have.lengthOf(3)` |
| Схема корректна | `pm.response.to.have.jsonSchema(schema)` |

## curl Equivalents

| Понятие Postman | Эквивалент в curl |
|----------------|-----------------|
| GET-запрос | `curl -X GET url` |
| POST JSON | `curl -X POST -H "Content-Type: application/json" -d '{"k":"v"}' url` |
| Заголовок авторизации | `curl -H "Authorization: Bearer TOKEN" url` |
| Параметры запроса | `curl "url?key=val&key2=val2"` |
| Следовать перенаправлению | `curl -L url` |
| Подробный вывод | `curl -v url` |
