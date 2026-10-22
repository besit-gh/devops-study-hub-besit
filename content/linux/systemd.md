---
title: systemd и управление службами
module: linux
duration_min: 20
difficulty: intermediate
tags: [systemd, systemctl, journald, services, units]
exercises: 4
---

## Обзор

systemd — система инициализации и менеджер служб, работающий как PID 1 в основных дистрибутивах Linux: Ubuntu, Debian, RHEL, CentOS, Fedora, Arch и других. После загрузки ядро передаёт ему управление, и systemd запускает остальные процессы: монтирует файловые системы, поднимает сетевые интерфейсы, запускает демоны и подготавливает систему к входу пользователя. Для DevOps-инженера это означает, что с systemd приходится работать при развёртывании приложений, настройке автоматических перезапусков, диагностике упавших служб и создании расписаний — на виртуальной машине, физическом сервере или в контейнере с полноценным init-процессом.

В основе systemd лежат параллельный запуск, явное описание зависимостей и единая система журналирования. В отличие от последовательных скриптов SysV init, systemd строит граф зависимостей по unit-файлам и запускает независимые компоненты параллельно, сокращая время загрузки. Конфигурация служб хранится в декларативных файлах формата INI, а не в shell-скриптах, поэтому поведение проще проверять и аудировать. Журналирование централизовано в journald: он собирает stdout, stderr и сообщения ядра в структурированный бинарный журнал, который можно фильтровать одной командой — `journalctl`.

В архитектуре DevOps systemd расположен на инфраструктурном уровне под оркестрацией приложений. Даже если приложения работают в Docker или Kubernetes, а конфигурацией управляет Ansible, хосты используют systemd для запуска Docker daemon, kubelet, SSH-сервера и других базовых служб. Если служба падает, демон не запускается или цикл зависимостей мешает загрузке узла, диагностику начинают с systemd. Его понимание ускоряет разбор производственных инцидентов и помогает надёжнее автоматизировать развёртывание.

---

## Основные понятия

### Типы unit и расположение файлов

Всё, чем управляет systemd, называется *unit*. Unit описывается текстовым конфигурационным файлом с расширением, соответствующим типу. Чаще всего встречаются шесть типов:

| Тип | Расширение | Назначение |
|------|-----------|---------|
| **Service** | `.service` | Демон или процесс однократного выполнения |
| **Timer** | `.timer` | Замена cron — запускает `.service` по расписанию |
| **Socket** | `.socket` | Активация через сокет — запускает службу при первом подключении |
| **Mount** | `.mount` | Точки монтирования файловой системы под управлением systemd |
| **Target** | `.target` | Точки синхронизации и группы unit (аналог уровней запуска) |
| **Path** | `.path` | Запускает службу при изменении пути в файловой системе |

Unit-файлы загружаются из нескольких каталогов в порядке приоритета — от самого высокого к низкому:

| Каталог | Назначение |
|-----------|---------|
| `/etc/systemd/system/` | Локальные переопределения и пользовательские unit — **создавайте их здесь** |
| `/run/systemd/system/` | Unit, созданные во время работы (временные; исчезают после перезагрузки) |
| `/lib/systemd/system/` | Unit, установленные пакетами — **не редактируйте напрямую** |

Если файл с одним именем есть в нескольких каталогах, используется копия с наивысшим приоритетом. Файл `/etc/systemd/system/nginx.service` полностью перекрывает `/lib/systemd/system/nginx.service`.

**Drop-in-каталоги** — более безопасный способ переопределения. Для unit `nginx.service` systemd автоматически объединяет все `.conf`-файлы из `/etc/systemd/system/nginx.service.d/` с основной конфигурацией. Так можно изменить отдельный раздел, не копируя и не поддерживая весь исходный файл.

```bash
# Показать все загруженные unit-файлы и расположение их исходников
systemctl list-unit-files --type=service

# Показать, какой именно файл systemd использует для unit
systemctl cat nginx.service

# Показать итоговую конфигурацию после применения drop-in
systemctl show nginx.service
```

### Состояния служб

У службы есть два независимых измерения состояния: *состояние включения* (что произойдёт при загрузке) и *активное состояние* (что служба делает сейчас).

**Активные состояния:**

