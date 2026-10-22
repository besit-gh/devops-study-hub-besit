---
title: Интеграции и маршрутизация оповещений
module: opsgenie
duration_min: 20
difficulty: intermediate
tags: [opsgenie, integrations, routing, prometheus, datadog, api, deduplication]
exercises: 3
---

## Обзор
Польза Opsgenie особенно заметна при интеграции со стеком мониторинга. Prometheus, Grafana, Datadog, CloudWatch и другие инструменты создают оповещения. Без продуманной маршрутизации они превращаются в общий поток шума. Правила интеграции Opsgenie позволяют точно определить, какая команда получает конкретное оповещение, с каким приоритетом и по каким правилам дедупликации. В уроке рассматриваются REST API, основные интеграции и механизмы маршрутизации, которые отличают полезные оповещения от alert fatigue.

## Основные понятия

### REST API Opsgenie
API Opsgenie — основа интеграций. Понимание его работы особенно полезно, когда готовой интеграции нет или требуется индивидуальная настройка.

Base URL: `https://api.opsgenie.com/v2/`

Аутентификация: API-ключ в заголовке `Authorization`.

```bash
# Создать оповещение через REST API
curl -X POST "https://api.opsgenie.com/v2/alerts" \
  -H "Content-Type: application/json" \
  -H "Authorization: GenieKey YOUR_API_KEY" \
  -d '{
    "message": "High CPU usage on web-01",
    "alias": "web-01-high-cpu",
    "description": "CPU usage exceeded 90% for 5 minutes on web-01",
    "responders": [{"name": "platform-team", "type": "team"}],
    "tags": ["cpu", "infrastructure", "production"],
    "priority": "P2",
    "details": {
      "host": "web-01",
      "metric": "cpu_usage_percent",
      "value": "92.4"
    }
  }'

# Закрыть (разрешить) оповещение по псевдониму
curl -X POST "https://api.opsgenie.com/v2/alerts/web-01-high-cpu/close?identifierType=alias" \
  -H "Authorization: GenieKey YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"note": "CPU usage returned to normal"}'

# Получить сведения об оповещениях
curl -X GET "https://api.opsgenie.com/v2/alerts?query=status:open AND tag:production" \
  -H "Authorization: GenieKey YOUR_API_KEY"
```

Поле `alias` служит ключом дедупликации: два оповещения с одинаковым псевдонимом считаются одним и тем же оповещением.

### Обзор интеграций

Интеграции Opsgenie настраиваются для каждой команды и создают **ключ API интеграции**, на который внешний инструмент отправляет оповещения.

Перейдите: **Teams → [Team] → Integrations → Add Integration**.

Каждая интеграция включает:
- Уникальный ключ API, который использует внешний инструмент.
- Необязательные **правила интеграции** для условной маршрутизации и преобразования данных.
- Назначенную команду (ответственного по умолчанию).

| Integration | Type | Notes |
|---|---|---|
| Prometheus Alertmanager | Webhook | Configure in Alertmanager `receivers` |
| Grafana | Native | Built-in in Grafana contact points |
| Datadog | API key | Datadog webhook or Opsgenie monitor action |
| AWS CloudWatch | API key | Via CloudWatch SNS → Lambda → Opsgenie, or direct |
| Jira Software | Bi-directional | Alert → Jira issue; Jira issue → close alert |
| PagerDuty migration | Import tool | Migrate schedules/escalations |
| Generic webhook | Generic API | For anything not natively supported |

### Интеграция с Prometheus / Alertmanager
В Prometheus срабатывают правила оповещений → Alertmanager выполняет маршрутизацию → Opsgenie.

Alertmanager configuration:

```yaml
# alertmanager.yml
global:
  opsgenie_api_key: "YOUR_OPSGENIE_API_KEY"

receivers:
  - name: "opsgenie-platform"
    opsgenie_configs:
      - api_key: "TEAM_INTEGRATION_KEY"
        message: '{{ template "opsgenie.default.message" . }}'
        priority: '{{ if eq .GroupLabels.severity "critical" }}P1{{ else if eq .GroupLabels.severity "warning" }}P2{{ else }}P3{{ end }}'
        tags: '{{ range .GroupLabels.SortedPairs }}{{ .Name }}:{{ .Value }},{{ end }}'
        details:
          env: '{{ .GroupLabels.env }}'
          alertname: '{{ .GroupLabels.alertname }}'

route:
  receiver: "opsgenie-platform"
  group_by: ["alertname", "env", "service"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
```

### Grafana Integration
В Grafana настройте Opsgenie как точку контакта:

