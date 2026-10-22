---
title: Задания cron
module: linux
duration_min: 10
difficulty: beginner
tags: [cron, crontab, scheduling, automation]
exercises: 3
---

## Обзор

Cron — встроенный планировщик задач Linux, существующий практически во всех Unix-подобных системах с 1970-х годов. Он запускает команды и скрипты в заданное время или через определённые интервалы без участия человека. Для DevOps-инженера это простой и надёжный инструмент регулярных операций: ротации журналов, резервного копирования баз данных, синхронизации файлов с объектным хранилищем, удаления старых Docker-образов, опроса API и запуска проверок работоспособности. Дополнительная инфраструктура не нужна; cron доступен сразу после загрузки машины.

Cron намеренно устроен минималистично: каждая задача — одна строка в обычном текстовом файле. Нет графа зависимостей, повторных попыток или распределённой координации — только «запусти эту команду в это время». Простота одновременно является преимуществом и ограничением. Cron подходит, если расписание предсказуемо, задача автономна, а ошибку можно допустить или обработать внутри скрипта. Если нужны повторы, оповещения об ошибках, цепочки задач или распределённое выполнение, стоит использовать Airflow, Kubernetes CronJobs или systemd timers. Понимание ограничений cron помогает выбирать правильный инструмент.

В DevOps cron остаётся базовым инструментом. Он появился задолго до контейнеров и CI/CD, но продолжает использоваться и сегодня. В Kubernetes для расписаний есть ресурс `CronJob`, который добавляет возможности наблюдаемости и управления перезапусками, сохраняя привычный синтаксис из пяти временных полей. У Ansible, Puppet и Chef есть модули для управления crontab. Уверенное владение cron помогает понимать расписания в любой инфраструктуре.

---

## Основные понятия

### Синтаксис crontab

Каждая задача cron занимает одну строку: пять временных полей, а затем команда для выполнения. Поля разделяются пробелами и имеют фиксированный порядок.

```
┌─ minute        (0–59)
│ ┌─ hour         (0–23)
│ │ ┌─ day of month  (1–31)
│ │ │ ┌─ month        (1–12 or Jan–Dec)
│ │ │ │ ┌─ day of week   (0–7, both 0 and 7 = Sunday; or Sun–Sat)
│ │ │ │ │
* * * * *  /path/to/command --args
```

Умение читать cron-выражения постоянно нужно при ревью кода, работе с runbook и расследовании инцидентов. Попробуйте читать выражение справа налево: «в какие дни недели, в какие месяцы, в какие дни месяца, в какие часы и минуты». Например:

```
30 2 * * 1   →  "at minute 30 of hour 2, any day of month, any month, on Monday"
             →  Every Monday at 2:30 AM
```

**Взаимодействие дня месяца и дня недели:** если в обоих полях указано значение, отличное от `*`, cron запускает задачу при выполнении *любого* из условий, а не обоих одновременно. Это часто удивляет новичков.

```bash
# This does NOT mean "on the 1st if it's a Monday"
# It means "on the 1st of any month OR any Monday"
0 9 1 * 1   /usr/bin/script.sh
```