| Состояние | Значение |
|-------|---------|
| `active (running)` | Выполняется один или несколько процессов |
| `active (exited)` | Одноразовая служба успешно завершилась; systemd считает задачу выполненной |
| `active (waiting)` | Служба ожидает запускающего события |
| `inactive (dead)` | Не выполняется, ошибки нет |
| `failed` | Завершилась с ненулевым кодом, была остановлена сигналом или превысила тайм-аут |
| `activating` | Выполняется запуск |
| `deactivating` | Выполняется остановка |

**Состояния включения:**

| Состояние | Значение |
|-------|---------|
| `enabled` | Символическая ссылка есть в соответствующем каталоге `.wants/` или `.requires/` — служба запускается при загрузке |
| `disabled` | Ссылки нет — служба не запускается при загрузке, но её можно запустить вручную |
| `static` | Нет секции `[Install]` — нельзя включить или отключить; запускается только как зависимость |
| `masked` | Ссылка указывает на `/dev/null` — запуск невозможен, пока маска не снята |

**Маскирование и отключение:** `systemctl disable` удаляет ссылку автозапуска, но позволяет запускать unit вручную. `systemctl mask` полностью блокирует запуск — даже `systemctl start` завершится отказом. Маскируйте службы, которые не должны запускаться ни при каких обстоятельствах, например конфликтующую службу, установленную пакетом.

```bash
# Full status: active state, enable state, recent log lines, PID, memory
systemctl status nginx.service

# Check if a service is active/enabled in scripts (exits 0 or non-zero)
systemctl is-active nginx.service
systemctl is-enabled nginx.service

# Mask and unmask
systemctl mask snapd.service
systemctl unmask snapd.service
```

### Структура unit-файла

Файл unit типа `.service` состоит из трёх секций. Знание распространённых директив ускоряет создание и диагностику unit-файлов.

```ini
[Unit]
# Человекочитаемое описание для статуса и журнала
Description=My Application Server

# Порядок запуска: после этих unit, но без обязательной зависимости
After=network-online.target

# Мягкая зависимость: подключить unit, если он существует, но не считать отсутствие ошибкой
Wants=network-online.target

# Жёсткая зависимость: если postgresql.service не запустится, этот unit тоже завершится с ошибкой
Requires=postgresql.service

# Перезапускать этот unit при перезапуске другого (полезно для sidecar-сценариев)
PartOf=myapp-stack.target

[Service]
# Type определяет, как systemd понимает, что служба готова
# simple: готов сразу после запуска ExecStart (по умолчанию; подходит большинству демонов)
# forking: устаревший вариант; готов после двойного fork процесса (старые демоны)
# notify: готов, когда процесс отправляет sd_notify(READY=1)
# oneshot: для скриптов; systemd ждёт завершения процесса перед отметкой active
# exec: как simple, но ждёт успешного вызова exec()
Type=simple

User=myapp
Group=myapp
WorkingDirectory=/opt/myapp

ExecStart=/opt/myapp/bin/server --port 8080
# ExecReload отправляет SIGHUP процессу $MAINPID — используйте, только если приложение его обрабатывает
ExecReload=/bin/kill -HUP $MAINPID
# ExecStartPre выполняется перед ExecStart; ненулевой код блокирует запуск службы
ExecStartPre=/usr/bin/myapp-check-config

# Политики перезапуска
Restart=on-failure     # restart if exit code != 0 or killed by signal
RestartSec=5s          # wait 5s before restarting

# Переменные окружения
Environment=NODE_ENV=production
EnvironmentFile=/etc/myapp/env   # key=value pairs, one per line; # comments OK

# Лимиты ресурсов (переопределяют /etc/security/limits.conf для этой службы)
LimitNOFILE=65536

# Усиление безопасности
NoNewPrivileges=yes
PrivateTmp=yes         # isolated /tmp — processes can't see each other's temp files
ProtectSystem=strict   # mounts / and /usr read-only for this service
ReadWritePaths=/var/lib/myapp /var/log/myapp

[Install]
# Какой target включает эту службу — фактически уровень запуска, к которому она относится
WantedBy=multi-user.target   # стандарт для большинства серверных демонов
```

**Важный нюанс `Type=simple` и `Type=notify`:** если службе нужно время на подготовку (например, загрузить большую модель или выполнить миграции БД), при `Type=simple` systemd считает её запущенной сразу после старта процесса. Службы с `After=myapp.service` могут начать работу до готовности `myapp`. Если приложение поддерживает `sd_notify` (например, через Node.js `systemd-notify`, Go `coreos/go-systemd` или Python `sdnotify`), используйте `Type=notify`, чтобы корректно сообщать о готовности.

