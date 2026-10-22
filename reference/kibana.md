# Kibana — краткая справка

## KQL (язык запросов Kibana)

| Query | Описание |
|-------|-------------|
| `status: 404` | Точное совпадение поля |
| `status: 4*` | Совпадение по шаблону |
| `status >= 400 and status < 500` | Числовой диапазон |
| `message: "connection refused"` | Поиск фразы |
| `response_time > 1000` | Больше чем |
| `NOT status: 200` | Отрицание условия |
| `service: nginx AND status: error` | Логическое И |
| `env: prod OR env: staging` | Логическое ИЛИ |
| `tags: (error OR warning)` | Несколько значений |
| `_exists_: user.id` | Поле существует |
| `NOT _exists_: error_code` | Поле отсутствует |

## Синтаксис запросов Lucene (альтернатива в Discover — поиск и исследование данных)

| Query | Описание |
|-------|-------------|
| `field:value` | Совпадение термина |
| `field:"exact phrase"` | Phrase match |
| `field:val*` | Шаблон с подстановочными символами |
| `field:[100 TO 200]` | Включающий диапазон |
| `field:{100 TO 200}` | Исключающий диапазон |
| `field:[100 TO *]` | Диапазон без верхней границы |
| `+must -mustnot should` | Сокращённая булева запись |
| `field:(a OR b)` | Несколько терминов |

## ES\|QL (язык запросов Elasticsearch)

```esql
FROM logs-*
| WHERE @timestamp >= NOW() - 1 hour
| WHERE status >= 400
| STATS count = COUNT(*) BY service
| SORT count DESC
| LIMIT 10
```

```esql
FROM metrics-*
| EVAL response_ms = response_time / 1000000
| WHERE response_ms > 1
| STATS avg_ms = AVG(response_ms), p95 = PERCENTILE(response_ms, 95) BY endpoint
```

## Дашборд URLs (Dev Tools Console)

```
# Discover — поиск и исследование данных
/app/discover

# Дашборд
/app/dashboards

# Dev Tools (run Elasticsearch queries directly)
/app/dev_tools

# Stack Monitoring
/app/monitoring
```

## Dev Tools Console Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Execute request |
| `Ctrl+/` | Comment/uncomment |
| `Ctrl+Space` | Autocomplete |
| `Ctrl+I` | Auto-indent |
| `Ctrl+Home` | Jump to start |

## Index Patterns / Data Views

| Action | Location |
|--------|----------|
| Создать data view | Stack Management → Data Views → Create |
| Set default data view | Click star on data view |
| Refresh field list | Edit data view → Refresh |
| Field format override | Edit data view → field → edit format |
