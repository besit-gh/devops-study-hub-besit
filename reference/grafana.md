# Grafana — краткая справка

## grafana-cli

| Команда | Описание |
|---------|-------------|
| `grafana-cli plugins list-remote` | Список доступных плагинов |
| `grafana-cli plugins install plugin-id` | Установить плагин |
| `grafana-cli plugins ls` | Список установленных плагинов |
| `grafana-cli plugins remove plugin-id` | Удалить плагин |
| `grafana-cli plugins update-all` | Обновить все плагины |
| `grafana-cli admin reset-admin-password newpass` | Сбросить пароль администратора |

## HTTP API (примеры curl)

```bash
GRAFANA="http://admin:password@localhost:3000"

# Health check
curl "$GRAFANA/api/health"

# Список дашбордов
curl "$GRAFANA/api/search?type=dash-db"

# Получить дашборд по UID
curl "$GRAFANA/api/dashboards/uid/DASHBOARD_UID"

# Импортировать дашборд
curl -X POST "$GRAFANA/api/dashboards/import" \
  -H "Content-Type: application/json" \
  -d @dashboard.json

# Список источников данных
curl "$GRAFANA/api/datasources"

# Список правил оповещения
curl "$GRAFANA/api/v1/provisioning/alert-rules"

# Silence an alert
curl -X POST "$GRAFANA/api/alertmanager/grafana/api/v2/silences" \
  -H "Content-Type: application/json" \
  -d '{"matchers":[{"name":"alertname","value":"MyAlert","isRegex":false}],"startsAt":"...","endsAt":"..."}'
```

## Подготовка дашбордов (YAML)

```yaml
apiVersion: 1
providers:
  - name: default
    type: file
    options:
      path: /etc/grafana/dashboards
      foldersFromFilesStructure: true
```

## Настройка источников данных (YAML)

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
  - name: Loki
    type: loki
    url: http://loki:3100
```

## Common Переменнаяs in Dashboards

| Переменная | Описание |
|----------|-------------|
| `$__timeFilter(column)` | SQL time filter from dashboard range |
| `$__interval` | Auto-calculated interval |
| `$__rate_interval` | Recommended for rate() queries |
| `$__from` | Dashboard from time (ms) |
| `$__to` | Dashboard to time (ms) |
| `${variable}` | Template variable substitution |
| `${variable:regex}` | With regex formatting |

## LogQL (Loki) Quick Reference

| Query | Описание |
|-------|-------------|
| `{service="nginx"}` | All logs from nginx |
| `{service="nginx"} \|= "ERROR"` | Filter for "ERROR" string |
| `{service="nginx"} != "DEBUG"` | Exclude "DEBUG" |
| `{service="nginx"} \| json` | Parse JSON logs |
| `{service="nginx"} \| pattern '<ip> - - [<_>] "<method> <uri> <_>" <status>'` | Pattern parser |
| `rate({service="nginx"} \|= "error" [5m])` | Error rate per second |
| `count_over_time({service="nginx"}[5m])` | Log count over time |
