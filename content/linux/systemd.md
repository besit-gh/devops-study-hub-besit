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
# List all loaded unit files and their source locations
systemctl list-unit-files --type=service

# Show exactly which file systemd is using for a unit
systemctl cat nginx.service

# Show the final merged configuration after drop-ins are applied
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
| `on-success` | Yes | No | No |
| `on-failure` | No | Yes | No |
| `on-abnormal` | No | Yes (signals, watchdog, timeout) | Yes |
| `on-abort` | No | Uncaught signals only | No |
| `always` | Yes | Yes | Yes |

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
| 0 | `poweroff.target` | Halt |
| 1 | `rescue.target` | Single-user / recovery mode |
| 3 | `multi-user.target` | Multi-user, no GUI (typical server) |
| 5 | `graphical.target` | Multi-user + display manager |
| 6 | `reboot.target` | Reboot |

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
| Calendar (wall clock) | `OnCalendar` | `Mon *-*-* 09:00:00` | Every Monday at 09:00 |
| Boot-relative | `OnBootSec` | `OnBootSec=5min` | 5 minutes after boot |
| Activation-relative | `OnActiveSec` | `OnActiveSec=1h` | 1 hour after timer starts |
| Unit-active-relative | `OnUnitActiveSec` | `OnUnitActiveSec=30min` | 30 min after last run completes |

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

**Persistence gotcha:** On a fresh Debian/Ubuntu install, the journal may be volatile (stored in `/run/`) and lost on reboot. To make it persistent:

```bash
mkdir -p /var/log/journal
systemd-tmpfiles --create --prefix /var/log/journal
systemctl restart systemd-journald
```

Or set `Storage=persistent` in `/etc/systemd/journald.conf`.

**Rate limiting:** journald rate-limits log lines per service by default (`RateLimitIntervalSec=30s`, `RateLimitBurst=10000`). A chatty service that exceeds this will have log lines dropped, and you'll see `Suppressed N messages from myapp.service` in the journal. Raise the limits in `/etc/systemd/journald.conf` for noisy but important services, or fix the application's log verbosity.

**Forwarding to syslog/external systems:** For centralized log shipping (e.g., to Elasticsearch, Loki, Splunk), set `ForwardToSyslog=yes` in `journald.conf` or use `journalctl -o json` piped to your log shipper. Many modern agents (Promtail, Filebeat, Fluentd) can read the journal natively via the journal API without touching files at all.

### Overriding Package Unit Files

The correct override workflow is drop-in files, not editing `/lib/systemd/system/` directly (package upgrades will overwrite your changes with no warning).

```bash
# Preferred: use systemctl edit — opens $EDITOR, saves to the right place automatically
systemctl edit nginx
# Saves to: /etc/systemd/system/nginx.service.d/override.conf

# To override the entire unit (not just add stanzas), use --full
systemctl edit --full nginx
# Saves to: /etc/systemd/system/nginx.service (a full copy)
# Warning: you now own the full file — upstream changes won't reach you
```

A drop-in only needs the stanzas you want to change. systemd merges them on top of the base file:

```ini
# /etc/systemd/system/nginx.service.d/limits.conf
[Service]
LimitNOFILE=65536
LimitCORE=infinity
```

**Clearing a directive:** To unset a directive inherited from the base unit, set it to empty first, then set your value. This is mandatory for list-type directives like `ExecStart` — appending a second `ExecStart` without clearing adds a second execution, not a replacement:

```ini
[Service]
# Clear the upstream ExecStart before setting your own — required for ExecStart
ExecStart=
ExecStart=/usr/sbin/nginx -c /etc/nginx/nginx-custom.conf
```

After any unit file change:

```bash
systemctl daemon-reload    # re-read all unit files from disk
systemctl restart nginx    # apply changes to the running service
```

**`daemon-reload` is mandatory.** Editing a unit file on disk has zero effect until you reload. Forgetting this step is a very common source of confusion — you change the file, restart the service, and the old behavior persists because systemd is still running from its cached version.

### Diagnosing Boot and Dependency Problems

When a service fails to start, the debugging sequence follows a predictable path:

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

**`Result` field meanings:** When a service fails, `systemctl show` exposes a `Result` field that tells you *why* it failed:

| Result | Meaning |
|--------|---------|
| `success` | Exited cleanly |
| `exit-code` | Non-zero exit status |
| `signal` | Killed by a signal (check `ExecMainCode`) |
| `core-dump` | Process dumped core |
| `watchdog` | Watchdog timeout expired |
| `start-limit-hit` | Restart loop limit was reached |
| `oom-kill` | Killed by the OOM killer |

**`oom-kill` in production:** If you see `Result=oom-kill`, the kernel ran out of memory and killed your process — this is not a systemd restart. Check `journalctl -k | grep oom` for the kernel OOM killer's own log lines, which include memory stats at the time of the kill. The fix is at the application level (memory leak, oversized heap) or the host level (more RAM, cgroups memory limits).

---

## Примеры

### Example 1: Deploying a Node.js API as a systemd Service

**Scenario:** You have a Node.js application at `/opt/api/server.js` that should run as a dedicated user, restart on failure, and start at boot.