**`Requires` и `Wants`:** `Requires` задаёт жёсткую зависимость: если `postgresql.service` завершится с ошибкой, зависимая служба тоже не запустится. `Wants` задаёт мягкую зависимость и не блокирует запуск при сбое PostgreSQL. В большинстве случаев подходит сочетание `Wants` и `After`: оно задаёт порядок запуска без излишней связи между отказами.

**`After` не подразумевает `Wants`:** одна директива `After=postgresql.service` задаёт только порядок запуска и не запускает PostgreSQL. Чтобы добавить зависимость и одновременно задать порядок, объедините `After` с `Wants` или `Requires`.

### Подробно о политиках перезапуска

| Политика | Перезапуск при успешном завершении (0)? | Перезапуск при ошибке? | Перезапуск при SIGTERM? |
|--------|----------------------------|---------------------|---------------------|
| `no` | No | No | No |
| `on-success` | Да | Нет | Нет |
| `on-failure` | Нет | Да | Нет |
| `on-abnormal` | Нет | Да (сигналы, watchdog, тайм-аут) | Да |
| `on-abort` | Нет | Только необработанные сигналы | Нет |
| `always` | Да | Да | Да |

Для долгоживущих серверных приложений стандартный выбор — `Restart=on-failure`: служба восстановится после аварии или OOM kill, но не будет перезапускаться бесконечно после намеренного `systemctl stop`.

**Защита от циклического перезапуска:** если служба перезапускается слишком часто, systemd прекращает попытки. По умолчанию допускается пять перезапусков за десять секунд. Настройте ограничения так:

```ini
[Unit]
StartLimitIntervalSec=60s   # окно наблюдения
StartLimitBurst=5           # максимум перезапусков в этом окне
StartLimitAction=none       # или reboot-force, reboot, poweroff
```

**`RestartSec` зависит от `StartLimitBurst`:** при `RestartSec=30s` и `StartLimitBurst=5` лимит не будет достигнут, если пять сбоев не произойдут в пределах 60 секунд с учётом задержек. Настраивайте эти параметры совместно.

**Расположение директив:** в новых версиях systemd (≥ 230) `StartLimitIntervalSec` и `StartLimitBurst` указываются в секции `[Unit]`, а не `[Service]`. В старых версиях они размещаются в `[Service]`. Неправильное расположение может быть проигнорировано без явной ошибки; проверяйте через `systemctl show myapp.service | grep StartLimit`.

```bash
# После достижения лимита перезапусков сбросьте счётчик ошибок, чтобы разрешить ручной запуск
systemctl reset-failed myapp.service
systemctl start myapp.service
```

### Targets (уровни запуска)

Targets — точки синхронизации, именованные этапы, через которые проходит процесс загрузки. Они заменяют уровни запуска SysV.

| Уровень запуска SysV | Target systemd | Значение |
|--------------|---------------|---------|
| 0 | `poweroff.target` | Выключение |
| 1 | `rescue.target` | Однопользовательский режим / восстановление |
| 3 | `multi-user.target` | Многопользовательский режим без GUI (типичный сервер) |
| 5 | `graphical.target` | Многопользовательский режим с графической оболочкой |
| 6 | `reboot.target` | Перезагрузка |

```bash
# Проверить target по умолчанию
systemctl get-default

# Изменить target по умолчанию (например, для сервера без GUI)
systemctl set-default multi-user.target

# Переключиться в rescue-режим без перезагрузки (только для интерактивных систем)
systemctl isolate rescue.target

# Посмотреть все unit, входящие в target, и их зависимости
systemctl list-dependencies multi-user.target
```

При выполнении `systemctl enable myapp.service` systemd создаёт символическую ссылку `/etc/systemd/system/multi-user.target.wants/myapp.service` (если задано `WantedBy=multi-user.target`). Target включает службу в набор запускаемых зависимостей, поэтому при достижении `multi-user.target` systemd запустит её.

**`enable` не запускает службу:** `systemctl enable` только создаёт ссылку для следующей загрузки. Используйте `systemctl enable --now`, чтобы включить автозапуск и запустить службу одной командой. Забытый флаг `--now` — распространённая ошибка развёртывания: конфигурация выглядит готовой, но служба не работает.

### Таймеры — замена cron

