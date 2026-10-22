---
title: Alertmanager
module: prometheus
duration_min: 20
difficulty: intermediate
tags: [prometheus, alertmanager, alerting, oncall, slack, pagerduty]
exercises: 3
---

## Обзор

Alertmanager управляет жизненным циклом оповещений от Prometheus и других совместимых систем. Он получает события, группирует связанные оповещения для уменьшения шума, направляет их нужным получателям по меткам, устраняет дубликаты и поддерживает silences на время планового обслуживания. Понимание Alertmanager необходимо для дежурств: ошибки в дереве маршрутизации приводят к пропущенным уведомлениям или шквалу оповещений, напрямую влияющим на production.

Разделение Prometheus и Alertmanager сделано намеренно. Prometheus вычисляет правила оповещений и отправляет события в Alertmanager по HTTP, но не определяет, кому и когда отправлять уведомления. За весь жизненный цикл уведомлений отвечает Alertmanager: группирует близкие по времени оповещения, ждёт перед отправкой, чтобы объединить всплески, маршрутизирует по меткам и подавляет дубликаты. Благодаря этому несколько экземпляров Prometheus могут отправлять события в один кластер Alertmanager, который выполняет общую дедупликацию.

Важный эксплуатационный момент: неправильная настройка `group_wait`, `group_interval` и `repeat_interval` приводит к двум проблемам. Слишком короткие интервалы создают поток уведомлений, к которому дежурные привыкают и перестают реагировать. Слишком длинный `repeat_interval` означает, что длительный инцидент не будет повторно напоминать о себе после первого уведомления. Подбор значений с учётом процесса дежурств команды так же важен, как и сами выражения оповещений.

## Основные понятия

### Правила оповещений в Prometheus

Правила оповещений хранятся в файлах правил, загружаемых Prometheus (в тех же файлах, что и recording rules). Правило срабатывает, когда выражение возвращает непустой результат дольше указанного интервала `for`.

```yaml
# rules/alerts.yml
groups:
  - name: availability
    rules:

      - alert: InstanceDown
        expr: up == 0
        for: 2m          # must be true for 2m before firing
        labels:
          severity: critical
          team: infra
        annotations:
          summary: "Instance {{ $labels.instance }} is down"
          description: "Job {{ $labels.job }} on {{ $labels.instance }} has been down for more than 2 minutes."
          runbook_url: "https://wiki.example.com/runbooks/instance-down"

      - alert: HighErrorRate
        expr: job:http_error_ratio:rate5m > 0.05
        for: 5m
        labels:
          severity: warning
          team: backend
        annotations:
          summary: "High error rate on {{ $labels.job }}"
          description: "Error rate is {{ $value | humanizePercentage }} (threshold: 5%)"

      - alert: DiskFillingSoon
        expr: predict_linear(node_filesystem_free_bytes{fstype!="tmpfs"}[6h], 4*3600) < 0
        for: 10m
        labels:
          severity: warning
          team: infra
        annotations:
          summary: "Disk on {{ $labels.instance }} will fill within 4 hours"
```

**Состояния оповещения:**
- **Inactive** — выражение ложно или не возвращает результат
- **Pending** — выражение истинно, но интервал `for` ещё не истёк
- **Firing** — выражение остаётся истинным дольше интервала `for`

Параметр `for` предотвращает частые переключения состояния и снижает шум от кратковременных всплесков. Значение `0` означает немедленное срабатывание. Для критической инфраструктуры обычно используют 1–2 минуты; для нарушений SLO — 5–10 минут, чтобы не вызывать дежурного из-за кратких всплесков трафика.

**Labels и annotations:**
- `labels` — часть идентичности оповещения; используются Alertmanager для маршрутизации и подавления. Ограничивайте число возможных значений (severity, team, env).
- `annotations` — понятный человеку контекст уведомления. Для маршрутизации не используются. Для динамических значений применяйте шаблоны Go.

### Шаблоны Go в annotations

Annotations правил Prometheus и Alertmanager поддерживают синтаксис шаблонов Go. Используйте его в реальных оповещениях, чтобы добавить контекст и ускорить реакцию дежурного.

**Доступные переменные шаблона:**

| Переменная | Тип | Описание |
|----------|------|-------------|
| `$labels` | map | Все метки оповещения (метрики и самого правила) |
| `$value` | float64 | Числовое значение выражения в момент срабатывания |
| `$externalURL` | string | Внешний URL Prometheus/Alertmanager (ссылка на интерфейс) |

**Доступ к меткам:**

```yaml
annotations:
  summary: "Instance {{ $labels.instance }} is down"
  description: "Job {{ $labels.job }} on {{ $labels.instance }} has been down for 2 minutes."
```