**Alerting → Contact Points → Add contact point → Opsgenie**

Поля настройки:
- **API Key**: ключ интеграции команды Opsgenie.
- **Auto close**: закрывать оповещение Opsgenie после восстановления оповещения Grafana (эту опцию рекомендуется включать всегда).
- **Override priority**: переопределять статический приоритет или использовать шаблоны меток.
- **Message**: шаблон аннотации Grafana: `{{ $labels.alertname }} - {{ $labels.instance }}`

### Datadog Integration
Доступны два способа:

**Способ 1 — webhook Datadog в Opsgenie:**
Datadog → Integrations → Webhooks → добавьте конечную точку API Opsgenie как URL webhook с ключом интеграции.

**Способ 2 — интеграция Datadog в Opsgenie:**
В Opsgenie добавьте интеграцию типа Datadog — она создаст ключ API. В Datadog укажите упоминание Opsgenie (`@opsgenie-team-name`) в уведомлениях монитора.

Datadog → Monitor → Notification message:

```
{{#is_alert}}@opsgenie-platform-team{{/is_alert}}
{{#is_recovery}}@opsgenie-platform-team{{/is_recovery}}
```

### CloudWatch Integration
Сигналы тревоги CloudWatch → тема SNS → функция Lambda → API Opsgenie.

Example Lambda (Python) for CloudWatch → Opsgenie:

```python
import json
import urllib.request

OPSGENIE_API_KEY = "YOUR_KEY"

def lambda_handler(event, context):
    sns_message = json.loads(event["Records"][0]["Sns"]["Message"])
    alarm_name = sns_message["AlarmName"]
    new_state = sns_message["NewStateValue"]

    if new_state == "ALARM":
        payload = {
            "message": f"CloudWatch: {alarm_name}",
            "alias": f"cloudwatch-{alarm_name}",
            "priority": "P2",
            "tags": ["cloudwatch", "aws"]
        }
        action = "alerts"
    else:
        payload = {"note": "Alarm cleared"}
        action = f"alerts/cloudwatch-{alarm_name}/close?identifierType=alias"

    req = urllib.request.Request(
        f"https://api.opsgenie.com/v2/{action}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"GenieKey {OPSGENIE_API_KEY}",
                 "Content-Type": "application/json"},
        method="POST"
    )
    urllib.request.urlopen(req)
```

### Integration Rules (Conditions and Actions)
Правила интеграции позволяют изменять, маршрутизировать или подавлять оповещения по их входящим полям до запуска политики эскалации.

Правила проверяются по порядку. Применяется первое совпавшее правило, если не включена опция «continue».

**Condition types:**

| Condition | Example |
|---|---|
| Message contains | `message contains "OutOfMemory"` |
| Tags match | `tags include "production"` |
| Priority equals | `priority is P1` |
| Alert source | `source is "Prometheus"` |
| Custom detail field | `details.env equals "production"` |

**Action types:**

| Action | Use |
|---|---|
| Set priority | Override priority based on severity label |
| Add responder (team) | Route to a different team |
| Add tag | Enrich alert with environment or service tag |
| Set alias | Control deduplication key |
| Acknowledge | Auto-acknowledge low-noise alerts |
| Suppress | Drop the alert entirely (maintenance windows) |
| Change message | Normalise alert titles across tools |

Пример правила интеграции: направлять оповещения БД команде баз данных и назначать P1, если серьёзность равна `critical`.

```
Rule 1: IF tags include "database" AND details.severity == "critical"
  THEN set priority to P1, add responder team: "database-team"

Rule 2: IF tags include "database"
  THEN add responder team: "database-team"

Rule 3 (default): route to platform-team
```

### Tags and Priorities (P1–P5)

| Priority | Meaning | Typical use |
|---|---|---|
| P1 | Critical | Production down, data loss, security breach |
| P2 | High | Major feature broken, significant degradation |
| P3 | Moderate | Non-critical issue, workaround exists |
| P4 | Low | Minor issue, informational |
| P5 | Informational | No action required |

Приоритет определяет:
- Какие способы уведомления сработают (пользователи настраивают правила уведомлений для каждого приоритета).
- Будет ли оповещение учитываться в метриках нарушения SLA.
- Порядок отображения в списке оповещений.

Теги — произвольные строки. Рекомендуемый формат: `env:production`, `team:platform`, `service:checkout`. По тегам можно искать и фильтровать оповещения в списке и аналитике.

### Deduplication and Suppression