Таймеры systemd состоят из пары unit: `.timer`, задающего расписание, и соответствующего `.service`, выполняющего работу. В отличие от cron, таймеры интегрированы с journald и сохраняют полный журнал, поддерживают порядок зависимостей, монотонные расписания (относительно загрузки) и календарные расписания (по часам), а также управляются стандартными командами `systemctl`.

```ini
# /etc/systemd/system/db-backup.service
[Unit]
Description=Database Backup

[Service]
Type=oneshot
User=backup
ExecStart=/usr/local/bin/db-backup.sh
# No [Install] section — this service is only invoked by the timer, never enabled directly
```

```ini
# /etc/systemd/system/db-backup.timer
[Unit]
Description=Run database backup daily at 02:00

[Timer]
# Calendar expression: daily at 02:00 local time
OnCalendar=*-*-* 02:00:00
# If the system was off at 02:00, run the job within 15 minutes of next boot
Persistent=true
# Randomize start time within a 10-minute window to avoid thundering herd
RandomizedDelaySec=10min
# Which service to trigger (defaults to same name with .service extension)
Unit=db-backup.service

[Install]
WantedBy=timers.target
```

```bash
# Включить таймер и запустить его (не саму службу напрямую)
systemctl enable --now db-backup.timer

# Показать таймеры и время следующего/последнего запуска
systemctl list-timers --all

# Запустить задачу вручную, не дожидаясь расписания
systemctl start db-backup.service

# Проверить последний запуск через журнал
journalctl -u db-backup.service -n 50
```

**`Persistent=true` обеспечивает догоняющий запуск, похожий на catch-up для cron:** без него задача, пропущенная из-за выключенной системы, будет пропущена окончательно. С ним systemd выполнит её один раз после следующей загрузки, если плановый запуск не состоялся. Это важно для резервного копирования и обслуживания систем, которые не работают постоянно.

| Тип таймера | Директива | Пример | Значение |
|-----------|-----------|---------|---------|
| Календарное время | `OnCalendar` | `Mon *-*-* 09:00:00` | Каждый понедельник в 09:00 |
| Относительно загрузки | `OnBootSec` | `OnBootSec=5min` | Через 5 минут после загрузки |
| Относительно активации | `OnActiveSec` | `OnActiveSec=1h` | Через час после запуска таймера |
| Относительно активности unit | `OnUnitActiveSec` | `OnUnitActiveSec=30min` | Через 30 минут после завершения последнего запуска |

### journalctl — запросы к журналу

journald собирает stdout, stderr, сообщения syslog, сообщения ядра и записи аудита в структурированный бинарный журнал. Он хранится в `/var/log/journal/` (постоянно) или `/run/log/journal/` (временно — теряется после перезагрузки). Бинарный формат позволяет выполнять сложную фильтрацию на стороне сервера до передачи данных в терминал.

```bash
# --- Basic service filtering ---
journalctl -u nginx                          # all logs for nginx.service
journalctl -u nginx -f                       # follow (like tail -f)
journalctl -u nginx -n 100                   # last 100 lines
journalctl -u nginx -b                       # since last boot
journalctl -u nginx -b -1                    # the boot before last

# --- Time filtering ---
journalctl -u nginx --since "2024-01-15 10:00:00"
journalctl -u nginx --since "1 hour ago"
journalctl -u nginx --since today --until "2024-01-15 12:00:00"

# --- Priority filtering (syslog levels) ---
journalctl -u nginx -p err                   # errors and above (emerg, alert, crit, err)
journalctl -u nginx -p warning..err          # range: warning to err

# --- Multiple units ---
journalctl -u nginx -u php-fpm               # logs interleaved from both services

# --- Output formats ---
journalctl -u nginx -o json-pretty           # structured JSON — great for parsing
journalctl -u nginx -o cat                   # message text only, no metadata
journalctl -u nginx --no-pager               # don't page; useful in scripts

# --- Kernel / system-wide ---
journalctl -k                                # kernel messages only (dmesg equivalent)
journalctl -b                                # all messages from current boot
journalctl --list-boots                      # show available boot records

# --- Disk usage and cleanup ---
journalctl --disk-usage
journalctl --vacuum-size=500M               # trim journal to 500MB
journalctl --vacuum-time=30d                # remove entries older than 30 days
```

**Особенность хранения:** в новой установке Debian/Ubuntu журнал может быть временным (храниться в `/run/`) и теряться после перезагрузки. Чтобы сделать его постоянным:

```bash
mkdir -p /var/log/journal
systemd-tmpfiles --create --prefix /var/log/journal
systemctl restart systemd-journald
```

Or set `Storage=persistent` in `/etc/systemd/journald.conf`.

**Ограничение частоты:** по умолчанию journald ограничивает число сообщений от каждой службы (`RateLimitIntervalSec=30s`, `RateLimitBurst=10000`). Если служба превышает лимит, часть записей отбрасывается, а в журнале появляется `Suppressed N messages from myapp.service`. Для важных, но многословных служб увеличьте лимиты в `/etc/systemd/journald.conf` или уменьшите подробность логирования приложения.

**Передача в syslog или внешние системы:** для централизованного сбора журналов (например, в Elasticsearch, Loki или Splunk) задайте `ForwardToSyslog=yes` в `journald.conf` либо передавайте вывод `journalctl -o json` в систему сбора. Многие современные агенты (Promtail, Filebeat, Fluentd) умеют читать журнал напрямую через API, не обращаясь к файлам.

### Переопределение unit-файлов пакетов

Правильный способ переопределения настроек — drop-in-файлы, а не прямое редактирование `/lib/systemd/system/`: обновление пакета может перезаписать изменения без предупреждения.

```bash
# Preferred: use systemctl edit — opens $EDITOR, saves to the right place automatically
systemctl edit nginx
# Saves to: /etc/systemd/system/nginx.service.d/override.conf

# To override the entire unit (not just add stanzas), use --full
systemctl edit --full nginx
# Saves to: /etc/systemd/system/nginx.service (a full copy)
# Warning: you now own the full file — upstream changes won't reach you
```

В drop-in-файле достаточно указать только те секции, которые требуется изменить. systemd объединит их с исходным файлом:

```ini
# /etc/systemd/system/nginx.service.d/limits.conf
[Service]
LimitNOFILE=65536
LimitCORE=infinity
```

**Сброс директивы:** чтобы отменить директиву из базового unit, сначала задайте ей пустое значение, а затем укажите новое. Это обязательно для списочных директив вроде `ExecStart`: если добавить второй `ExecStart` без сброса, получится второй запуск, а не замена исходного:

```ini
[Service]
# Clear the upstream ExecStart before setting your own — required for ExecStart
ExecStart=
ExecStart=/usr/sbin/nginx -c /etc/nginx/nginx-custom.conf
```

После любого изменения файла unit:

```bash
systemctl daemon-reload    # re-read all unit files from disk
systemctl restart nginx    # apply changes to the running service
```

**`daemon-reload` обязателен.** Изменение unit-файла на диске не действует до перезагрузки конфигурации systemd. Если забыть этот шаг, можно изменить файл и перезапустить службу, но старое поведение сохранится, поскольку systemd использует кэшированную версию.

### Диагностика загрузки и проблем зависимостей

Если сервис не запускается, следуйте последовательному алгоритму диагностики:

```bash
# Step 1: Check status — shows last few log lines inline
systemctl status myapp.service

# Step 2: Get full logs for this boot
journalctl -u myapp.service -b

# Step 3: Check what systemd thinks happened — exit code, signal, timing
systemctl show myapp.service --property=ExecMainStatus,ExecMainCode,Result

# Step 4: Inspect the dependency graph to find ordering problems
systemctl list-dependencies myapp.service
systemctl list-dependencies myapp.service --reverse  # what depends ON myapp?

# Step 5: Check for failed units system-wide
systemctl --failed

# Step 6: Analyze boot time for slow units
systemd-analyze blame             # sorted list of units by startup time
systemd-analyze critical-chain    # the critical path that determined total boot time
systemd-analyze verify myapp.service  # static lint check of the unit file
```

**Значения поля `Result`:** при сбое службы `systemctl show` показывает причину в поле `Result`:

| Result | Значение |
|--------|---------|
| `success` | Завершилась успешно |
| `exit-code` | Ненулевой код завершения |
| `signal` | Завершена сигналом (проверьте `ExecMainCode`) |
| `core-dump` | Процесс создал core dump |
| `watchdog` | Истёк тайм-аут watchdog |
| `start-limit-hit` | Достигнут лимит перезапусков |
| `oom-kill` | Завершён механизмом OOM killer |