**Форматирование числового значения:**

```yaml
annotations:
  # $value is the raw float: 0.073
  description: "Error rate is {{ $value }}"                    # → "Error rate is 0.073"
  description: "Error rate is {{ $value | humanize }}"         # → "Error rate is 73m" (milli-units)
  description: "Error rate is {{ $value | humanizePercentage }}" # → "Error rate is 7.3%"
  description: "Free bytes: {{ $value | humanize1024 }}"       # → human-readable bytes (KiB, MiB)
```

**`humanizePercentage`** принимает дробь от 0 до 1 и форматирует её как процент. Если выражение возвращает `0.073`, шаблон выдаст `"7.3%"`.

**Перебор меток в шаблонах получателей Alertmanager:**

В конфигурации получателя (например, в теле сообщения Slack) доступен `.Alerts` — список объектов оповещений. У каждого объекта есть `.Labels` и `.Annotations`:

```yaml
slack_configs:
  - text: >-
      {{ range .Alerts -}}
      *Alert:* {{ .Annotations.summary }}
      *Severity:* {{ .Labels.severity }}
      *Value:* {{ .Annotations.description }}
      {{ end }}
```

**Условные выражения в шаблонах:**

```yaml
annotations:
  description: >-
    {{ if eq $labels.severity "critical" }}
    CRITICAL: {{ $labels.instance }} is unreachable.
    {{ else }}
    WARNING: {{ $labels.instance }} may be degraded.
    {{ end }}
```

### Конвейер Alertmanager

Когда Prometheus генерирует оповещение, он отправляет его в Alertmanager. Далее выполняются следующие этапы:

```
Incoming alerts
      │
      ▼
  [Inhibition]    ← suppress alerts when a parent alert is firing
      │
      ▼
  [Silencing]     ← mute alerts matching a silence matcher
      │
      ▼
  [Routing tree]  ← match alerts to receivers based on labels
      │
      ▼
  [Grouping]      ← bundle related alerts into one notification
      │
      ▼
  [Deduplication] ← don't re-send if alert is already active
      │
      ▼
  [Receiver]      ← Slack, PagerDuty, email, webhook, etc.
```

### Дерево маршрутизации

Дерево маршрутизации — основа конфигурации Alertmanager. Оно состоит из узлов `route`; каждое оповещение проходит дерево сверху вниз и направляется в первый подходящий маршрут (или во все совпавшие, если задано `continue: true`). Корневой маршрут принимает все оповещения: у него должен быть receiver, и он не может содержать условий сопоставления.

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m           # how long to wait before sending "resolved"
  slack_api_url: "https://hooks.slack.com/services/..."

route:
  # Root route — catches everything not matched by children
  receiver: "default-slack"
  group_by: ["alertname", "job"]
  group_wait: 30s               # wait for more alerts before sending first notification
  group_interval: 5m            # how long to wait before re-sending a group
  repeat_interval: 4h           # how often to re-send an ongoing alert

  routes:
    # Critical infra alerts → PagerDuty
    - match:
        severity: critical
        team: infra
      receiver: pagerduty-infra
      group_wait: 10s           # page faster for critical
      repeat_interval: 1h

    # Backend team → their Slack channel
    - match_re:
        team: "backend|api"
      receiver: slack-backend
      continue: false           # stop routing after this match (default)

    # Catch-all warning → low-priority Slack
    - match:
        severity: warning
      receiver: slack-warnings
```

**`match` и `match_re`:**
- `match` проверяет точное совпадение значения метки.
- `match_re` проверяет значение метки регулярным выражением (синтаксис RE2).

```yaml
# Exact match — both labels must match exactly
- match:
    severity: critical
    team: infra

# Regex match — team label matches "backend" OR "api"
- match_re:
    team: "backend|api"
