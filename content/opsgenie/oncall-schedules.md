---
title: Графики дежурств и эскалации Opsgenie
module: opsgenie
duration_min: 20
difficulty: beginner
tags: [opsgenie, on-call, schedules, escalation, incident-management]
exercises: 3
---

## Обзор

Opsgenie — платформа Atlassian для управления оповещениями и расписаниями дежурств. Она отвечает на два вопроса: кто дежурит сейчас и что произойдёт, если человек не ответит. В DevOps Opsgenie связывает инструменты мониторинга (Prometheus, Datadog, Grafana) с людьми, которые устраняют сбои. Без такой системы оповещения попадают в общий почтовый ящик или канал Slack, где ответственность размывается и каждый предполагает, что сообщение увидел кто-то другой. Opsgenie делает ответственность явной: назначает конкретного дежурного, устанавливает срок ответа и автоматически запускает заданную цепочку эскалации, если ответа нет.

Архитектура основана на разделении ответственности: *расписания* отвечают на вопрос «кто и когда доступен», *политики эскалации* — «что делать, если никто не ответил», а *правила маршрутизации* — «какая команда отвечает за оповещение». Эти три механизма можно комбинировать для организаций любой сложности. A small startup might have one schedule and one escalation policy. A large enterprise might have hundreds, but each is built from the same primitives. This modularity means you can change one piece — swap a rotation type, add an escalation step — without rebuilding everything else.

В общей цепочке DevOps Opsgenie — последнее звено между обнаружением проблемы и реагированием. Prometheus создаёт оповещение, Alertmanager направляет его в Opsgenie, а Opsgenie определяет дежурного инженера и уведомляет его. Система интегрируется с управлением инцидентами (Jira, временные шкалы в стиле PagerDuty), средствами коммуникации (Slack, Microsoft Teams) и runbook-системами, чтобы инженер получал вместе с уведомлением необходимый контекст. Основа работы — правильно настроенные расписания и политики эскалации; остальная функциональность Opsgenie опирается на них.

---

## Основные понятия

### Команды и пользователи

**Пользователи** — люди с учётной записью Opsgenie. У каждого пользователя есть:

| Attribute | Description |
|-----------|-------------|
| **Contact methods** | Phone, SMS, email, mobile push — configured in user profile |
| **Notification rules** | Personal rules for *how* and *when* to be notified per priority level |
| **Role** | Admin, User, Stakeholder, or Read Only |
| **Time zone** | Used to display schedule times and apply notification rules correctly |

**Команды** объединяют пользователей вокруг сервиса или функции и являются основной единицей маршрутизации Opsgenie. При поступлении оповещение направляется команде, после чего применяется её политика эскалации. У команды есть:

- Одна или несколько политик эскалации
- Одно или несколько расписаний
- Собственная очередь оповещений
- Интеграции (оповещения от конкретного источника мониторинга можно направлять сразу нужной команде)

Navigate to: **Teams → [Team Name] → Members / On-call / Schedules / Escalation Policies**

**Важно:** пользователь может состоять в нескольких командах, но правила его уведомлений глобальны и одинаковы для оповещений всех команд. Разные правила для разных сервисов потребовали бы отдельных учётных записей Opsgenie, что обычно не оправдано. Настраивайте уведомления с учётом наиболее критичного сценария.

---

### Структура расписания

**Расписание** — именованный объект, который в каждый момент времени определяет список дежурных участников. Оно состоит из одной или нескольких **ротаций**. Важно понимать эту двухуровневую структуру.

```
Schedule: "Platform Team - Global"
├── Rotation 1: EU Business Hours
│     participants: [alice, bob]
│     type: weekly
│     restriction: Mon–Fri 07:00–15:00 UTC
├── Rotation 2: US East Business Hours
│     participants: [carol, dave]
│     type: weekly
│     restriction: Mon–Fri 14:00–22:00 UTC
└── Rotation 3: Fallback (no restriction)
      participants: [team-lead]
      type: weekly
```

Определяя дежурных, Opsgenie проверяет все ротации, активные в данный момент. Если ротации пересекаются, все подходящие участники считаются дежурными одновременно. Политика эскалации определяет, кого из них уведомить первым.

**Основные свойства расписания:**

| Property | What it controls |
|----------|-----------------|
| **Rotation type** | How participants cycle (daily, weekly, custom) |
| **Rotation length** | Duration before advancing to the next participant |
| **Time restriction** | Hours/days during which this rotation is active |
| **Start date/time** | When the rotation begins; determines who is "first" in the cycle |
| **Participants** | Ordered list of users or groups |

**Важно:** дата и время начала ротации определяют, кто занимает «слот 1». Если недельная ротация начинается в среду, первый участник дежурит с этой среды по следующий вторник. Неверная дата начала — частая причина того, что в начале нового цикла дежурит не тот инженер. После создания всегда проверяйте расписание в **Schedules → Timeline**.