```bash
# Create a dedicated system user (no home directory, no login shell)
useradd --system --no-create-home --shell /usr/sbin/nologin apiuser

# Create the environment file (keep secrets out of the unit file)
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
# Soft dep on postgres — if it's not running, we'll fail at connection time
# but systemd won't block our start waiting for it
Requires=postgresql.service

[Service]
Type=simple
User=apiuser
Group=apiuser
WorkingDirectory=/opt/api

# Load secrets from a root-owned file — process inherits them as env vars
EnvironmentFile=/etc/api/env

ExecStartPre=/usr/bin/node --check /opt/api/server.js   # syntax check before starting
ExecStart=/usr/bin/node /opt/api/server.js

# Restart on crash, OOM kill, or signal — but NOT on clean exit (systemctl stop)
Restart=on-failure
RestartSec=10s

# Restart loop: if it crashes 5 times in 2 minutes, give up
StartLimitIntervalSec=120s
StartLimitBurst=5

# Security: drop capabilities and isolate filesystem
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/log/api /var/lib/api

# Logging: stdout/stderr go directly to journald — no log file needed
StandardOutput=journal
StandardError=journal
SyslogIdentifier=api-server

[Install]
WantedBy=multi-user.target
```

```bash
# Install and start the service
systemctl daemon-reload
systemctl enable --now api.service

# Verify it came up correctly
systemctl status api.service

# Check startup logs
journalctl -u api.service -b -n 50

# Test that it survives a simulated crash
kill -9 $(systemctl show api.service --property=MainPID --value)
# Wait 10 seconds (RestartSec), then check it restarted
sleep 12 && systemctl status api.service
```

---

### Example 2: Replacing a Cron Job with a systemd Timer

**Scenario:** A cron job runs `/usr/local/bin/cleanup-old-logs.sh` every day at 3 AM. Migrate it to a systemd timer so failures appear in `systemctl --failed` and logs are captured in journald.

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

### Example 3: Overriding a Package-Installed Service with a Drop-In

**Scenario:** The package-installed `postgresql.service` uses a default memory configuration. You need to set `POSTGRES_HUGE_PAGES=try` and raise the open file limit without owning the entire unit file.

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

### Example 4: Diagnosing a Service That Fails to Start

**Scenario:** After a deployment, `myapp.service` shows `failed` state. Walk through the full diagnosis.

```bash
# Step 1: Quick overview — note the exit code and the last few log lines
systemctl status myapp.service
# Output shows: "code=exited, status=1/FAILURE"

# Step 2: Full logs from this boot to see the complete error
journalctl -u myapp.service -b --no-pager
# Output: "Error: cannot open config file /etc/myapp/config.yaml: no such file"

# Step 3: Confirm the result code programmatically
systemctl show myapp.service --property=Result,ExecMainStatus
# Result=exit-code
# ExecMainStatus=1

# Step 4: Check if ExecStartPre failed (common cause — pre-check exits non-zero)
journalctl -u myapp.service -b -p err

# Step 5: Verify the binary and config exist where the unit expects them
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

### Exercise 1: Write and Deploy a Custom Service Unit

Create a minimal web server using Python's built-in HTTP server and manage it as a proper systemd service.

1. Create a system user `webdemo` with no login shell.
2. Write `/etc/systemd/system/webdemo.service` that:
   - Runs `python3 -m http.server 8888` from `/var/www/html` as the `webdemo` user.
   - Sets `Restart=on-failure` and `RestartSec=5s`.
   - Enables with `WantedBy=multi-user.target`.
   - Sets `NoNewPrivileges=yes` and `PrivateTmp=yes`.
3. Enable and start the service. Verify with `systemctl status` and `curl localhost:8888`.
4. Simulate a crash by sending `SIGKILL` to the main PID. Confirm the service restarts within 10 seconds.
5. Check the journal for the restart event. What log lines does systemd emit between the crash and the successful restart?

**What to figure out:** How do you find the MainPID without hardcoding it? What does `systemctl show` expose? Why does `PrivateTmp=yes` not affect `curl` running in your shell?

---

### Exercise 2: Investigate and Fix a Broken Service

**Setup:** Run this to create a broken service:

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

**Tasks:**

1. Use `systemctl status` and `journalctl` to determine exactly why the service failed. What is the `Result` value?
2. After the restart loop exhausts itself, what does `systemctl status` show as the final state?
3. Fix the service by creating `/usr/local/bin/nonexistent-binary` as a script that prints "hello" and exits 0. What additional step is required before systemd will find the fix?
4. The service is now stuck in the restart limit. How do you clear it and start fresh without rebooting?
5. Move `StartLimitBurst` and `StartLimitIntervalSec` to the `[Unit]` section. Run `systemd-analyze verify broken.service`. What does this tell you about your unit file?

---

### Exercise 3: Build a systemd Timer to Replace a Cron Job

**Scenario:** You have this cron job: `*/5 * * * * /usr/local/bin/health-check.sh >> /var/log/health-check.log 2>&1`

1. Write `health-check.sh` — it should check if port 80 is open on localhost using `nc` or `curl` and exit non-zero if it's not.
2. Write a `health-check.service` (Type=oneshot) and `health-check.timer` that runs every 5 minutes. Do **not** redirect output to a file — let journald capture it.
3. Enable the timer and verify `systemctl list-timers` shows the next trigger time.
4. Deliberately stop nginx (or any service on port 80) and manually trigger `systemctl start health-check.service`. Confirm the failure appears in `systemctl --failed` and in `journalctl -u health-check.service`.
5. Answer: why is a systemd timer with `Persistent=true` more reliable than cron for a job on a laptop or a spot instance that may not always be running at the scheduled time?

---

### Exercise 4: Practice Drop-In Overrides and Inspect Merged Configuration

1. Find the package-installed unit file for `ssh.service` (or `sshd.service`). Display it with `systemctl cat`.
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