```

**Параметры группировки:**

| Параметр | Описание |
|-----------|-------------|
| `group_by` | Метки для группировки оповещений. `["..."]` объединяет всё в одну группу. |
| `group_wait` | Задержка перед первым уведомлением новой группы — позволяет объединить несколько событий. |
| `group_interval` | Минимальный интервал между уведомлениями существующей группы при поступлении новых событий. |
| `repeat_interval` | Как часто повторно отправлять уведомление для уже активной группы. |

**`continue: true`:** по умолчанию маршрутизация останавливается на первом совпадении. Установите `continue: true`, чтобы отправить уведомление этому получателю И продолжить проверку следующих маршрутов (например, для аудита или канала NOC).

### Настройка получателей

```yaml
receivers:
  - name: "default-slack"
    slack_configs:
      - channel: "#alerts-general"
        title: "{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}"
        text: >-
          {{ range .Alerts -}}
          *Alert:* {{ .Annotations.summary }}
          *Severity:* {{ .Labels.severity }}
          *Description:* {{ .Annotations.description }}
          {{ end }}
        send_resolved: true

  - name: "pagerduty-infra"
    pagerduty_configs:
      - routing_key: "<PD_integration_key>"
        severity: "{{ .CommonLabels.severity }}"
        description: "{{ .CommonAnnotations.summary }}"
        details:
          firing: "{{ .Alerts.Firing | len }}"
          resolved: "{{ .Alerts.Resolved | len }}"
        send_resolved: true

  - name: "slack-backend"
    slack_configs:
      - api_url: "https://hooks.slack.com/services/BACKEND_WEBHOOK"
        channel: "#backend-alerts"
        send_resolved: true

  - name: "slack-warnings"
    slack_configs:
      - channel: "#alerts-low-priority"
        send_resolved: false    # don't clutter channel with resolves

  - name: "email-oncall"
    email_configs:
      - to: "oncall@example.com"
        from: "alertmanager@example.com"
        smarthost: "smtp.example.com:587"
        auth_username: "alertmanager@example.com"
        auth_password: "<password>"
        require_tls: true

  - name: "null"   # drop alerts — used as a catch-all when you want to silence a category
    # no configs needed — empty receiver discards alerts
```

**Получатель webhook** (универсальные интеграции — OpsGenie, пользовательские скрипты):

```yaml
  - name: "webhook-custom"
    webhook_configs:
      - url: "http://my-handler:8080/alert"
        send_resolved: true
        http_config:
          bearer_token: "<token>"
```

### Правила подавления

Inhibition подавляет оповещения, если уже активно другое (исходное) оповещение. Типичный пример: если узел недоступен, подавить все оповещения приложений, вызванные его отказом, иначе каждое приложение на этом узле будет отдельно вызывать дежурного.

```yaml
inhibit_rules:
  # Suppress warning alerts when a critical alert for the same instance fires
  - source_match:
      severity: critical
    target_match:
      severity: warning
    equal: ["instance", "job"]   # both alerts must share these label values

  # Suppress all alerts for an instance if InstanceDown is firing
  - source_match:
      alertname: InstanceDown
    target_match_re:
      alertname: ".+"
    equal: ["instance"]
```

**Как работает поле `equal`:** правило подавляет `target` только тогда, когда `source` и `target` имеют одинаковые значения всех меток, перечисленных в `equal`. Это не позволяет сбою узла в одном дата-центре подавлять оповещения в другом дата-центре лишь потому, что у них одинаковая метка severity.

**`target_match_re`:** выбирает любое оповещение, значение метки которого соответствует регулярному выражению. `alertname: ".+"` соответствует всем оповещениям с непустым alertname. Это позволяет подавлять все оповещения конкретного экземпляра, если он недоступен.

**Подавление оповещений Kubernetes: игнорирование pod-оповещений при отказе узла:**

```yaml
inhibit_rules:
  # When InstanceDown fires for a node, suppress pod-level alerts on that node
  - source_match:
      alertname: InstanceDown
    target_match_re:
      alertname: "KubePodCrashLooping|KubeDeploymentReplicasMismatch"
    equal: ["instance"]
```

Это работает, потому что `InstanceDown` содержит метку `instance` с адресом узла, и оповещения Kubernetes для pod на этом узле содержат ту же метку. При совпадении pod-оповещения подавляются.

### Подавление оповещений (silences)

Silence создаются через интерфейс или API Alertmanager. Они временно отключают уведомления для совпадающих оповещений и используются при обслуживании, развёртывании и известных инцидентах.

```bash
# Create a silence via API (expires in 2 hours)
curl -s -X POST http://alertmanager:9093/api/v2/silences \
  -H "Content-Type: application/json" \
  -d '{
    "matchers": [
      {"name": "instance", "value": "host1:9100", "isRegex": false},
      {"name": "job", "value": "node", "isRegex": false}
    ],
    "startsAt": "2024-01-01T02:00:00Z",
    "endsAt": "2024-01-01T04:00:00Z",
    "createdBy": "oncall-engineer",
    "comment": "Scheduled maintenance window"
  }'

# List active silences
curl -s http://alertmanager:9093/api/v2/silences | jq '.[] | select(.status.state=="active")'

# Delete a silence
curl -s -X DELETE http://alertmanager:9093/api/v2/silences/<silence_id>
```

**amtool** — CLI для управления Alertmanager:

```bash
amtool --alertmanager.url=http://alertmanager:9093 silence add \
  alertname=InstanceDown instance=host1:9100 \
  --duration=2h \
  --author=oncall-engineer \
  --comment="Maintenance"