---

### Типы ротаций

#### Недельная ротация
Самый распространённый тип: каждый участник дежурит полную неделю, после чего очередь переходит к следующему.

```
Week 1 (Mon 00:00 – Sun 23:59 UTC): Alice
Week 2 (Mon 00:00 – Sun 23:59 UTC): Bob
Week 3 (Mon 00:00 – Sun 23:59 UTC): Carol
→ repeat
```

Подходит командам из трёх и более человек, для которых недельное дежурство приемлемо. Компромисс: меньше переключений контекста, но семь дней подряд приходится нести ответственность.

#### Суточная ротация
Участники меняются каждые 24 часа. Подходит для высоконагруженных сервисов и команд, которые хотят равномернее распределить нагрузку.

```
Mon: Alice
Tue: Bob
Wed: Carol
Thu: Alice
Fri: Bob
...
```

**Важно:** при суточной ротации становится больше передач дежурства. Поддерживайте runbook и контекст инцидентов в актуальном состоянии: человеку, который заступил во вторник, не должно требоваться звонить дежурившему в понедельник, чтобы понять текущие проблемы. Введите обязательную сводку в инструменте управления инцидентами в конце каждой смены.

#### Follow-the-Sun
Это не отдельный тип ротации в интерфейсе, а *схема*, реализуемая объединением нескольких ротаций с ограничениями по времени в одном расписании. Каждая ротация покрывает рабочие часы своего региона, обеспечивая непрерывное дежурство 24/7 без работы инженеров за пределами их местного дня.

```
Rotation 1: EU        (07:00–15:00 UTC) → alice, bob alternate weekly
Rotation 2: US East   (14:00–22:00 UTC) → carol, dave alternate weekly
Rotation 3: APAC      (22:00–07:00 UTC) → eve, frank alternate weekly
```

Перекрытия в один час (14:00–15:00, 22:00–23:00) предусмотрены специально: они создают окно передачи дежурства, когда доступны и уходящий, и заступающий инженеры.

#### Произвольная длительность ротации
Можно задать любую длительность: 12 часов, 3 дня, 2 недели. Это полезно для:
- 12-часовых смен в небольшой команде с разделением на день и ночь
- двухнедельных ротаций при очень низкой нагрузке на дежурных

```
Custom example — 12-hour split:
  Shift A: Mon–Sun 06:00–18:00 UTC → Alice (day shift)
  Shift B: Mon–Sun 18:00–06:00 UTC → Bob  (night shift)
```

**Сравнение типов ротаций:**

| Type | Cadence | Best for | Watch out for |
|------|---------|----------|---------------|
| Weekly | 7 days | Teams ≥ 3, moderate load | 7-day fatigue, holiday week |
| Daily | 24 hours | High alert volume, large teams | Handoff quality, context loss |
| Follow-the-Sun | Regional hours | Globally distributed teams | Gap between regions if misconfigured |
| Custom | Any interval | Niche shift structures | Complex cycle math, misaligned start dates |

---

### Пробелы в расписании

**Пробел** возникает, когда в определённый период не активна ни одна ротация. Оповещения в этот период никого не уведомят. Это незаметный отказ: Opsgenie не выдаёт ошибку, а просто не находит получателя.

**Типичные причины пробелов:**

| Cause | Example |
|-------|---------|
| Time restriction leaves hours uncovered | Rotation set to Mon–Fri 09:00–17:00 with no weekend coverage |
| All participants removed from a rotation | Rotation still exists but participant list is empty |
| Rotation end date reached | Rotation was set with an expiry that passed |
| Override applied but replacement not covering full window | Override ends at 18:00; schedule resumes at 09:00 next day — 15-hour gap |

**Как обнаружить пробелы:** откройте **Schedules → [Schedule Name] → Timeline**. Пробелы отображаются пустыми (белыми или серыми) периодами без имени участника. Если пробелы есть в ближайшие 30 дней, Opsgenie также показывает предупреждение.

**Способ устранения — резервная ротация:**

```
Add a final rotation with:
  Participant: [team-lead or on-call manager]
  Time restriction: none (covers all hours)
  Rotation type: weekly (single participant, always the same person)
  Purpose: catch-all for any hour not covered by primary rotations
```

Поскольку ротации одного расписания оцениваются совместно, резервная ротация без временных ограничений гарантирует наличие дежурного. Если ротации пересекаются, порядок уведомления по-прежнему задаёт политика эскалации: резервная ротация не получает приоритет, а лишь закрывает пустые интервалы.

**API: программная проверка пробелов**

