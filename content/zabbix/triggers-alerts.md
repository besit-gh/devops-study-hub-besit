---
title: Триггеры и оповещения Zabbix
module: zabbix
duration_min: 20
difficulty: intermediate
tags: [zabbix, triggers, alerting, media-types, actions, escalation, maintenance]
exercises: 3
---

## Обзор
Триггеры Zabbix — логические выражения, вычисляемые по значениям элементов данных. Когда выражение становится истинным (состояние PROBLEM), Zabbix создаёт событие, которое может запустить уведомления, автоматическое исправление или создание тикета. Конвейер оповещений — triggers → events → actions → media types — составляет операционное ядро Zabbix. Умение правильно писать выражения триггеров, настраивать уведомления по нескольким каналам, строить эскалации и подавлять оповещения во время планового обслуживания важно и на собеседованиях, и в повседневной работе. Ошибки в выражениях триггеров часто приводят к alert fatigue.

## Основные понятия

### Выражения триггеров
Выражение триггера принимает значение 0 (OK) или 1 (PROBLEM). Язык выражений использует функции, применяемые к истории элементов данных.

**Базовый синтаксис выражения:**
```
last(/hostname/item.key) operator threshold
```

**Распространённые функции триггеров:**

| Функция | Описание | Пример |
|----------|-------------|---------|
| `last()` | Последнее значение | `last(/host/agent.ping) = 0` |
| `avg(,Xs)` | Среднее за временной интервал | `avg(/host/system.cpu.load,300s) > 5` |
| `min(,Xs)` | Минимум за интервал | `min(/host/net.if.in[eth0],60s) < 100` |
| `max(,Xs)` | Максимум за интервал | `max(/host/vfs.fs.size[/,pused],3600s) > 90` |
| `nodata(,Xs)` | Истина, если данные не поступали X секунд | `nodata(/host/agent.ping,300s) = 1` |
| `diff()` | Истина, если последнее значение отличается от предыдущего | `diff(/host/system.uname) = 1` |
| `count(,Xs,pattern)` | Число значений, соответствующих шаблону в интервале | `count(/host/log[/var/log/app.log,ERROR],60s,like,ERROR) > 10` |
| `change()` | Абсолютная разница между двумя последними значениями | `change(/host/system.cpu.load) > 2` |
| `fuzzytime(,Xs)` | Истина, если время узла отличается от времени сервера более чем на X секунд | `fuzzytime(/host/system.localtime,60s) = 0` |

**Выражения с несколькими условиями:**
```
# CPU high AND memory low (compound problem)
avg(/web-01/system.cpu.util[,user],300s) > 85
and
last(/web-01/vm.memory.size[pavailable]) < 10

# Disk full on any filesystem (using LLD-created items)
last(/web-01/vfs.fs.size[/data,pused]) > 95
or
last(/web-01/vfs.fs.size[/,pused]) > 95
```

**Рекомендации по выражениям триггеров:**
- Для CPU и памяти используйте `avg()` за интервал вместо `last()`, чтобы избежать ложных срабатываний из-за единичного измерения.
- Задавайте **выражение восстановления**, определяющее, когда PROBLEM сбрасывается: это предотвращает слишком быстрое переключение триггера обратно в OK.
- Перед внедрением всегда проверяйте выражения через **Configuration → Hosts → Items → Test**.

**Пример выражения восстановления:**
```
Problem:  avg(/host/system.cpu.load[all,avg1],300s) > 5
Recovery: avg(/host/system.cpu.load[all,avg1],300s) < 3
```
Триггер срабатывает при нагрузке выше 5, но сбрасывается только после падения ниже 3. Такой гистерезис предотвращает частые переключения состояния.

### Уровни серьёзности
В Zabbix есть шесть встроенных уровней серьёзности для приоритизации и маршрутизации оповещений.

| Уровень | Цвет | Типичное применение |
|-------|-------|-------------|
| Не классифицировано | Серый | По умолчанию, триггеры ещё не рассмотрены |
| Информация | Синий | Информационные события: изменение конфигурации, плановая перезагрузка |
| Предупреждение | Жёлтый | Ранние признаки проблемы: диск заполнен на 75%, CPU загружен на 60% |
| Средний | Оранжевый | Требующие действий проблемы: деградация сервиса |
| Высокий | Красный | Сервис серьёзно нарушен — требуется немедленное внимание |
| Авария | Тёмно-красный | Полный отказ — немедленно вызовите дежурного |

Фильтры серьёзности доступны в настройках типов каналов и действий. Например, оповещения уровня Disaster можно направлять в PagerDuty, а Warning — только в Slack.