amtool --alertmanager.url=http://alertmanager:9093 alert query
amtool --alertmanager.url=http://alertmanager:9093 config show
```

### Дедупликация

Alertmanager автоматически выполняет дедупликацию: если одно и то же оповещение (с теми же метками) продолжает срабатывать, отправляется одно уведомление, а затем повторяется с интервалом `repeat_interval`. Это отличается от группировки: дедупликация предотвращает повторную отправку одного оповещения, а группировка определяет, как объединять разные оповещения в уведомления.

## Примеры

**Запуск Alertmanager через Docker:**

```bash
cat > /tmp/alertmanager.yml <<EOF
global:
  resolve_timeout: 5m
route:
  receiver: "null"
  routes: []
receivers:
  - name: "null"
EOF

docker run -d \
  --name alertmanager \
  -p 9093:9093 \
  -v /tmp/alertmanager.yml:/etc/alertmanager/alertmanager.yml \
  prom/alertmanager

# Check config validity without running
docker run --rm \
  -v /tmp/alertmanager.yml:/etc/alertmanager/alertmanager.yml \
  prom/alertmanager \
  --config.file=/etc/alertmanager/alertmanager.yml \
  --check-config

# Validate Prometheus rule files
promtool check rules rules/alerts.yml
```

**Проверка маршрутизации без отправки настоящих уведомлений:**

```bash
# Use amtool to test which receiver an alert would hit
amtool config routes test \
  --config.file=/tmp/alertmanager.yml \
  severity=critical team=infra alertname=InstanceDown
```

**Полный alertmanager.yml с маршрутизацией, получателями и подавлением:**

```yaml
global:
  resolve_timeout: 5m

route:
  receiver: "null"
  group_by: ["alertname", "job"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

  routes:
    - match:
        severity: critical
      receiver: pagerduty-infra
      group_wait: 10s
      repeat_interval: 1h

    - match:
        severity: warning
      receiver: slack-warnings
      group_wait: 5m
      repeat_interval: 4h

inhibit_rules:
  - source_match:
      severity: critical
    target_match:
      severity: warning
    equal: ["job"]

receivers:
  - name: "null"

  - name: pagerduty-infra
    pagerduty_configs:
      - routing_key: "<PD_key>"
        send_resolved: true

  - name: slack-warnings
    slack_configs:
      - api_url: "https://hooks.slack.com/services/..."
        channel: "#warnings"
        send_resolved: true
```

## Практические задания

1. Напишите полный `alertmanager.yml`, который направляет: (a) оповещения `severity=critical` в PagerDuty с `group_wait` 10s; (b) `severity=warning` в канал Slack с `group_wait` 5m; (c) все остальные — в приёмник `null` (отбрасывать). Добавьте правило подавления, скрывающее предупреждения, когда для того же `job` срабатывает критическое оповещение.

2. Напишите в файле правил Prometheus три правила оповещения: (a) `InstanceDown` — цель с `up == 0` в течение 2 минут, серьёзность critical; (b) `HighMemoryUsage` — `node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes < 0.10` в течение 5 минут, серьёзность warning; (c) `DiskWillFillIn4Hours` — использовать `predict_linear`, период `for` 10 минут, серьёзность warning. Добавьте содержательные аннотации с подстановкой переменных шаблона Go `$labels.instance` и `$value | humanizePercentage`, где это уместно.

3. Предположим, в кластере Kubernetes для узла сработало оповещение `InstanceDown`. Напишите правило подавления, которое отключит оповещения `KubePodCrashLooping` и `KubeDeploymentReplicasMismatch` для Pod на этом же узле. Считайте, что оба типа оповещений имеют общую метку `instance`, указывающую на узел.


---

### Быстрая проверка

4. Посчитайте приёмники в заготовке конфигурации Alertmanager. Выполните: `printf 'receivers:\n- name: team-slack\n- name: team-email\n- name: team-pagerduty\n' | grep -c '^- name:'`

```expected_output
3
```

Подсказка: отфильтруйте строки по шаблону и поручите shell посчитать совпадения.
Подсказка: используйте `grep -c`, чтобы посчитать строки, соответствующие шаблону `^- name:`, в выводе `printf`, переданном через конвейер.

5. Извлеките `repeat_interval` из заготовки конфигурации маршрута. Выполните: `printf 'route:\n  receiver: team-slack\n  group_wait: 30s\n  repeat_interval: 4h\n' | awk '/repeat_interval:/{print $2}'`

```expected_output
4h
```

Подсказка: используйте инструмент обработки текста, который находит строку по шаблону и выводит нужное поле.
Подсказка: используйте `awk` с шаблоном `/repeat_interval:/` и `{print $2}`, чтобы извлечь второе поле найденной строки.