Перед развёртыванием проверяйте выражения с помощью [crontab.guru](https://crontab.guru). Ошибка в расписании — частая причина того, что задача в production незаметно не запускается.

---

### Синтаксис значений полей

| Символ | Значение | Пример | Как читать |
|--------|---------|---------|----------|
| `*` | Любое значение / каждый | `* * * * *` | Каждую минуту |
| `,` | Список значений | `0,30 * * * *` | В начале и на 30-й минуте каждого часа |
| `-` | Включительный диапазон | `0 9-17 * * *` | В начале каждого часа с 9:00 до 17:00 |
| `/` | Интервал шага | `*/15 * * * *` | Каждые 15 минут |
| `/` с диапазоном | Шаг внутри диапазона | `0 8-18/2 * * *` | Каждые два часа с 8:00 до 18:00 |

Шаги и диапазоны можно комбинировать. `*/15` — сокращение для `0-59/15`. `0-23/6` означает «каждые шесть часов, начиная с нуля»: 0, 6, 12, 18.

**Именованные сокращения** — некоторые реализации cron (Vixie cron, cronie) поддерживают эти строки вместо пяти полей:

| Сокращение | Эквивалент | Значение |
|----------|------------|---------|
| `@reboot` | *(нет)* | Один раз при запуске cron |
| `@hourly` | `0 * * * *` | Каждый час в начале часа |
| `@daily` | `0 0 * * *` | Каждый день в полночь |
| `@midnight` | `0 0 * * *` | Псевдоним `@daily` |
| `@weekly` | `0 0 * * 0` | Каждое воскресенье в полночь |
| `@monthly` | `0 0 1 * *` | Первого числа каждого месяца в полночь |
| `@yearly` | `0 0 1 1 *` | Первого января в полночь |

**Важный нюанс `@reboot`:** задача запускается при старте демона cron, а не строго при загрузке ОС. Если crond перезапустится во время работы системы, задача выполнится повторно. Не используйте `@reboot` для инициализации, которая должна происходить строго один раз.

---

### Где хранятся задания cron

Задания cron хранятся в разных местах. Расположение определяет владельца задачи, пользователя, от имени которого она запускается, и способ развёртывания.

| Расположение | Назначение | Нужно поле пользователя | Кто устанавливает |
|----------|---------|---------------------|-------------|
| `crontab -e` (для пользователя) | Личные задачи по расписанию | Нет (неявно) | Сам пользователь |
| `/etc/crontab` | Общесистемный файл | **Да** | Root / управление конфигурацией |
| `/etc/cron.d/` | Общесистемный каталог, отдельный файл на приложение | **Да** | Пакеты и управление конфигурацией |
| `/etc/cron.hourly/` | Скрипты, запускаемые каждый час | Нет | Поместить исполняемый скрипт |
| `/etc/cron.daily/` | Скрипты, запускаемые ежедневно | Нет | Поместить исполняемый скрипт |
| `/etc/cron.weekly/` | Скрипты, запускаемые еженедельно | Нет | Поместить исполняемый скрипт |
| `/etc/cron.monthly/` | Скрипты, запускаемые ежемесячно | Нет | Поместить исполняемый скрипт |

**`/etc/cron.d/` — подходящее место для заданий приложения в production.** При развёртывании через пакет, Ansible или Chef поместите в `/etc/cron.d/` файл с именем приложения. Так задания проще находить, проверять и хранить в системе контроля версий. Файлы в `/etc/cron.d/` должны принадлежать root и не должны быть доступны для записи всем пользователям: cron молча игнорирует файлы, не прошедшие проверку прав.

**`crontab -e` предназначен для личных или разовых задач.** Такие задания хранятся в `/var/spool/cron/crontabs/<username>` и исчезают при удалении пользователя. Не используйте личные crontab для production-нагрузок: другие администраторы могут даже не знать об этих заданиях.

Каталоги `cron.daily/` запускаются во время, заданное в `/etc/crontab` (на Debian/Ubuntu часто в 06:25). На настольных системах точное время контролирует `anacron`, учитывающий, что компьютер может быть выключен. На серверах обычно лучше задавать точное расписание через `cron.d`, а не полагаться на каталоги daily/weekly.

---

### Проблема окружения

Это самая частая причина сбоев cron. При запуске задания cron **не** загружает стартовые файлы shell: ни `~/.bashrc`, ни `~/.profile`, ни `/etc/profile`. Окружение почти пустое.

**Окружение cron по умолчанию (примерно):**
```
HOME=/root          (or the user's home)
LOGNAME=username
USER=username
SHELL=/bin/sh       (not bash — /bin/sh)
PATH=/usr/bin:/bin  (nothing else)
```

Это приводит к двум типам сбоев:

1. **Команда не найдена** — `/usr/local/bin/python3`, `aws`, `node` и `docker` отсутствуют в `/usr/bin:/bin`
2. **Неправильное поведение** — скрипт работает в интерактивном режиме, потому что загружает конфигурацию, задающую `AWS_REGION`, `JAVA_HOME`, `VIRTUAL_ENV` и другие переменные.

**Решение 1 — явно задайте переменные в начале crontab:**

```bash
# /etc/cron.d/myapp
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/go/bin
MAILTO=oncall@example.com
AWS_DEFAULT_REGION=us-east-1

30 2 * * * deploy /usr/local/bin/backup.sh
```

**Решение 2 — используйте абсолютные пути во всех командах:**

```bash
30 2 * * * deploy /usr/bin/aws s3 sync /data s3://mybucket/ >> /var/log/backup.log 2>&1
```

**Решение 3 — загрузите окружение внутри скрипта:**

```bash
#!/bin/bash
# backup.sh
source /etc/profile.d/myapp.sh
export JAVA_HOME=/usr/lib/jvm/java-17
# ... rest of script
```

**Совет по диагностике:** если задание работает вручную, но падает в cron, воспроизведите минимальное окружение командой:

```bash
env -i HOME=/root SHELL=/bin/bash PATH=/usr/bin:/bin /bin/bash --noprofile --norc /usr/local/bin/yourscript.sh
```

Команда очищает окружение примерно до того состояния, в котором его видит cron, и обычно сразу выявляет отсутствующую переменную или бинарный файл.

---

### Обработка вывода и журналирование

По умолчанию, если задача cron что-либо выводит в stdout или stderr, cron пытается отправить вывод пользователю по электронной почте через локальный MTA. На большинстве серверов MTA отсутствует, поэтому вывод молча теряется. На серверах с MTA почта может быстро переполниться. В обоих случаях нужна явная стратегия обработки вывода.

```bash
# BAD — output goes to local mail or nowhere. You'll never know if it failed.
30 2 * * * /usr/bin/backup.sh

# GOOD — append stdout and stderr to a log file
30 2 * * * /usr/bin/backup.sh >> /var/log/backup.log 2>&1

# GOOD — timestamp each run, then append output
30 2 * * * { echo "=== $(date -Iseconds) ==="; /usr/bin/backup.sh; } >> /var/log/backup.log 2>&1

# OK — suppress all output (only if the script handles its own logging)
*/5 * * * * /usr/bin/healthcheck.sh > /dev/null 2>&1

# GOOD — send errors to a specific address (requires working MTA)
MAILTO=alerts@example.com
30 2 * * * /usr/bin/backup.sh > /dev/null  # stdout suppressed; stderr mailed
```

**Порядок `2>&1` важен.** Он должен идти после перенаправления: `>> /var/log/backup.log 2>&1`. Обратный порядок — `2>&1 >> /var/log/backup.log` — сначала направляет stderr в терминал, а затем stdout в файл. В результате ошибки оказываются не там, где ожидалось, и теряются из журнала.

**Ротация журналов:** если cron бесконечно добавляет записи в файл, тот будет расти без ограничений. Реализуйте ротацию в самом скрипте или добавьте конфигурацию logrotate в `/etc/logrotate.d/`.

```
/var/log/backup.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    create 0640 root root
}
```

---

### Предотвращение параллельных запусков

Cron не проверяет, работает ли предыдущий экземпляр задания. Если резервное копирование длится 70 минут и запускается ежедневно в 02:00, в 03:00 cron всё равно попытается запустить его снова. Два процесса будут конкурировать за одну базу данных, файлы блокировок или путь вывода.

**Используйте `flock` для блокировки через файл:**

```bash
# -n = non-blocking (exit immediately if lock is held, don't queue)
# /tmp/backup.lock is created automatically if it doesn't exist
30 2 * * * flock -n /tmp/backup.lock /usr/bin/backup.sh >> /var/log/backup.log 2>&1
```

**Используйте `flock` с тайм-аутом:**

```bash
# Wait up to 10 seconds for the lock; if still held, give up
30 2 * * * flock -w 10 /tmp/backup.lock /usr/bin/backup.sh >> /var/log/backup.log 2>&1
```

**Шаблон блокировки внутри скрипта:**

```bash
#!/bin/bash
# backup.sh — self-locking via file descriptor
LOCKFILE=/tmp/backup.lock

exec 9>"${LOCKFILE}"
flock -n 9 || { echo "[$(date -Iseconds)] Already running, exiting."; exit 1; }

# All work happens here; lock released automatically on exit
echo "[$(date -Iseconds)] Starting backup..."
```

**Особенность `flock`:** блокировка привязана к файловому дескриптору, а не к пути файла. Она автоматически снимается при завершении процесса, в том числе аварийном (сбой или сигнал kill). Поэтому не остаётся устаревших файлов блокировки, которые нужно удалять вручную, в отличие от подходов с `mkdir` или `pidfile`.

| Locking method | Stale lock risk | Works across scripts | Notes |
|---------------|----------------|----------------------|-------|
| `flock` | None (kernel-managed) | Yes | Preferred; available on all Linux systems |
| `mkdir` | Yes — must clean up | No | Fragile; avoid |
| PID file | Yes — must validate PID | Yes | More complex; used by some daemons |

---

### Команды управления crontab

```bash
# Edit your crontab (uses $EDITOR or $VISUAL, defaults to vi/nano)
crontab -e

# List your current crontab
crontab -l

# Remove all your cron jobs — NO CONFIRMATION PROMPT
crontab -r

# Remove with confirmation (supported on most modern systems)
crontab -i -r

# Edit another user's crontab (must be root)
crontab -u www-data -e

# List another user's crontab
crontab -u deploy -l

# Install a crontab from a file (replaces existing entirely)
crontab /path/to/mycrontab.txt

# Pipe a crontab in (useful in provisioning scripts)
echo "*/5 * * * * /usr/bin/healthcheck.sh > /dev/null 2>&1" | crontab -
```

**Подводный камень с `crontab -r` и `-e`:** клавиши `r` и `e` расположены рядом. Если вместо `-e` ошибочно ввести `-r`, все задания cron удалятся без подтверждения и возможности отмены. Храните crontab под контролем версий — например, как задачу Ansible или файл в репозитории, — чтобы восстановить его через Git, а не по памяти.

---

### Проверка выполнения заданий cron

Отсутствие вывода не означает, что задание действительно выполнялось. Всегда проверяйте журналы.

```bash
# Ubuntu/Debian — cron logs to syslog
grep CRON /var/log/syslog | tail -30

# RedHat/CentOS — dedicated cron log
tail -30 /var/log/cron

# systemd-based systems — via journald
journalctl -u cron --since "1 hour ago"
journalctl -u crond -f          # follow in real time (RHEL/CentOS uses crond)
journalctl -u cron --since today --grep "backup"

# Example syslog output showing successful launch:
# Jun 15 02:30:01 server CRON[12345]: (root) CMD (/usr/bin/backup.sh >> /var/log/backup.log 2>&1)
```

The syslog entry confirms cron *launched* the job. Whether the job *succeeded* is a separate question — you need the job's own log output or exit code for that. A common pattern is to emit a final `echo "SUCCESS $(date -Iseconds)"` at the end of a script and then grep for it to confirm completion.

**Checking for silent failures:**

```bash
# Confirm the last run left a success marker
grep "SUCCESS" /var/log/backup.log | tail -1

# Alert if the backup log hasn't been written to in over 25 hours
find /var/log/backup.log -mmin +1500 && echo "ALERT: backup may not have run"
```

**Dead Man's Snitch / Healthchecks.io pattern:** For critical cron jobs, send an HTTP ping to an external monitoring service at the end of the script. If the ping doesn't arrive within the expected window, the service alerts you. This catches both missed runs and silent failures.

```bash
#!/bin/bash
# backup.sh — with dead man's snitch
set -e
/usr/bin/pg_dump mydb | gzip > /backups/mydb-$(date +%Y%m%d).sql.gz
# Only reached if the above succeeded (set -e)
curl -fsS --retry 3 https://hc-ping.com/your-uuid-here > /dev/null
```

---

### Cron Security Considerations

Cron jobs run with real user permissions. A misconfigured job can be a privilege escalation vector.

**`/etc/cron.allow` and `/etc/cron.deny`** control which users may use `crontab`. If `/etc/cron.allow` exists, only listed users can schedule jobs. If only `/etc/cron.deny` exists, everyone except listed users can. If neither exists, behavior is implementation-defined (usually root-only or all users depending on distro).

```bash
# Check who is allowed to schedule cron jobs
cat /etc/cron.allow 2>/dev/null || echo "cron.allow not present"
cat /etc/cron.deny  2>/dev/null || echo "cron.deny not present"
```

**World-writable script called by root cron = privilege escalation.** If root's crontab calls `/opt/scripts/backup.sh` and that file is writable by a non-root user, that user can inject arbitrary commands to run as root.

```bash
# Audit: find scripts called by root crontab that are writable by others
crontab -u root -l | grep -oP '/[^ ]+\.sh' | xargs ls -l
```

**Always verify permissions on scripts called by cron:**

```bash
chmod 750 /opt/scripts/backup.sh
chown root:root /opt/scripts/backup.sh
```

---

## Примеры

### Example 1: Nightly Database Backup with Locking and Logging

This example drops a complete production-style cron config into `/etc/cron.d/` for a PostgreSQL backup job. It uses flock to prevent overlapping runs, timestamps every run, and rotates logs.

```bash
# Step 1: Create the backup script
cat > /usr/local/bin/pg-backup.sh << 'EOF'
#!/bin/bash
set -euo pipefail

BACKUP_DIR="/var/backups/postgres"
DB_NAME="appdb"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTFILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[${TIMESTAMP}] Starting backup of ${DB_NAME}"
pg_dump -U postgres "${DB_NAME}" | gzip > "${OUTFILE}"
echo "[$(date -Iseconds)] Backup complete: ${OUTFILE} ($(du -sh "${OUTFILE}" | cut -f1))"

# Prune backups older than 30 days
find "${BACKUP_DIR}" -name "*.sql.gz" -mtime +30 -delete
echo "[$(date -Iseconds)] Old backups pruned"

# Signal success to monitoring
curl -fsS --retry 3 "https://hc-ping.com/your-uuid" > /dev/null || true
EOF

chmod 750 /usr/local/bin/pg-backup.sh
chown root:root /usr/local/bin/pg-backup.sh
```

```bash
# Step 2: Create the cron.d file
cat > /etc/cron.d/pg-backup << 'EOF'
# PostgreSQL nightly backup — owned by platform team
# Runs at 2:30 AM daily as the postgres user
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""

30 2 * * * postgres flock -n /tmp/pg-backup.lock /usr/local/bin/pg-backup.sh >> /var/log/pg-backup.log 2>&1
EOF

chmod 644 /etc/cron.d/pg-backup
chown root:root /etc/cron.d/pg-backup
```

```bash
# Step 3: Add logrotate config
cat > /etc/logrotate.d/pg-backup << 'EOF'
/var/log/pg-backup.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
    create 0640 root root
}
EOF
```

```bash
# Step 4: Verify it's loaded — cron picks up /etc/cron.d/ automatically, no reload needed
# Simulate the run manually to confirm the script works before waiting for 2:30 AM
sudo -u postgres /usr/local/bin/pg-backup.sh

# Verify log output
tail -5 /var/log/pg-backup.log

# After 2:30 AM passes, confirm cron launched it
grep "pg-backup" /var/log/syslog
```

---

### Example 2: Docker Image Cleanup Every 6 Hours

Old Docker images accumulate quickly on CI workers and app servers. This job prunes dangling images every 6 hours with staggered timing to avoid hitting the Docker daemon at peak CI load.

```bash
# Step 1: Create the cleanup script
cat > /usr/local/bin/docker-prune.sh << 'EOF'
#!/bin/bash
set -euo pipefail

echo "[$(date -Iseconds)] Starting Docker prune"

# Remove dangling images (untagged, not referenced by any container)
REMOVED=$(docker image prune -f 2>&1)
echo "${REMOVED}"

# Remove stopped containers older than 24h
docker container prune -f --filter "until=24h" 2>&1

echo "[$(date -Iseconds)] Docker prune complete"
EOF

chmod 750 /usr/local/bin/docker-prune.sh
chown root:root /usr/local/bin/docker-prune.sh
```

```bash
# Step 2: Install the cron job
# Runs at 1:15, 7:15, 13:15, 19:15 — offset from the hour to reduce contention
cat > /etc/cron.d/docker-prune << 'EOF'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=""

15 1,7,13,19 * * * root flock -n /tmp/docker-prune.lock /usr/local/bin/docker-prune.sh >> /var/log/docker-prune.log 2>&1
EOF

chmod 644 /etc/cron.d/docker-prune
chown root:root /etc/cron.d/docker-prune
```

```bash
# Step 3: Verify
# Run manually first
/usr/local/bin/docker-prune.sh
tail /var/log/docker-prune.log

# Check the cron entry parsed correctly (no syntax errors cause cron to ignore the file)
# cron does not provide a --check flag; watch syslog for parse errors after saving
journalctl -u cron --since "1 minute ago"
```

---

### Example 3: Environment-Sensitive Health Check with Python

This example deliberately exercises the environment problem. A Python-based health check uses a virtualenv and reads a secret from a file — both things that break under naive cron setup.

```bash
# Step 1: The health check script
cat > /opt/myapp/healthcheck.py << 'EOF'
#!/usr/bin/env python3
import os, sys, requests

API_URL = os.environ["MYAPP_API_URL"]
TOKEN   = open("/etc/myapp/api-token").read().strip()

try:
    r = requests.get(f"{API_URL}/health", headers={"Authorization": f"Bearer {TOKEN}"}, timeout=10)
    r.raise_for_status()
    print(f"OK: {r.status_code}")
    sys.exit(0)
except Exception as e:
    print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)
EOF

chmod 750 /opt/myapp/healthcheck.py
```

```bash
# Step 2: Wrapper script that sets up the environment before calling Python
# This is Fix 3 from the Environment Problem section — source inside the script
cat > /usr/local/bin/myapp-healthcheck.sh << 'EOF'
#!/bin/bash
set -euo pipefail

# Activate virtualenv — not in cron's PATH
source /opt/myapp/venv/bin/activate

# Set required env var — not inherited from any shell profile
export MYAPP_API_URL="https://api.internal.example.com"

exec /opt/myapp/healthcheck.py
EOF

chmod 750 /usr/local/bin/myapp-healthcheck.sh
```

```bash
# Step 3: Install the cron job — note MAILTO catches stderr if the exit code is non-zero
cat > /etc/cron.d/myapp-healthcheck << 'EOF'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MAILTO=oncall@example.com

*/5 * * * * deploy flock -n /tmp/myapp-hc.lock /usr/local/bin/myapp-healthcheck.sh >> /var/log/myapp-healthcheck.log 2>&1
EOF

chmod 644 /etc/cron.d/myapp-healthcheck
chown root:root /etc/cron.d/myapp-healthcheck
```

```bash
# Step 4: Simulate the cron environment to verify before waiting 5 minutes
# This is the env -i debugging technique from the Environment Problem section
sudo -u deploy env -i HOME=/home/deploy SHELL=/bin/bash PATH=/usr/bin:/bin \
  /bin/bash --noprofile --norc /usr/local/bin/myapp-healthcheck.sh

# If it passes here, it will pass under cron
tail /var/log/myapp-healthcheck.log
```

---

## Практические задания

### Exercise 1: Audit and Fix a Broken Cron Job

You are given the following cron job that was installed by a previous engineer. It works when run manually as the `deploy` user, but the cron logs show it launches and then produces no output, and the backup files are never created.

```
*/30 * * * * deploy backup.sh > /var/log/backup.log
```

**Tasks:**

1. List at least three distinct problems with this cron entry and explain why each causes a failure.
2. Rewrite the entry so it runs correctly. The backup script lives at `/usr/local/bin/backup.sh`. It must run every 30 minutes, append output with timestamps, and capture both stdout and stderr.
3. Write the `env -i` command you would use to simulate the cron environment for the `deploy` user and test the script before deploying your fix.
4. Where should this entry live if it's part of a deployed application — your personal crontab or `/etc/cron.d/`? Explain the operational reason.

---

### Exercise 2: Design a Schedule Without Overlaps

A report generation script takes between 8 and 25 minutes to run depending on data volume. It must run at least once per hour. The script is not idempotent — if two instances run simultaneously, the output file is corrupted.

**Tasks:**

1. Write the cron entry with `flock` that prevents overlapping runs. Use `/tmp/report-gen.lock` as the lock file.
2. Explain what happens if the script is still running when cron tries to start the next instance. What does the user see in the log? What does NOT happen (i.e., what would you need to add yourself if you wanted an alert)?
3. Modify your entry so that if the script fails (non-zero exit), an email is sent to `reports-team@example.com`. What must be configured on the system for this to work?
4. Using `journalctl`, write the exact command that would show you every time this job was launched in the last 24 hours.

---

### Exercise 3: Write and Deploy a Full Cron Job from Scratch

Build a complete log archiving solution using cron. Requirements:

- Every day at 3:45 AM, compress all `.log` files in `/var/log/myapp/` that are older than 7 days into a tarball named `myapp-archive-YYYYMMDD.tar.gz` in `/var/backups/myapp/`.
- Tarballs older than 90 days should be deleted.
- The job runs as the `root` user.
- Each run appends a timestamped entry to `/var/log/myapp-archive.log`.
- The log file is rotated weekly, keeping 8 weeks of history.

**Deliverables:**

1. The shell script at `/usr/local/bin/myapp-archive.sh` — complete and runnable.
2. The file at `/etc/cron.d/myapp-archive` — including all necessary environment variables and correct permissions (`chmod 644`, owned by `root:root`).
3. The logrotate config at `/etc/logrotate.d/myapp-archive`.
4. The exact command to verify the job ran after its first scheduled execution, without waiting — i.e., how do you confirm the syslog shows cron launched it AND the log file shows it completed successfully?

---

### Быстрая проверка

1. Count the number of fields in a cron expression.

   ```bash
   echo "30 */2 * * 1-5" | awk '{print NF}'
   ```

   ```expected_output
   5
   ```

hint: Think about how you can split a cron expression into its individual parts and count those parts.
hint: Use echo with the cron expression string and pipe it to awk, using NF to print the number of fields.

2. Extract the minute field from a cron expression.

   ```bash
   echo "*/15 6-22 * * 1-5" | awk '{print $1}'
   ```

   ```expected_output
   */15
   ```
hint: Think about how you can isolate a specific field from a delimited string in Linux.
hint: Use the cut command with the -d flag to set the delimiter and -f1 to select the first field from the cron expression.