```bash
# Retrieve the on-call timeline for the next 7 days
# and look for periods where onCallParticipants is empty
curl -X GET \
  "https://api.opsgenie.com/v2/schedules/platform-global/timeline?scheduleIdentifierType=name&intervalUnit=days&interval=7" \
  -H "Authorization: GenieKey YOUR_API_KEY" | \
  jq '.data.finalTimeline.rotations[].periods[] | select(.recipient == null) | .startDate, .endDate'
```

Пустой ответ означает, что пробелов не найдено. Любой результат указывает на пробел и охватывающий его временной интервал.

---

### Управление переопределениями дежурств

**Override (переопределение)** временно заменяет участника расписания, не изменяя саму ротацию. Этот механизм подходит для отпусков, обмена сменами и покрытия мероприятий.

**Поля переопределения:**

| Field | Description |
|-------|-------------|
| **User** | The replacement (who will be on call instead) |
| **Start time** | When the override begins (inclusive) |
| **End time** | When the override ends (exclusive) |
| **Alias** | Optional label for the override (e.g., "alice-vacation-dec") |

Navigate to: **Schedules → [Schedule Name] → Add Override**

Переопределения отображаются в расписании отдельным цветом и учитываются в аналитике дежурств. Поэтому отчёты о справедливом распределении нагрузки и расчёты компенсаций остаются корректными даже при обмене сменами.

**API: create an override**

```bash
# Create an override: replace alice with carol from Dec 20 to Dec 30
curl -X POST "https://api.opsgenie.com/v2/schedules/platform-global/overrides" \
  -H "Authorization: GenieKey YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user": {
      "type": "user",
      "username": "carol@company.com"
    },
    "startDate": "2024-12-20T00:00:00Z",
    "endDate": "2024-12-30T00:00:00Z",
    "alias": "alice-vacation-dec"
  }'
```

**API: проверьте, кто будет дежурить в будущем**

```bash
# Check who would be on call on Dec 25 at 14:00 UTC
curl -X GET \
  "https://api.opsgenie.com/v2/schedules/platform-global/on-calls?scheduleIdentifierType=name&flat=true&date=2024-12-25T14:00:00Z" \
  -H "Authorization: GenieKey YOUR_API_KEY" | jq '.data.onCallParticipants'
```

Ожидаемый вывод при корректно применённом переопределении:
```json
[
  {
    "name": "Carol Smith",
    "type": "user"
  }
]
```

**API: список всех активных переопределений**

```bash
# List overrides currently in effect for the schedule
curl -X GET \
  "https://api.opsgenie.com/v2/schedules/platform-global/overrides?scheduleIdentifierType=name" \
  -H "Authorization: GenieKey YOUR_API_KEY" | jq '.data[] | {alias: .alias, user: .user.username, start: .startDate, end: .endDate}'
```

**Важно:** переопределения не распространяются на шаги эскалации, в которых указан конкретный пользователь. Если политика ссылается на «дежурного из расписания», переопределение учитывается. Но если в политике жёстко задан адрес пользователя (например, `alice@company.com`), переопределение не поможет — Алису продолжат вызывать даже во время отпуска. **Для автоматического учёта отпусков указывайте в шагах эскалации расписания, а не отдельных пользователей.**

---

### Политики эскалации

**Политика эскалации** определяет, что делать, если оповещение не подтверждено в заданный срок. Это цепочка действий по принципу «если никто не ответил, то…». Для каждого оповещения, направленного команде, запускается её политика эскалации.

**Структура политики эскалации:**

```
Policy: "Platform - P1 Escalation"
│
├─ Step 1 [at 0 min]:  Notify on-call from schedule "platform-global"
│                       via: push notification + SMS
├─ Step 2 [at 5 min]:  Notify on-call from schedule "platform-global"
│                       via: phone call (re-notify same person, different method)
├─ Step 3 [at 10 min]: Notify user: platform-lead@company.com
│                       via: phone call
├─ Step 4 [at 20 min]: Notify team: Engineering Leadership (all members)
│                       via: push + phone call
│
└─ Repeat policy: 3 times, then keep alert open (never auto-close)
```

**Параметры настройки шага:**