### Зависимости триггеров
Зависимости триггеров предотвращают лавину вторичных оповещений. Когда срабатывает триггер первопричины, зависимые триггеры подавляются, даже если их условия тоже истинны.

**Пример:**
- Триггер A: «Узел недоступен» (не работает сетевой коммутатор)
- Триггер B: «Порт SSH недоступен на web-01»
- Триггер C: «HTTP-проверка на web-01 завершается ошибкой»

If A depends on (is blocked by) B and C: when the switch goes down, B and C fire but A does NOT notify if B or C is already in PROBLEM state.

Чаще зависимость настраивают наоборот: B и C зависят от A. Если срабатывает A (узел недоступен), B и C подавляются, поскольку первопричина уже известна.

**Настройка зависимостей:**
```
Configuration → Triggers → (select trigger) → Dependencies tab → Add
```

Добавьте зависимость: «Этот триггер подавляется, когда срабатывает: [родительский триггер]»

### Типы каналов уведомлений
Тип канала уведомлений определяет, как Zabbix доставляет сообщения. Он не зависит от маршрутизации и может использоваться в нескольких действиях.

**Встроенные типы каналов:**
- Электронная почта (SMTP)
- SMS (через скрипты внешнего шлюза)
- Webhook (обычный HTTP)

**Настройка канала электронной почты:**
```
SMTP server:    smtp.gmail.com
SMTP port:      587
SMTP helo:      gmail.com
SMTP email:     zabbix@example.com
Security:       STARTTLS
Authentication: Username/Password
Username:       zabbix@example.com
Password:       <app password>
```

**Канал Slack webhook:**
В Zabbix есть встроенный тип канала Slack. Настройка:
```
Media type: Slack
bot_token:   xoxb-your-bot-token
channel:     #alerts
```
В шаблоне сообщения используются макросы Zabbix:
```
{TRIGGER.NAME} on {HOST.NAME}
Severity: {TRIGGER.SEVERITY}
Status: {TRIGGER.STATUS}
```

**Пользовательский канал webhook (обычный HTTP):**
```
Name: PagerDuty
Type: Webhook
URL: https://events.pagerduty.com/v2/enqueue
Request method: POST
Headers:
  Content-Type: application/json
Parameters:
  payload: {
    "routing_key": "{$PD_INTEGRATION_KEY}",
    "event_action": "trigger",
    "dedup_key": "{EVENT.ID}",
    "payload": {
      "summary": "{TRIGGER.NAME}",
      "severity": "{TRIGGER.SEVERITY}",
      "source": "{HOST.NAME}",
      "custom_details": {
        "item_value": "{ITEM.VALUE}"
      }
    }
  }
```

**Назначение типа канала пользователю:**
```
Administration → Users → (user) → Media tab → Add
Type: Slack
Send to: @username
When active: 1-7,00:00-24:00
Use if severity: Warning, Average, High, Disaster
```

### Настройка действий
Действия определяют логику маршрутизации: когда триггер срабатывает и соответствует заданным условиям, уведомление отправляется выбранным пользователям через определённый канал.

**Компоненты действия:**
1. **Условия** — фильтруют события, запускающие действие (по группе узлов, серьёзности триггера, регулярному выражению имени и т. д.)
2. **Операции** — что выполнить (отправить сообщение, запустить удалённую команду)
3. **Операции восстановления** — что делать, когда триггер возвращается в OK
4. **Операции обновления** — что делать, когда событие подтверждено

**Пример действия — уведомление дежурного при уровне Disaster/High:**
```
Action name: Notify Platform On-Call

Conditions (ALL must match):
  - Trigger severity >= High
  - Host group = Linux servers

Operations:
  - Step 1: Send message to user: oncall-user via PagerDuty
    Default operation step duration: 1h

Recovery operations:
  - Send message to user: oncall-user via PagerDuty
    (Uses recovery message template)
```

### Этапы эскалации
Действия Zabbix поддерживают многоэтапную эскалацию. Если проблема не подтверждена в течение заданного интервала, запускается следующий этап.

```
Step 1 (0-1h):   Send Slack to #alerts-platform
Step 2 (1h-2h):  Send PagerDuty to on-call engineer
Step 3 (2h+):    Send PagerDuty to engineering manager
                 + Run remote command: /usr/local/bin/auto-restart-service.sh
```

**Длительность этапа операции:** каждый этап действует в течение заданного интервала. Если событие **подтверждено** до запуска следующего этапа, эскалация прекращается. Это можно настроить так, чтобы она продолжалась и после подтверждения.

