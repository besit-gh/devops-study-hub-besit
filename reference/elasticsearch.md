# Elasticsearch — краткая справка

## Кластер и состояние

| Вызов API | Описание |
|----------|-------------|
| `GET /_cluster/health` | Состояние кластера (green/yellow/red) |
| `GET /_cluster/stats` | Статистика всего кластера |
| `GET /_nodes/stats` | Статистика по узлам |
| `GET /_cat/nodes?v` | Список узлов и их ролей |
| `GET /_cat/shards?v` | Распределение шардов |
| `GET /_cat/allocation?v` | Использование диска по узлам |
| `GET /_cat/pending_tasks` | Ожидающие задачи кластера |

## Управление индексами

| Вызов API | Описание |
|----------|-------------|
| `GET /_cat/indices?v` | Список индексов со статистикой |
| `PUT /myindex` | Создать индекс |
| `PUT /myindex` `{ "settings": { "number_of_shards": 1 } }` | Создать индекс с настройками |
| `DELETE /myindex` | Удалить индекс |
| `GET /myindex/_settings` | Показать настройки индекса |
| `GET /myindex/_mapping` | Показать mapping индекса |
| `POST /myindex/_open` | Открыть закрытый индекс |
| `POST /myindex/_close` | Закрыть индекс |
| `POST /myindex/_refresh` | Принудительно обновить индекс, чтобы документы стали доступны для поиска |
| `POST /myindex/_flush` | Принудительно сбросить данные на диск |
| `POST /_aliases` `{ "actions": [...] }` | Управлять псевдонимами |

## CRUD-операции с документами

| Вызов API | Описание |
|----------|-------------|
| `PUT /index/_doc/ID` `{ ... }` | Индексировать документ с указанным ID |
| `POST /index/_doc` `{ ... }` | Индексировать документ с автоматически созданным ID |
| `GET /index/_doc/ID` | Получить документ |
| `POST /index/_update/ID` `{ "doc": { ... } }` | Частично обновить документ |
| `DELETE /index/_doc/ID` | Удалить документ |
| `POST /index/_delete_by_query` `{ "query": { ... } }` | Удалить документы по запросу |
| `GET /index/_count` `{ "query": { ... } }` | Подсчитать совпавшие документы |

## Search Queries

| Запрос | Описание |
|-------|-------------|
| `{ "query": { "match_all": {} } }` | Все документы |
| `{ "query": { "match": { "field": "text" } } }` | Полнотекстовый поиск |
| `{ "query": { "term": { "field": "exact" } } }` | Точное совпадение по ключевому слову |
| `{ "query": { "range": { "field": { "gte": 10 } } } }` | Фильтр по диапазону |
| `{ "query": { "bool": { "must": [...], "filter": [...] } } }` | Булев запрос |
| `{ "query": { "wildcard": { "field": "val*" } } }` | Шаблон с подстановочными символами |
| `{ "from": 0, "size": 20, "query": { ... } }` | Пагинация |
| `{ "sort": [{ "field": "desc" }], "query": { ... } }` | Сортировать результаты |

## Агрегацияs

| Агрегация | Описание |
|-------------|-------------|
| `{ "aggs": { "by_field": { "terms": { "field": "status" } } } }` | Подсчитать документы по значению поля |
| `{ "aggs": { "avg_price": { "avg": { "field": "price" } } } }` | Среднее значение |
| `{ "aggs": { "total": { "sum": { "field": "amount" } } } }` | Сумма |
| `{ "aggs": { "over_time": { "date_histogram": { "field": "@timestamp", "calendar_interval": "day" } } } }` | Гистограмма по времени |

## Index Lifecycle (ILM)

| Вызов API | Описание |
|----------|-------------|
| `GET /_ilm/policy` | Список политик ILM |
| `PUT /_ilm/policy/myPolicy` `{ "policy": { ... } }` | Создать политику ILM |
| `GET /index/_ilm/explain` | Показать состояние ILM для индекса |
| `POST /index/_ilm/retry` | Повторить неудачный шаг ILM |

## curl Shorthand

```bash
# Set base URL
ES="http://localhost:9200"

curl -X GET "$ES/_cluster/health?pretty"
curl -X GET "$ES/_cat/indices?v&s=index"
curl -X POST "$ES/myindex/_search?pretty" \
  -H "Content-Type: application/json" \
  -d '{"query":{"match_all":{}}}'
```
