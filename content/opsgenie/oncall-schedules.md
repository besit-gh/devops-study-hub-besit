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

A platform team with engineers in London (EU) and New York (US East) wants continuous 24/7 weekday coverage. A team lead handles weekends.

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

The 14:00–15:00 UTC overlap between EU and US East rotations means both the outgoing EU engineer and the incoming US East engineer are technically on call simultaneously — a deliberate handoff window. The escalation policy should target the schedule (not individual users) so it automatically picks up whoever the current slot owner is.

---

### Example 2: Multi-Step Escalation Policy with Priority Tiers

This example creates two escalation policies — one for P1 and one for P3 — and wires them to the schedule from Example 1.

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

### Example 3: Automated Override for a Holiday Blackout Period

A script that reads a CSV of planned time-off and creates Opsgenie overrides in bulk. Useful for managing a whole quarter of vacation schedules at once.

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

### Example 4: Prometheus Alertmanager → Opsgenie Integration

Connect an existing Alertmanager deployment to route alerts into Opsgenie with the correct priority mapping.

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

**Gotcha:** Alertmanager's `repeat_interval: 12h` means if an alert fires and is not resolved, Alertmanager re-sends it to Opsgenie every 12 hours. If the Opsgenie alert is already acknowledged, the repeat sends create a *new* alert rather than updating the existing one, depending on your deduplication key (`alias` field). Set `alias` in `opsgenie_configs` to a deterministic value based on alert labels to enable deduplication:

```yaml
alias: '{{ .GroupLabels.alertname }}-{{ .GroupLabels.cluster }}'
```

---

## Практические задания

### Exercise 1: Audit a Schedule for Coverage Gaps

**Goal:** Practice identifying and fixing gaps using the API.

1. Create a schedule via the Opsgenie UI with a single weekly rotation restricted to **Monday–Friday, 09:00–17:00 UTC** with two participants. Do not add a fallback rotation.
2. Use the API to query who is on call on a **Saturday at 14:00 UTC**:
   ```bash
   curl -X GET \
     "https://api.opsgenie.com/v2/schedules/YOUR_SCHEDULE_NAME/on-calls?scheduleIdentifierType=name&flat=true&date=2024-06-15T14:00:00Z" \
     -H "Authorization: GenieKey YOUR_API_KEY" | jq '.data.onCallParticipants'
   ```
3. Observe the empty result (the gap). Now add a fallback rotation via the UI with no time restriction and a single participant (yourself or a test user).
4. Re-run the same API query and confirm the fallback participant appears.
5. **Explain in your own words:** Why does having a gap in a schedule result in a silent failure rather than an error? What are the operational consequences of an undetected gap in a production environment?

---

### Exercise 2: Design an Escalation Policy for an SLA Constraint

**Goal:** Translate a business requirement into escalation policy configuration.

Your team has an SLA that states: *"P1 alerts must reach an engineer within 5 minutes and a manager within 15 minutes, 24/7."*

1. Design the escalation policy steps on paper (or in a text file) before touching the UI. Specify:
   - How many steps the policy needs
   - The wait time between each step
   - Who each step notifies (on-call from schedule vs. named user)
   - Why each choice satisfies or risks violating the SLA
2. Create the policy in the Opsgenie UI under your team.
3. Verify the cumulative timing: if step 1 fires at 0 min, what is the total elapsed time when the manager is first contacted?
4. **Gotcha challenge:** Change your policy so that step 2 has a 12-minute wait. Does this still satisfy the "manager within 15 minutes" SLA? Show your math. If it doesn't, what is the minimum wait you can set at step 2 given a 5-minute step 1 wait?

---

### Exercise 3: Automate a Shift Swap via the API

**Goal:** Use the Opsgenie override API to handle a real-world shift swap scenario without touching the UI.

**Scenario:** Alice is on call this week (weekly rotation). She has a dentist appointment on Wednesday from 10:00–13:00 UTC and has asked Bob to cover. You need to:

1. Write a `curl` command to create an override replacing Alice with Bob for exactly that window on the next occurring Wednesday.
2. After creating the override, query the on-call endpoint for **Wednesday at 11:30 UTC** and confirm Bob appears.
3. Query again for **Wednesday at 14:00 UTC** (after the override ends) and confirm Alice has resumed.
4. Delete the override using its returned ID:
   ```bash
   curl -X DELETE \
     "https://api.opsgenie.com/v2/schedules/YOUR_SCHEDULE/overrides/OVERRIDE_ALIAS_OR_ID?scheduleIdentifierType=name" \
     -H "Authorization: GenieKey YOUR_API_KEY"
   ```
5. Query **Wednesday at 11:30 UTC** once more and confirm Alice is back on call (override deleted, rotation restored).
6. **Reflection question:** If your escalation policy hardcoded `alice@company.com` instead of referencing the schedule, would step 2 have shown Bob? Why or why not? What does this tell you about escalation policy design?

---

### Exercise 4: Map an Alert Source to the Correct Escalation Policy

**Goal:** Understand routing rules by building an end-to-end alert path from source to engineer.

1. In Opsgenie, create two escalation policies for your team:
   - `High-Priority` — three steps, 5-minute waits, phone call on step 3
   - `Low-Priority` — one step, no repeat
2. Create two routing rules for your team:
   - Rule 1: If alert tags contain `env:production` → route to `High-Priority`
   - Rule 2 (catch-all): All other alerts → route to `Low-Priority`
3. Use the Opsgenie API to create a test alert with the `env:production` tag:
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
4. In the Opsgenie UI, find the alert and confirm it was routed to `High-Priority`. Check the alert's **Activity Log** tab to see which escalation steps fired.
5. Create a second alert *without* the `env:production` tag and verify it routes to `Low-Priority`.
6. **Reflection question:** What would happen if you reversed the order of your routing rules (catch-all first, specific rule second)? Test it and explain the result.

---

### Быстрая проверка

7. Calculate hours in a 7-day on-call rotation. Run: `python3 -c "print(7 * 24)"`

```expected_output
168
```

hint: Think about how you can use Python's inline execution flag to evaluate a mathematical expression directly from the terminal.
hint: Use python3 -c to run a short print statement that multiplies the number of days by the number of hours in a day.

8. Count participants in an on-call schedule stub. Run: `printf 'participants:\n- user: alice\n- user: bob\n- user: carol\n- user: dave\n' | grep -c '^- user:'`

```expected_output
4
```

hint: Think about how grep can be used not just to find matches, but also to report the number of matching lines directly.
hint: Use grep with the -c flag, which counts the number of lines matching a given pattern, such as the line prefix '^- user:'.