**Операции удалённых команд** запускают скрипты на агентах Zabbix или самом сервере. Используйте их осторожно: удалённое выполнение расширяет поверхность атаки. Ограничьте доступ настройкой `AllowKey=system.run[*]` в конфигурации агента и включайте `EnableRemoteCommands=1` только при необходимости.

### Окна обслуживания
Окна обслуживания подавляют оповещения для выбранных узлов или групп во время плановых работ, не удаляя триггеры.

**Создание окна обслуживания:**
```
Configuration → Maintenance → Create maintenance

Name: Monthly kernel patching - web tier
Maintenance type: With data collection (metrics still stored)
Active since/till: 2026-06-01 02:00 – 2026-06-01 04:00

Hosts/Groups: Linux servers → web-tier group

Schedule type: One time only
```

`With data collection` — метрики продолжают собираться, подавляются только уведомления. Полезно для анализа после обслуживания.
`No data collection` — элементы данных не опрашиваются. Используйте, если узел выключен.

**Повторяющееся обслуживание:**
Задайте `Schedule type: Weekly` или `Monthly` и укажите нужные дни для циклов установки обновлений.

## Примеры

**Полный цикл оповещения — предупреждение о месте на диске с эскалацией:**

1. Элемент данных: `vfs.fs.size[/data,pused]` (сбор каждые 5 минут)
2. Trigger:
   ```
   Problem: last(/web-01/vfs.fs.size[/data,pused]) > 85
   Recovery: last(/web-01/vfs.fs.size[/data,pused]) < 80
   Severity: Warning
   ```
3. Условия действия: серьёзность триггера = Warning, группа узлов = Web Tier
4. Операции:
   - Этап 1 (0–30 мин): Slack `#alerts` — «Диск /data заполнен на {ITEM.VALUE}% на {HOST.NAME}»
   - Этап 2 (30 мин – 2 ч): отправить вызов дежурному через PagerDuty
5. Операции восстановления: Slack `#alerts` — «РЕШЕНО: диск /data теперь заполнен на {ITEM.VALUE}%»

**Проверка выражения триггера без ожидания реальных данных:**
```
Configuration → Hosts → Items → (select item) → Test
```
Введите тестовое значение и проверьте, что триггер сработал бы.

**Проверка активных оповещений через API:**
```bash
curl -s -X POST http://zabbix-server/api_jsonrpc.php \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "trigger.get",
    "params": {
      "only_true": 1,
      "selectHosts": ["host"],
      "output": ["description", "priority", "lastchange"]
    },
    "auth": "<auth-token>",
    "id": 1
  }' | jq '.result[] | {host: .hosts[0].host, trigger: .description, severity: .priority}'
```

## Практические задания

1. Напишите выражение триггера для узла, которое срабатывает с уровнем `Average`, если средняя нагрузка CPU за 5 минут превышает 4 более трёх минут подряд, и восстанавливается только при падении ниже 2. Добавьте выражение восстановления и объясните, почему здесь важно использовать `avg()`, а не `last()`.
2. Настройте действие с тремя этапами эскалации: этап 1 отправляет сообщение в Slack `#alerts`; этап 2 через 30 минут без подтверждения отправляет оповещение дежурному через PagerDuty; этап 3 через час отправляет письмо руководителю инженерной команды. Установите условия так, чтобы действие срабатывало только для уровней `High` или `Disaster` в группе узлов `Production`.
3. Создайте окно обслуживания для группы узлов с 02:00 до 04:00 UTC в первое воскресенье каждого месяца, используя режим `With data collection`. Проверьте, что активный триггер узла из этой группы не отправляет уведомления во время окна, но данные по-прежнему видны в **Monitoring → Latest data**.


---

### Быстрая проверка

4. Проверьте простой порог триггера Zabbix. Выполните: `python3 -c "cpu=85; threshold=80; print('PROBLEM' if cpu > threshold else 'OK')"`

```expected_output
PROBLEM
```

Подсказка: Python можно использовать прямо в командной строке для вычисления условия.
Подсказка: используйте `python3 -c`, чтобы выполнить короткий скрипт, сравнивающий переменную `cpu` с порогом через условие if/else и `print()`.

5. Посчитайте уровни серьёзности триггеров Zabbix. Выполните: `printf 'Not classified\nInformation\nWarning\nAverage\nHigh\nDisaster\n' | wc -l`

```expected_output
6
```

Подсказка: посчитайте количество строк в выводе команды.
Подсказка: передайте строки через конвейер в `wc -l`, который подсчитывает количество строк.
