# Prometheus — краткая справка

## Основы PromQL

| Query | Description |
|-------|-------------|
| `metric_name` | Мгновенный вектор — текущее значение |
| `metric_name[5m]` | Вектор диапазона — последние 5 минут |
| `metric_name{label="val"}` | Фильтр по метке |
| `metric_name{label=~"val.*"}` | Совпадение метки по регулярному выражению |
| `metric_name{label!="val"}` | Метка не равна значению |
| `metric_name{label!~"val.*"}` | Метка не соответствует регулярному выражению |
| `metric_name offset 1h` | Значение час назад |

## Операторы агрегации

| Query | Description |
|-------|-------------|
| `sum(metric)` | Сумма всех рядов |
| `sum by (label) (metric)` | Сумма с группировкой по метке |
| `avg(metric)` | Среднее значение |
| `max(metric)` | Максимум |
| `min(metric)` | Минимум |
| `count(metric)` | Количество рядов |
| `topk(5, metric)` | Пять наибольших значений |
| `bottomk(5, metric)` | Пять наименьших значений |

## Функции скорости и изменения

| Query | Description |
|-------|-------------|
| `rate(counter[5m])` | Скорость в секунду за 5 минут (сглаженная) |
| `irate(counter[5m])` | Мгновенная скорость по двум последним выборкам |
| `increase(counter[1h])` | Общий прирост за час |
| `delta(gauge[10m])` | Изменение gauge за 10 минут |
| `deriv(gauge[5m])` | Производная за секунду |
| `predict_linear(gauge[1h], 3600)` | Прогноз значения через час |

## Распространённые метрики

| Metric | Description |
|--------|-------------|
| `up` | Статус сбора метрик: 1 — доступен, 0 — недоступен |
| `scrape_duration_seconds` | Длительность сбора метрик |
| `process_cpu_seconds_total` | Использование CPU (счётчик) |
| `process_resident_memory_bytes` | Резидентная память RSS |
| `http_requests_total` | Счётчик HTTP-запросов |
| `http_request_duration_seconds` | Гистограмма задержки запросов |
| `node_cpu_seconds_total` | Время CPU по режимам |
| `node_memory_MemAvailable_bytes` | Доступная память |
| `node_filesystem_avail_bytes` | Свободное место на диске |
| `node_network_receive_bytes_total` | Полученные байты сети |

## Командная строка alertmanager

| Command | Description |
|---------|-------------|
| `amtool alert` | Список активных оповещений |
| `amtool alert query alertname=name` | Фильтр оповещений |
| `amtool silence add alertname=name` | Создать период подавления оповещений |
| `amtool silence list` | Список периодов подавления |
| `amtool silence expire ID` | Удалить период подавления |
| `amtool config show` | Показать загруженную конфигурацию |
| `amtool check-config alertmanager.yml` | Проверить конфигурацию |

## promtool

| Command | Description |
|---------|-------------|
| `promtool check config prometheus.yml` | Проверить конфигурацию |
| `promtool check rules rules.yml` | Проверить правила оповещений |
| `promtool query instant http://localhost:9090 'up'` | Run instant query |
| `promtool query range http://localhost:9090 'up'` | Run range query |
| `promtool test rules tests.yml` | Unit test alert rules |

## Recording Rule Patterns

```yaml
groups:
  - name: example
    interval: 30s
    rules:
      - record: job:http_requests:rate5m
        expr: sum by (job) (rate(http_requests_total[5m]))
      - alert: HighErrorRate
        expr: rate(http_errors_total[5m]) > 0.05
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High error rate on {{ $labels.job }}"
```