**`oom-kill` в production:** если видите `Result=oom-kill`, ядру не хватило памяти и оно завершило процесс — это не перезапуск systemd. Проверьте `journalctl -k | grep oom`: сообщения OOM killer содержат статистику памяти на момент завершения. Решение может быть на уровне приложения (утечка памяти, слишком большая heap) или хоста (добавить RAM, настроить лимиты памяти cgroups).

---

## Примеры

### Пример 1: развёртывание API на Node.js как службы systemd

**Сценарий:** приложение Node.js находится в `/opt/api/server.js`; оно должно работать от отдельного пользователя, перезапускаться при сбое и запускаться при загрузке системы.

```bash
# Создать отдельного системного пользователя без домашнего каталога и login shell
useradd --system --no-create-home --shell /usr/sbin/nologin apiuser

# Создать файл окружения (не хранить секреты в unit-файле)
mkdir -p /etc/api
cat > /etc/api/env <<'EOF'
NODE_ENV=production
PORT=3000
DATABASE_URL=postgres://user:pass@localhost/mydb
EOF
chmod 600 /etc/api/env
chown root:apiuser /etc/api/env
```

```ini
# /etc/systemd/system/api.service
[Unit]
Description=My Node.js API Server
Documentation=https://github.com/myorg/api
After=network-online.target postgresql.service
Wants=network-online.target
# Мягкая зависимость от postgres: если служба не запущена, ошибка возникнет при подключении
# systemd не будет блокировать запуск в ожидании этой службы
Requires=postgresql.service

[Service]
Type=simple
User=apiuser
Group=apiuser
WorkingDirectory=/opt/api

# Загрузить секреты из файла, принадлежащего root; процесс получит их как переменные окружения
EnvironmentFile=/etc/api/env

ExecStartPre=/usr/bin/node --check /opt/api/server.js   # syntax check before starting
ExecStart=/usr/bin/node /opt/api/server.js

# Перезапускать при сбое, OOM kill или сигнале, но НЕ после штатной остановки (systemctl stop)
Restart=on-failure
RestartSec=10s

# Ограничить перезапуски: если за 2 минуты произойдёт 5 сбоев, прекратить попытки
StartLimitIntervalSec=120s
StartLimitBurst=5

# Безопасность: убрать capabilities и изолировать файловую систему
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/log/api /var/lib/api

# Журналирование: stdout/stderr направляются прямо в journald, отдельный файл не нужен
StandardOutput=journal
StandardError=journal
SyslogIdentifier=api-server

[Install]
WantedBy=multi-user.target
```

```bash
# Установить и запустить службу
systemctl daemon-reload
systemctl enable --now api.service

# Проверить, что служба успешно запустилась
systemctl status api.service

# Проверить журналы запуска
journalctl -u api.service -b -n 50

# Проверить восстановление после имитации сбоя
kill -9 $(systemctl show api.service --property=MainPID --value)
# Подождать 10 секунд (RestartSec) и проверить перезапуск
sleep 12 && systemctl status api.service
```

---

### Пример 2: замена задания cron таймером systemd

**Сценарий:** cron ежедневно запускает `/usr/local/bin/cleanup-old-logs.sh` в 03:00. Перенесите задачу на таймер systemd, чтобы сбои отображались в `systemctl --failed`, а журналы попадали в journald.

```ini
# /etc/systemd/system/cleanup-logs.service
[Unit]
Description=Clean up application logs older than 30 days
After=local-fs.target

[Service]
Type=oneshot
# Run as root because logs are in /var/log with mixed ownership
User=root
ExecStart=/usr/local/bin/cleanup-old-logs.sh
# On success, write a timestamp so we can verify last run
ExecStartPost=/bin/sh -c 'date > /var/run/cleanup-logs-last-run'

# If the script fails, send an alert via a notification script
OnFailure=notify-on-failure@%n.service

# No [Install] section — started exclusively by the timer
```

```ini
# /etc/systemd/system/cleanup-logs.timer
[Unit]
Description=Daily log cleanup at 03:00

[Timer]
OnCalendar=*-*-* 03:00:00
# Randomize within 20 minutes to avoid all servers hitting storage simultaneously
RandomizedDelaySec=20min
# Run once on next boot if last scheduled run was missed (e.g., server was down)
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
# Remove the old cron job first
crontab -l | grep -v cleanup-old-logs | crontab -

# Deploy the timer
systemctl daemon-reload
systemctl enable --now cleanup-logs.timer

# Confirm it's scheduled
systemctl list-timers cleanup-logs.timer

# Test the service immediately without waiting for 3AM
systemctl start cleanup-logs.service

# Check the result
systemctl status cleanup-logs.service
journalctl -u cleanup-logs.service -n 30
cat /var/run/cleanup-logs-last-run
```