**Дедупликация** предотвращает создание дубликатов для одного и того же условия. Она управляется полем `alias`: оповещения с одинаковым псевдонимом объединяются, а последующие уведомления обновляют существующее оповещение.

Задавайте псевдоним в виде стабильного идентификатора: `{service}-{alert_name}-{environment}`.

Если система мониторинга повторно отправляет одно и то же оповещение (например, Prometheus каждые 4 часа), Opsgenie добавляет заметки к существующему оповещению, а не создаёт новые.

**Suppression rules** (under integration rules or maintenance windows) drop matching alerts before they create Opsgenie notifications.

Окно обслуживания: **Settings → Maintenance**. Во время запланированных работ оповещения, соответствующие заданным фильтрам, подавляются. Настройте его перед плановыми отключениями, чтобы избежать шквала оповещений.

```
Maintenance window:
  Name: "Planned DB maintenance 2024-03-20 02:00-04:00 UTC"
  Start: 2024-03-20 02:00 UTC
  End:   2024-03-20 04:00 UTC
  Affected: alerts with tag "database" OR responders include "database-team"
  Action: Suppress (create but suppress notification)
```

### Heartbeat Monitoring
**Heartbeat (сигнал активности)** подтверждает, что система работает. Если сигналы перестают поступать, Opsgenie создаёт оповещение.

Применение: контроль cron-заданий, пакетных процессов и агентов, которые не отправляют оповещение при сбое, а просто перестают работать.

```bash
# Send a heartbeat ping (the system runs this on a schedule)
curl -X GET "https://api.opsgenie.com/v2/heartbeats/my-backup-job/ping" \
  -H "Authorization: GenieKey YOUR_API_KEY"
```

Если сигнал не поступил в течение заданного интервала, Opsgenie создаёт оповещение для настроенной команды.

Configure at: **Settings → Heartbeat Monitoring → Add Heartbeat**

Поля настройки: name, interval (e.g., 10 minutes), interval unit, alert message, responder team.

## Примеры

### Полная схема маршрутизации для нескольких команд

```
Integration: Prometheus (team: platform, default P3)

Rule 1: severity=critical AND env=production → P1, responder: platform-team + management-team
Rule 2: service=database → responder: database-team
Rule 3: service=frontend AND severity=warning → suppress (frontend has own alerting)
Rule 4: env=staging → P5, suppress notifications
Rule 5 (default): route to platform-team, keep priority from source
```

## Практические задания

1. Напишите полную конфигурацию `receivers` и `route` для Alertmanager, отправляющую оповещения Prometheus в Opsgenie: `severity: critical` соответствует P1, `severity: warning` — P2, все остальные оповещения по умолчанию получают P3. Псевдоним оповещения должен состоять из меток `alertname` и `instance`, чтобы дедупликация выполнялась отдельно для каждого узла.

2. Спроектируйте правила интеграции для ситуации, когда Opsgenie получает оповещения из трёх источников: Prometheus, Datadog и собственного приложения. Требования: (а) любое оповещение с тегом `security` направляется команде безопасности с приоритетом P1 независимо от источника; (б) оповещения Datadog с тегом `staging` полностью подавляются; (в) оповещения собственного приложения с `error_type: transient` автоматически подтверждаются. Запишите каждое правило как пару «условие + действие».

3. Пакетное задание запускается каждые 6 часов, и нужно обнаруживать его незаметные сбои. При ошибке задание не отправляет оповещение, а просто перестаёт выполняться. Объясните, как использовать heartbeat-мониторинг Opsgenie: что должно делать задание, как настроить heartbeat, что произойдёт при сбое и как проверить оповещения, не вызывая настоящий сбой.


---

### Быстрая проверка

4. Извлеките поле условия маршрутизации из примера политики. Выполните: `printf 'conditions:\n- field: priority\n  operation: equals\n  value: P1\n' | awk '/field:/{print $2}'`

```expected_output
priority
```

Подсказка: `awk` может находить строки с нужным ключевым словом и выводить выбранное поле.
Подсказка: используйте шаблон `'/field:/{print $2}'`, чтобы найти строки с `field:` и вывести второй разделённый пробелами элемент.

5. Посчитайте правила маршрутизации в политике. Выполните: `printf 'rules:\n- name: critical-rule\n  priority: P1\n- name: high-rule\n  priority: P2\n- name: default-rule\n  priority: P3\n' | grep -c '^- name:'`

```expected_output
3
```

Подсказка: `grep` умеет считать количество строк, соответствующих шаблону.
Подсказка: используйте `grep -c`, чтобы посчитать строки, соответствующие шаблону `^- name:`, в переданном через конвейер тексте.
