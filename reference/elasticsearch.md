# Elasticsearch — краткая справка

## Кластер и состояние

| API Call | Description |
|----------|-------------|
| `GET /_cluster/health` | Состояние кластера (green/yellow/red) |
| `GET /_cluster/stats` | Статистика всего кластера |
| `GET /_nodes/stats` | Статистика по узлам |
| `GET /_cat/nodes?v` | Список узлов и их ролей |
| `GET /_cat/shards?v` | Распределение шардов |
| `GET /_cat/allocation?v` | Использование диска по узлам |
| `GET /_cat/pending_tasks` | Ожидающие задачи кластера |

## Управление индексами

| API Call | Description |
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

| API Call | Description |
|----------|-------------|
| `PUT /index/_doc/ID` `{ ... }` | Index document with ID |
| `POST /index/_doc` `{ ... }` | Index with auto-generated ID |
| `GET /index/_doc/ID` | Retrieve document |
| `POST /index/_update/ID` `{ "doc": { ... } }` | Partial update |
| `DELETE /index/_doc/ID` | Delete document |
| `POST /index/_delete_by_query` `{ "query": { ... } }` | Delete by query |
| `GET /index/_count` `{ "query": { ... } }` | Count matching docs |

## Search Queries

| Query | Description |
|-------|-------------|
| `{ "query": { "match_all": {} } }` | All documents |
| `{ "query": { "match": { "field": "text" } } }` | Full-text match |
| `{ "query": { "term": { "field": "exact" } } }` | Exact keyword match |
| `{ "query": { "range": { "field": { "gte": 10 } } } }` | Range filter |
| `{ "query": { "bool": { "must": [...], "filter": [...] } } }` | Boolean query |
| `{ "query": { "wildcard": { "field": "val*" } } }` | Шаблон с подстановочными символами |
| `{ "from": 0, "size": 20, "query": { ... } }` | Pagination |
| `{ "sort": [{ "field": "desc" }], "query": { ... } }` | Sort results |

## Aggregations

| Aggregation | Description |
|-------------|-------------|
| `{ "aggs": { "by_field": { "terms": { "field": "status" } } } }` | Count by field value |
| `{ "aggs": { "avg_price": { "avg": { "field": "price" } } } }` | Average |
| `{ "aggs": { "total": { "sum": { "field": "amount" } } } }` | Sum |
| `{ "aggs": { "over_time": { "date_histogram": { "field": "@timestamp", "calendar_interval": "day" } } } }` | Time histogram |

## Index Lifecycle (ILM)

| API Call | Description |
|----------|-------------|
| `GET /_ilm/policy` | List ILM policies |
| `PUT /_ilm/policy/myPolicy` `{ "policy": { ... } }` | Create ILM policy |
| `GET /index/_ilm/explain` | Show index ILM status |
| `POST /index/_ilm/retry` | Retry failed ILM step |

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