---

### Пример 3: переопределение службы пакета через drop-in

**Сценарий:** установленная пакетом служба `postgresql.service` использует настройки памяти по умолчанию. Нужно задать `POSTGRES_HUGE_PAGES=try` и увеличить лимит открытых файлов, не копируя весь unit-файл.

```bash
# Inspect what the package provides
systemctl cat postgresql.service

# Create a drop-in — systemctl edit opens $EDITOR automatically
# and places the file in the correct .d/ directory
systemctl edit postgresql.service
```

```ini
# systemctl edit places this at:
# /etc/systemd/system/postgresql.service.d/override.conf

[Service]
# Raise file descriptor limit for many concurrent connections
LimitNOFILE=102400

# Add an environment variable on top of whatever the package sets
# (note: we are NOT clearing Environment= first, so this is additive)
Environment=POSTGRES_HUGE_PAGES=try

# Run a pre-start check that the data directory has correct ownership
ExecStartPre=/bin/sh -c 'stat -c "%U" /var/lib/postgresql/data | grep -q postgres || exit 1'
```

```bash
# Reload systemd and apply changes
systemctl daemon-reload

# Verify the merged configuration shows your additions
systemctl cat postgresql.service      # shows base + drop-in markers
systemctl show postgresql.service --property=LimitNOFILE,Environment

# Restart to apply
systemctl restart postgresql.service
systemctl status postgresql.service
```

---

### Пример 4: диагностика службы, которая не запускается

**Сценарий:** после развёртывания `myapp.service` находится в состоянии `failed`. Выполните полную диагностику.

```bash
# Шаг 1: краткая сводка — проверить код завершения и последние строки журнала
systemctl status myapp.service
# Output shows: "code=exited, status=1/FAILURE"

# Шаг 2: полный журнал текущей загрузки для просмотра ошибки
journalctl -u myapp.service -b --no-pager
# Output: "Error: cannot open config file /etc/myapp/config.yaml: no such file"

# Шаг 3: программно проверить код результата
systemctl show myapp.service --property=Result,ExecMainStatus
# Result=exit-code
# ExecMainStatus=1

# Шаг 4: проверить, не завершился ли с ошибкой ExecStartPre
journalctl -u myapp.service -b -p err

# Шаг 5: проверить наличие бинарного файла и конфигурации по ожидаемым путям
systemctl cat myapp.service | grep Exec
# ExecStart=/opt/myapp/bin/server --config /etc/myapp/config.yaml

ls -la /etc/myapp/config.yaml
# ls: cannot access '/etc/myapp/config.yaml': No such file or directory

# Fix: restore the config file from your configuration management or backup
cp /etc/myapp/config.yaml.example /etc/myapp/config.yaml
chown myapp:myapp /etc/myapp/config.yaml

# Restart and verify
systemctl start myapp.service
systemctl status myapp.service
# Active: active (running) since ...

# Step 6: If restart loop was hit, reset the failure counter first
systemctl reset-failed myapp.service
systemctl start myapp.service
```

---

## Практические задания

### Задание 1: создать и развернуть собственный unit службы

Создайте минимальный веб-сервер на встроенном HTTP-сервере Python и настройте управление им как полноценной службой systemd.

1. Создайте системного пользователя `webdemo` без login shell.
2. Создайте `/etc/systemd/system/webdemo.service`, который:
   - Runs `python3 -m http.server 8888` from `/var/www/html` as the `webdemo` user.
   - Sets `Restart=on-failure` and `RestartSec=5s`.
   - Enables with `WantedBy=multi-user.target`.
   - Sets `NoNewPrivileges=yes` and `PrivateTmp=yes`.
3. Включите автозапуск и запустите службу. Проверьте её командами `systemctl status` и `curl localhost:8888`.
4. Имитируйте сбой, отправив `SIGKILL` основному PID. Убедитесь, что служба перезапускается в течение 10 секунд.
5. Найдите в журнале событие перезапуска. Какие сообщения systemd записывает между сбоем и успешным запуском?