| Field | Options |
|-------|---------|
| **Notify** | On-call from schedule, specific user, team (all members), team (on-call only) |
| **Via** | Default (user's own notification rules), or override with specific methods |
| **Wait before next step** | Minutes to wait for acknowledgment before escalating |

**Повтор эскалации:** если все шаги завершились без подтверждения, политика может повторить их до N раз. После исчерпания повторов оповещение остаётся открытым, но эскалация прекращается. **Не настраивайте автоматическое закрытие для production-сервисов:** незамеченное неподтверждённое оповещение опаснее, чем продолжающееся раздражающее уведомление.

**Важно:** время ожидания каждого шага отсчитывается от срабатывания *предыдущего шага*, а не от создания оповещения. Шаг 1 срабатывает в 0 минут, шаг 2 — через 5 минут (прошло всего 5 минут), шаг 3 — через 10 минут после шага 2 (всего 15 минут). Внимательно проверяйте суммарное время, особенно если SLA обещает, что человек получит P1 не позднее чем через 10 минут. В этом примере менеджера вызовут через 15 минут, что нарушает SLA в 10 минут.

**Отдельная политика эскалации для каждого приоритета (рекомендуемая схема):**

Вместо одной общей политики создайте отдельную для каждого приоритета оповещения:

| Policy name | Step 1 wait | Step 2 target | Step 3 target | Repeat |
|-------------|-------------|---------------|---------------|--------|
| P1-Critical | 0 min | On-call (5 min) | Manager (10 min) | 3x |
| P2-High | 0 min | On-call (10 min) | Team lead (20 min) | 2x |
| P3-Medium | 0 min | On-call (30 min) | — | 1x |
| P4-Low | 0 min | — | — | 0x (no repeat) |

Настройте это в правилах маршрутизации: оповещения с `priority: P1` направляйте в политику P1-Critical и так далее. Это не позволит предупреждению о нехватке дискового места разбудить технического директора в три часа ночи.

---

### Способы уведомления и приоритет

Каждый пользователь настраивает личные правила уведомлений в **Profile → Notification Rules**. Они независимы от политик эскалации и определяют, *как* связаться с человеком, а не *когда* и *кого* уведомлять.

**Типичная настройка правил уведомлений:**

```
For alerts with priority P1 or P2:
  Immediately:           mobile push notification
  If not ack in 2 min:  SMS
  If not ack in 4 min:  phone call

For alerts with priority P3 or P4:
  Immediately:           email + mobile push notification

For alerts with priority P5 (informational):
  Immediately:           email only
```

**Соответствие приоритетов оповещений:**

| Priority | Typical use | Expected response |
|----------|-------------|-------------------|
| P1 | Customer-facing outage, data loss | Immediate, any time |
| P2 | Degraded performance, partial outage | Within 15 minutes |
| P3 | Non-customer-facing, recoverable | Business hours |
| P4 | Warning, investigate soon | Best effort |
| P5 | Informational | No action required |

**Разделение ответственности — главная модель понимания:**

- **Политика эскалации** = *кого* и *когда* уведомлять (цепочка ответственности во времени)
- **Правила уведомлений** = *как* связаться с человеком (звонок, push или email в зависимости от приоритета)

Такое разделение позволяет менять способы связи с человеком без изменения политики эскалации, а перестраивать цепочку ответственности команды — без изменения личных настроек уведомлений.

**Важно:** если для шага эскалации явно задан способ связи (например, «всегда звонить независимо от правил пользователя»), личные правила уведомлений обходятся полностью. Используйте это редко и только для самых критичных шагов. Иначе инженеры теряют возможность настраивать уведомления и могут отключить их из-за усталости от оповещений.

---

### Правила маршрутизации

**Правила маршрутизации** связывают входящее оповещение с командой и политикой эскалации, которые будут его обрабатывать. Они анализируют источник, приоритет, теги и текст сообщения и направляют оповещение в соответствии с условиями.

```
Routing Rule: "Production Alerts → Platform Team"
  Condition:  alert.tags contains "env:production"
  AND         alert.source == "prometheus"
  Route to:   Platform Team → P1-Critical escalation policy

Routing Rule: "Staging Alerts → Platform Team (low priority)"
  Condition:  alert.tags contains "env:staging"
  Route to:   Platform Team → P3-Medium escalation policy

Routing Rule: "Default (catch-all)"
  Condition:  (none — matches everything)
  Route to:   Platform Team → P2-High escalation policy
```

**Порядок правил маршрутизации важен.** Они проверяются сверху вниз, и применяется первое совпадение. Самые конкретные правила размещайте вверху, а универсальное правило — внизу.

**Важно:** если ни одно правило не совпало и нет универсального правила, оповещение направляется в **политику эскалации команды по умолчанию**. Оно не теряется бесследно, но может попасть не туда. Добавляйте универсальное правило в конец набора каждой команды, чтобы неожиданные оповещения направлялись предсказуемо.

---

### Режимы участия дежурных в ротации

Если в ротации несколько участников и шаг эскалации ссылается на «дежурного из расписания», по умолчанию в каждый момент дежурит один участник — тот, чей слот активен. Однако ротацию можно настроить иначе:

| Mode | Behavior | Use case |
|------|----------|----------|
| **One at a time (default)** | Single participant on call per rotation slot | Standard weekly/daily rotation |
| **All participants simultaneously** | Everyone in the rotation is on call at once | Broadcast coverage, small critical teams |
| **Random** | One participant selected randomly each period | Load distribution, unpredictable assignment |

Для большинства production-сервисов используйте режим «по одному». Одновременный режим иногда полезен небольшой руководящей команде, где должен быть доступен любой руководитель, но он размывает персональную *ответственность*: когда дежурят все, никто не чувствует себя полностью ответственным. При одновременном режиме явно определите в политике эскалации, кто должен подтверждать оповещение.

---

## Примеры

### Example 1: Follow-the-Sun Schedule via API

Платформенной команде с инженерами в Лондоне (Европа) и Нью-Йорке (восток США) нужно непрерывное покрытие дежурств 24/7 в будни. Выходные закрывает руководитель команды.

```bash
# Step 1: Create the schedule shell
curl -X POST "https://api.opsgenie.com/v2/schedules" \
  -H "Authorization: GenieKey YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Platform Team - Global",
    "description": "Follow-the-sun coverage for platform engineering",
    "timezone": "UTC",
    "enabled": true,
    "ownerTeam": {
      "name": "Platform Team"
    },
    "rotations": [
      {
        "name": "EU Business Hours",
        "startDate": "2024-01-01T07:00:00Z",
        "type": "weekly",
        "length": 1,
        "participants": [
          {"type": "user", "username": "alice@company.com"},
          {"type": "user", "username": "bob@company.com"}
        ],
        "timeRestriction": {
          "type": "weekday-and-time-of-day",
          "restrictions": [
            {"day": "monday",    "startHour": 7,  "startMin": 0, "endHour": 15, "endMin": 0},
            {"day": "tuesday",   "startHour": 7,  "startMin": 0, "endHour": 15, "endMin": 0},
            {"day": "wednesday", "startHour": 7,  "startMin": 0, "endHour": 15, "endMin": 0},
            {"day": "thursday",  "startHour": 7,  "startMin": 0, "endHour": 15, "endMin": 0},
            {"day": "friday",    "startHour": 7,  "startMin": 0, "endHour": 15, "endMin": 0}
          ]
        }
      },
      {
        "name": "US East Business Hours",
        "startDate": "2024-01-01T14:00:00Z",
        "type": "weekly",
        "length": 1,
        "participants": [
          {"type": "user", "username": "carol@company.com"},
          {"type": "user", "username": "dave@company.com"}
        ],
        "timeRestriction": {
          "type": "weekday-and-time-of-day",
          "restrictions": [
            {"day": "monday",    "startHour": 14, "startMin": 0, "endHour": 22, "endMin": 0},
            {"day": "tuesday",   "startHour": 14, "startMin": 0, "endHour": 22, "endMin": 0},
            {"day": "wednesday", "startHour": 14, "startMin": 0, "endHour": 22, "endMin": 0},
            {"day": "thursday",  "startHour": 14, "startMin": 0, "endHour": 22, "endMin": 0},
            {"day": "friday",    "startHour": 14, "startMin": 0, "endHour": 22, "endMin": 0}
          ]
        }
      },
      {
        "name": "Fallback - All Hours",
        # No timeRestriction — covers nights, weekends, and any gap the regional rotations miss
        "startDate": "2024-01-01T00:00:00Z",
        "type": "weekly",
        "length": 1,
        "participants": [
          {"type": "user", "username": "teamlead@company.com"}
        ]
      }
    ]
  }'

# Step 2: Verify EU rotation is active on a Monday morning
curl -X GET \
  "https://api.opsgenie.com/v2/schedules/Platform%20Team%20-%20Global/on-calls?scheduleIdentifierType=name&flat=true&date=2024-01-08T09:00:00Z" \
  -H "Authorization: GenieKey YOUR_API_KEY" | jq '.data.onCallParticipants[].name'
# Expected: "Alice Johnson" (week 2 of EU rotation)

# Step 3: Verify fallback is active at weekend midnight
curl -X GET \
  "https://api.opsgenie.com/v2/schedules/Platform%20Team%20-%20Global/on-calls?scheduleIdentifierType=name&flat=true&date=2024-01-06T02:00:00Z" \
  -H "Authorization: GenieKey YOUR_API_KEY" | jq '.data.onCallParticipants[].name'
# Expected: "Team Lead" (fallback rotation, Saturday 02:00 UTC)
```

Перекрытие ротаций Европы и востока США с 14:00 до 15:00 UTC означает, что уходящий европейский инженер и заступающий инженер из США формально дежурят одновременно. Это специально предусмотренное окно передачи смены. Политика эскалации должна ссылаться на расписание, а не на отдельных пользователей, чтобы автоматически выбирать владельца текущего слота.

---

### Пример 2. Многошаговая политика эскалации с уровнями приоритета

В этом примере создаются две политики эскалации — для P1 и P3 — и связываются с расписанием из примера 1.

```bash
# Create P1 escalation policy: aggressive, short windows
curl -X POST "https://api.opsgenie.com/v2/escalations" \
  -H "Authorization: GenieKey YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Platform - P1 Critical",
    "description": "Customer-facing outage escalation chain",
    "ownerTeam": {"name": "Platform Team"},
    "rules": [
      {
        "condition": "if-not-acked",
        "notifyType": "default",
        "delay": {"timeAmount": 0, "timeUnit": "minutes"},
        "recipient": {
          "type": "schedule",
          "name": "Platform Team - Global"
        }
      },
      {
        "condition": "if-not-acked",
        "notifyType": "default",
        "delay": {"timeAmount": 5, "timeUnit": "minutes"},
        "recipient": {
          "type": "schedule",
          "name": "Platform Team - Global"
        }
      },
      {
        # Manager call at 10 min total elapsed (5+5). Hardcoded user is acceptable
        # for a manager escalation — managers do not rotate, so override risk is low.
        "condition": "if-not-acked",
        "notifyType": "default",
        "delay": {"timeAmount": 5, "timeUnit": "minutes"},
        "recipient": {
          "type": "user",
          "username": "vp-engineering@company.com"
        }
      }
    ],
    "repeat": {
      "waitInterval": 15,
      "count": 3,
      "resetRecipientStates": true,
      "closeAlertAfterAll": false   # Never auto-close production alerts
    }
  }'

# Create P3 escalation policy: relaxed, single step
curl -X POST "https://api.opsgenie.com/v2/escalations" \
  -H "Authorization: GenieKey YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Platform - P3 Medium",
    "description": "Non-critical alert — notify once, no repeat",
    "ownerTeam": {"name": "Platform Team"},
    "rules": [
      {
        "condition": "if-not-acked",
        "notifyType": "default",
        "delay": {"timeAmount": 0, "timeUnit": "minutes"},
        "recipient": {
          "type": "schedule",
          "name": "Platform Team - Global"
        }
      }
    ],
    "repeat": {
      "waitInterval": 60,
      "count": 1,
      "resetRecipientStates": false,
      "closeAlertAfterAll": false
    }
  }'

# Verify: list escalation policies for the team
curl -X GET \
  "https://api.opsgenie.com/v2/escalations?teamId=TEAM_ID_HERE" \
  -H "Authorization: GenieKey YOUR_API_KEY" | jq '.data[] | {name: .name, steps: (.rules | length)}'
# Expected output:
# {"name": "Platform - P1 Critical", "steps": 3}
# {"name": "Platform - P3 Medium",   "steps": 1}
```

---

### Пример 3. Автоматическое переопределение на период праздничных выходных

Скрипт читает CSV с запланированными отпусками и массово создаёт переопределения в Opsgenie. Это удобно для одновременного управления графиками отпусков на целый квартал.

```bash
#!/usr/bin/env bash
# bulk_overrides.sh
# CSV format: schedule_name,replacement_user,start_iso8601,end_iso8601,alias
# Example row: Platform Team - Global,carol@company.com,2024-12-23T00:00:00Z,2024-12-27T00:00:00Z,alice-xmas

API_KEY="${OPSGENIE_API_KEY:?Must set OPSGENIE_API_KEY}"
CSV_FILE="${1:?Usage: $0 overrides.csv}"

while IFS=',' read -r schedule replacement start end alias; do
  # Skip header line
  [[ "$schedule" == "schedule_name" ]] && continue

  echo "Creating override: $alias ($replacement covers $start → $end)"

  RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "https://api.opsgenie.com/v2/schedules/$(python3 -c "import urllib.parse; print(urllib.parse.quote('$schedule'))")/overrides" \
    -H "Authorization: GenieKey $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"user\": {\"type\": \"user\", \"username\": \"$replacement\"},
      \"startDate\": \"$start\",
      \"endDate\": \"$end\",
      \"alias\": \"$alias\"
    }")

  if [[ "$RESPONSE" == "201" ]]; then
    echo "  ✓ Created successfully"
  else
    echo "  ✗ Failed with HTTP $RESPONSE — check schedule name and user email"
  fi

done < "$CSV_FILE"
```

```csv
# overrides.csv
schedule_name,replacement_user,start_iso8601,end_iso8601,alias
Platform Team - Global,carol@company.com,2024-12-23T00:00:00Z,2024-12-27T00:00:00Z,alice-xmas
Platform Team - Global,dave@company.com,2024-12-28T00:00:00Z,2025-01-02T00:00:00Z,bob-newyear
```

```bash
# Run the script
chmod +x bulk_overrides.sh
export OPSGENIE_API_KEY="your_key_here"
./bulk_overrides.sh overrides.csv

# Verify: check who is on call on Dec 25
curl -s "https://api.opsgenie.com/v2/schedules/Platform%20Team%20-%20Global/on-calls?scheduleIdentifierType=name&flat=true&date=2024-12-25T12:00:00Z" \
  -H "Authorization: GenieKey $OPSGENIE_API_KEY" | jq '.data.onCallParticipants[].name'
# Expected: "Carol Smith"
```

---

### Пример 4. Интеграция Prometheus Alertmanager с Opsgenie

Подключите существующий Alertmanager, чтобы направлять оповещения в Opsgenie с правильным соответствием приоритетов.

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  receiver: 'opsgenie-default'
  routes:
    # P1: Any alert tagged severity=critical goes to the critical receiver
    - match:
        severity: critical
      receiver: 'opsgenie-p1'
      continue: false

    # P3: warnings route to low-priority receiver
    - match:
        severity: warning
      receiver: 'opsgenie-p3'
      continue: false

receivers:
  - name: 'opsgenie-p1'
    opsgenie_configs:
      - api_key: '<YOUR_OPSGENIE_API_KEY>'
        # api_url defaults to https://api.opsgenie.com/ — override for EU: https://api.eu.opsgenie.com/
        priority: 'P1'
        message: '{{ .GroupLabels.alertname }} — {{ .GroupLabels.cluster }}'
        description: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
        tags: 'env:production,team:platform'
        # Responders links the alert directly to the Platform Team in Opsgenie
        responders:
          - name: 'Platform Team'
            type: 'team'

  - name: 'opsgenie-p3'
    opsgenie_configs:
      - api_key: '<YOUR_OPSGENIE_API_KEY>'
        priority: 'P3'
        message: '{{ .GroupLabels.alertname }} — {{ .GroupLabels.cluster }}'
        description: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
        tags: 'env:production,team:platform'
        responders:
          - name: 'Platform Team'
            type: 'team'

  - name: 'opsgenie-default'
    opsgenie_configs:
      - api_key: '<YOUR_OPSGENIE_API_KEY>'
        priority: 'P2'
        message: '{{ .GroupLabels.alertname }}'
        responders:
          - name: 'Platform Team'
            type: 'team'
```

```bash
# Validate the alertmanager config before reloading
amtool check-config alertmanager.yml

# Reload without restart (if Alertmanager is running with --web.enable-lifecycle)
curl -X POST http://localhost:9093/-/reload

# Test: manually send a firing alert to Alertmanager and watch Opsgenie
amtool alert add \
  alertname="TestCriticalAlert" \
  severity="critical" \
  cluster="prod-us-east-1" \
  --annotation=description="Synthetic test alert — safe to acknowledge"

# Verify: the alert should appear in Opsgenie within ~30 seconds (group_wait)
# Check: Teams → Platform Team → Alert Activity
```

**Важно:** `repeat_interval: 12h` в Alertmanager означает, что неразрешённое оповещение повторно отправляется в Opsgenie каждые 12 часов. В зависимости от ключа дедупликации (`alias`) повтор может создать *новое* оповещение вместо обновления существующего, даже если исходное уже подтверждено. Чтобы включить дедупликацию, задайте в `opsgenie_configs` детерминированный `alias`, основанный на метках оповещения:

```yaml
alias: '{{ .GroupLabels.alertname }}-{{ .GroupLabels.cluster }}'
```

---

## Практические задания

### Задание 1. Проверьте расписание на пробелы в покрытии

**Цель:** отработать обнаружение и устранение пробелов с помощью API.

1. Создайте в интерфейсе Opsgenie расписание с одной недельной ротацией, ограниченной **понедельником–пятницей, 09:00–17:00 UTC**, и двумя участниками. Не добавляйте резервную ротацию.
2. Используйте API, чтобы узнать, кто дежурит **в субботу в 14:00 UTC**:
   ```bash
   curl -X GET \
     "https://api.opsgenie.com/v2/schedules/YOUR_SCHEDULE_NAME/on-calls?scheduleIdentifierType=name&flat=true&date=2024-06-15T14:00:00Z" \
     -H "Authorization: GenieKey YOUR_API_KEY" | jq '.data.onCallParticipants'
   ```
3. Убедитесь, что результат пуст (пробел в расписании). Затем добавьте через интерфейс резервную ротацию без временных ограничений и с одним участником (вы сами или тестовый пользователь).
4. Повторите тот же API-запрос и убедитесь, что резервный участник появился в результате.
5. **Объясните своими словами:** почему пробел в расписании приводит к незаметному отказу, а не к ошибке? К каким эксплуатационным последствиям может привести необнаруженный пробел в production?

---

### Задание 2. Спроектируйте политику эскалации с учётом SLA

**Цель:** преобразовать бизнес-требование в конфигурацию политики эскалации.

У вашей команды есть SLA: *«Оповещение P1 должно дойти до инженера в течение 5 минут, а до менеджера — в течение 15 минут, круглосуточно».*

1. До настройки интерфейса спроектируйте шаги политики на бумаге или в текстовом файле. Укажите:
   - Сколько шагов требуется политике.
   - Время ожидания между шагами.
   - Кого уведомляет каждый шаг (дежурного из расписания или конкретного пользователя).
   - Почему выбранная схема соблюдает SLA или создаёт риск его нарушения.
2. Создайте политику в интерфейсе Opsgenie для своей команды.
3. Проверьте суммарное время: если шаг 1 срабатывает в момент 0, сколько времени пройдёт до первого уведомления менеджера?
4. **Задание со звёздочкой:** измените политику так, чтобы ожидание шага 2 составляло 12 минут. Выполняется ли SLA «менеджер в течение 15 минут»? Покажите расчёт. Если нет, какое минимальное ожидание можно задать для шага 2 при пятиминутном ожидании шага 1?

---

### Задание 3. Автоматизируйте обмен сменами через API

**Цель:** использовать API переопределения Opsgenie для реального сценария обмена сменами без интерфейса.

**Сценарий:** на этой неделе дежурит Alice (недельная ротация). В среду с 10:00 до 13:00 UTC у неё приём у стоматолога, и она попросила Bob подменить её. Нужно:

1. Написать команду `curl`, создающую переопределение: Bob заменяет Alice ровно на этот интервал в ближайшую среду.
2. После создания переопределения запросить endpoint дежурств на **среду, 11:30 UTC** и убедиться, что в ответе указан Bob.
3. Повторить запрос для **среды, 14:00 UTC** (после окончания переопределения) и убедиться, что дежурство вернулось к Alice.
4. Удалить переопределение по полученному ID:
   ```bash
   curl -X DELETE \
     "https://api.opsgenie.com/v2/schedules/YOUR_SCHEDULE/overrides/OVERRIDE_ALIAS_OR_ID?scheduleIdentifierType=name" \
     -H "Authorization: GenieKey YOUR_API_KEY"
   ```
5. Ещё раз запросить состояние на **среду, 11:30 UTC** и убедиться, что снова дежурит Alice (переопределение удалено, ротация восстановлена).
6. **Вопрос для размышления:** если бы политика эскалации содержала жёстко заданный `alice@company.com`, а не ссылку на расписание, был бы Bob показан на шаге 2? Почему? Что это говорит о проектировании политик эскалации?

---

### Задание 4. Направьте оповещение источника в правильную политику эскалации

**Цель:** понять правила маршрутизации, построив полный путь оповещения от источника до инженера.

1. Создайте в Opsgenie две политики эскалации для своей команды:
   - `High-Priority` — три шага, ожидание по 5 минут, телефонный звонок на третьем шаге.
   - `Low-Priority` — один шаг без повторов.
2. Создайте два правила маршрутизации для команды:
   - Правило 1: если теги оповещения содержат `env:production`, направлять в `High-Priority`.
   - Правило 2 (универсальное): все остальные оповещения направлять в `Low-Priority`.
3. Используйте API Opsgenie, чтобы создать тестовое оповещение с тегом `env:production`:
   ```bash
   curl -X POST "https://api.opsgenie.com/v2/alerts" \
     -H "Authorization: GenieKey YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "Test production alert",
       "priority": "P1",
       "tags": ["env:production", "synthetic-test"],
       "details": {"source": "exercise-4"}
     }'
   ```
4. Найдите оповещение в интерфейсе Opsgenie и подтвердите, что оно направлено в `High-Priority`. На вкладке **Activity Log** проверьте, какие шаги эскалации сработали.
5. Создайте второе оповещение *без* тега `env:production` и проверьте, что оно направляется в `Low-Priority`.
6. **Вопрос для размышления:** что произойдёт, если поменять правила местами (сначала универсальное, затем конкретное)? Проверьте и объясните результат.

---

### Быстрая проверка

7. Рассчитайте количество часов в семидневном дежурстве. Выполните: `python3 -c "print(7 * 24)"`

```expected_output
168
```

Подсказка: используйте режим выполнения Python-команды прямо из терминала, чтобы вычислить математическое выражение.
Подсказка: используйте `python3 -c` и короткую команду `print`, перемножающую количество дней и часов в сутках.

8. Посчитайте участников в примере расписания дежурств. Выполните: `printf 'participants:\n- user: alice\n- user: bob\n- user: carol\n- user: dave\n' | grep -c '^- user:'`

```expected_output
4
```

Подсказка: `grep` умеет не только находить совпадения, но и сразу сообщать число подходящих строк.
Подсказка: используйте флаг `grep -c`, который считает строки по шаблону, например по префиксу `^- user:`.
