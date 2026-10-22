# Мониторинг (Datadog) — краткая справка

## Агент Datadog

| Команда | Описание |
|---------|-------------|
| `datadog-agent status` | Полное состояние агента |
| `datadog-agent check check_name` | Выполнить проверку вручную |
| `datadog-agent configcheck` | Проверить конфигурации проверок |
| `datadog-agent diagnose` | Запустить диагностику сетевой связности |
| `datadog-agent hostname` | Показать сообщаемое имя хоста |
| `datadog-agent flare` | Создать пакет диагностики для поддержки |
| `systemctl status datadog-agent` | Состояние службы агента |
| `journalctl -u datadog-agent -f` | Следить за журналом агента |

## CLI Datadog (dogstatsd / ddtrace)

| Команда | Описание |
|---------|-------------|
| `DD_ENV=prod DD_SERVICE=web ddtrace-run python app.py` | Подключить трассировку APM |
| `DD_AGENT_HOST=localhost ddtrace-run gunicorn app:app` | Удалённый агент |
| `dog metric post my.metric 42 --tags env:prod` | Отправить пользовательскую метрику |
| `dog event post "Deploy" "v1.2.3 deployed" --alert_type info` | Отправить событие |
| `dog monitor mute ID --end 1700000000` | Приглушить монитор до указанного времени |

## Метрики DogStatsD из кода

| Type | Pattern | Описание |
|------|---------|-------------|
| Count | `statsd.increment("requests.count", tags=["env:prod"])` | Increment counter |
| Gauge | `statsd.gauge("queue.depth", 42)` | Set gauge value |
| Histogram | `statsd.histogram("response.time", 0.234)` | Track distribution |
| Timing | `statsd.timing("query.ms", 150)` | Timing in ms |
| Set | `statsd.set("unique.users", user_id)` | Count unique values |

## Query Language (Metrics)

| Query | Описание |
|-------|-------------|
| `avg:system.cpu.user{*}` | Average CPU across all hosts |
| `sum:nginx.net.request_per_s{env:prod}` | Sum by tag filter |
| `avg:system.load.1{host:web01}` | Single host |
| `top(avg:system.cpu.user{*} by {host}, 5, "max", "desc")` | Top 5 hosts by CPU |
| `anomalies(avg:db.query.time{*}, 'basic', 2)` | Anomaly detection |
| `forecast(avg:disk.used{*}, 'linear', 7)` | 7-day forecast |
| `diff(avg:system.mem.used{*})` | Rate of change |

## Monitor Alert Thresholds (YAML)

```yaml
type: metric alert
query: "avg(last_5m):avg:system.cpu.user{env:prod} > 80"
thresholds:
  critical: 80
  warning: 60
  critical_recovery: 75
  warning_recovery: 55
```

## Logs Query Syntax

| Query | Описание |
|-------|-------------|
| `service:nginx status:error` | Errors from nginx |
| `env:prod @http.status_code:[500 TO 599]` | 5xx in production |
| `@duration:>1000` | Requests over 1s |
| `"connection refused"` | Exact phrase |
| `-status:info` | Exclude info level |
| `@user.id:12345 service:auth` | Specific user auth events |