**Что нужно выяснить:** как получить MainPID без жёстко заданного значения? Какие сведения показывает `systemctl show`? Почему `PrivateTmp=yes` не влияет на `curl`, запущенный из вашей оболочки?

---

### Задание 2: исследовать и исправить сломанную службу

**Подготовка:** выполните команды, чтобы создать службу с ошибкой:

```bash
cat > /etc/systemd/system/broken.service <<'EOF'
[Unit]
Description=Intentionally Broken Service

[Service]
Type=simple
ExecStart=/usr/local/bin/nonexistent-binary
Restart=on-failure
RestartSec=2s
StartLimitBurst=3
StartLimitIntervalSec=30s

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl start broken.service || true
```

**Задания:**

1. Используйте `systemctl status` и `journalctl`, чтобы точно определить причину сбоя. Какое значение имеет `Result`?
2. Когда лимит перезапусков будет исчерпан, какое итоговое состояние покажет `systemctl status`?
3. Исправьте службу, создав `/usr/local/bin/nonexistent-binary` как скрипт, который выводит `hello` и завершается с кодом 0. Какой дополнительный шаг нужен, чтобы systemd увидел исправление?
4. Служба достигла лимита перезапусков. Как сбросить его и запустить службу заново без перезагрузки?
5. Перенесите `StartLimitBurst` и `StartLimitIntervalSec` в секцию `[Unit]`. Выполните `systemd-analyze verify broken.service`. Что результат говорит о unit-файле?

---

### Задание 3: заменить cron-задачу таймером systemd

**Сценарий:** у вас есть cron-задача: `*/5 * * * * /usr/local/bin/health-check.sh >> /var/log/health-check.log 2>&1`

1. Напишите `health-check.sh`: он должен проверять, открыт ли порт 80 на localhost, используя `nc` или `curl`, и возвращать ненулевой код, если порт закрыт.
2. Создайте `health-check.service` (`Type=oneshot`) и `health-check.timer`, запускающий задачу каждые 5 минут. **Не** перенаправляйте вывод в файл — пусть его сохраняет journald.
3. Включите таймер и убедитесь, что `systemctl list-timers` показывает время следующего запуска.
4. Намеренно остановите nginx (или другую службу на порту 80) и вручную запустите `systemctl start health-check.service`. Убедитесь, что ошибка видна в `systemctl --failed` и `journalctl -u health-check.service`.
5. Объясните, почему таймер systemd с `Persistent=true` надёжнее cron для задачи на ноутбуке или spot-инстансе, который может быть выключен в запланированное время.

---

### Задание 4: отработать drop-in-переопределения и изучить итоговую конфигурацию

1. Найдите установленный пакетом unit-файл `ssh.service` (или `sshd.service`) и выведите его командой `systemctl cat`.
2. Use `systemctl edit sshd.service` to add a drop-in that:
   - Sets `RestartSec=10s` and `Restart=always`.
   - Adds `Environment=MY_CUSTOM_VAR=devops-practice`.
3. Without restarting sshd yet, use `systemctl show sshd.service` to confirm your changes are reflected in the merged configuration. What command shows you only the `Restart` and `RestartSec` properties?
4. Apply the changes by reloading and restarting sshd. Verify the service is still reachable via SSH.
5. Now undo your changes cleanly: delete the drop-in file, reload the daemon, and confirm `systemctl cat sshd.service` no longer shows your override. What is the path of the file you need to remove?

---

### Быстрая проверка

1. Extract the `Restart` value from a unit file snippet.

   ```bash
   printf '[Service]\nExecStart=/bin/true\nRestart=on-failure\n' | awk -F= '/^Restart=/{print $2}'
   ```

   ```expected_output
   on-failure
   ```

hint: Think about which command-line tool can search for a specific pattern and extract matching text from a file.
hint: Use grep with a pattern like 'Restart=' to filter the line, then pipe it to cut -d'=' -f2 (or awk -F'=' '{print $2}') to isolate the value after the equals sign.

2. Extract the `WantedBy` value from a unit file snippet.

   ```bash
   printf '[Install]\nWantedBy=multi-user.target\n' | awk -F= '/^WantedBy=/{print $2}'
   ```

   ```expected_output
   multi-user.target
   ```
hint: Think about which command-line tool can search for and extract specific patterns from text files.
hint: Use grep with the pattern 'WantedBy=' on the unit file, then pipe to cut or awk to isolate just the value after the equals sign.
