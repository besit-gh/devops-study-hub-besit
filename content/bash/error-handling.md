---
title: Обработка ошибок в Bash
module: bash
duration_min: 15
difficulty: intermediate
tags: [bash, error-handling, set-e, trap, exit-codes, pipefail]
exercises: 4
---

## Обзор

Поведение Bash по умолчанию опасно: после ошибки выполнение продолжается. Если `cp` завершится неудачно посреди скрипта развёртывания, скрипт перейдёт к следующей строке и может оставить систему в частично обновлённом, несогласованном состоянии. Это особенно важно в DevOps, где скрипты управляют production-развёртываниями, миграциями баз данных, подготовкой инфраструктуры и резервным копированием. Тихий сбой хуже явного падения: проблему можно обнаружить лишь тогда, когда понадобится резервная копия или результат миграции.

Основной принцип — *быстро завершаться при ошибке и всегда выполнять очистку*. Комбинация `set -euo pipefail` заставляет shell строго реагировать на сбои: неопределённые переменные и неудачные команды становятся причиной остановки, а не просто предупреждением. Встроенная команда `trap` обеспечивает очистку: зарегистрированная функция вызывается при успешном завершении, ошибке или получении сигнала. Так последовательность команд Bash становится более предсказуемой.

Надёжная обработка ошибок Bash важна для всего DevOps-стека. CI/CD-пайплайны (Jenkins, GitHub Actions, GitLab CI) выполняют shell-команды и определяют успех по кодам возврата. Ansible проверяет результаты запуска команд, а инструкции Docker `ENTRYPOINT` и `RUN` также выполняют команды: ненулевой код `RUN` ломает сборку образа. Понимание обработки ошибок в Bash необходимо, чтобы разбираться в том, как другие инструменты сообщают об успехе и сбоях.

---

## Основные понятия

### set -e — завершение при ошибке

```bash
set -e   # or: set -o errexit
```

С `set -e` shell немедленно завершается, если простая команда возвращает ненулевой код. Без этого режима ошибки могут быть проигнорированы:

```bash
# Without set -e — dangerous in a deployment context
mkdir /nonexistent/path          # fails, returns exit code 1
cp important.file /nonexistent/  # also fails
echo "Deployment complete"       # still runs — you think it succeeded
```

С `set -e` скрипт останавливается при первой ошибке, и ложное сообщение об успехе не выводится.

**Исключение: `set -e` не применяется к командам, код завершения которых проверяется явно:**

| Контекст | Действует ли `set -e`? |
|---|---|
| Простая команда: `cp a b` | Да |
| Условие `if`: `if grep -q x file` | Нет |
| Левая часть `&&` или `\|\|` | Нет |
| Команды в условии `while`/`until` | Нет |
| Последняя команда конвейера (без `pipefail`) | Да |

```bash
set -e

# These are all safe — exit codes are intentionally tested:
if ! grep -q "nginx" /etc/services; then
    echo "nginx not in services"
fi

systemctl is-active nginx || echo "nginx is down"

# To exempt a single command without wrapping it in if:
some_command_that_may_fail || true
```

**Особенность `set -e` при подстановке команд в subshell:** ошибки внутри `$(...)` могут не вызвать завершение, если подстановка используется в присваивании переменной. Само присваивание возвращает 0, даже если subshell завершился с ошибкой. Это частый источник скрытых дефектов.

```bash
set -e

# This does NOT exit even if git log fails (e.g., not a git repo):
LAST_COMMIT=$(git log -1 --format=%H)

# Safe approach: run first, then capture
git log -1 --format=%H > /dev/null   # will exit on failure
LAST_COMMIT=$(git log -1 --format=%H)
```

**Особенность `set -e` в функциях:** режим действует внутри функций, но если вызов функции находится в составном условии (например, `if myfunc; then`), ошибки внутри функции подавляются. Если нужно, чтобы `set -e` ловил внутренние ошибки, вызывайте функцию как обычную команду, а не внутри условия.

---

### set -u — ошибка при незаданных переменных

```bash
set -u   # or: set -o nounset
```

Без `set -u` обращение к незаданной переменной незаметно превращается в пустую строку. Последствия варьируются от неверного вывода до катастрофической потери данных:

```bash
# Without set -u:
echo "$UNSET_VAR/config"    # prints: /config  (wrong path)
rm -rf "$UNSET_VAR/"        # becomes: rm -rf /  (disaster)
```

С `set -u` скрипт немедленно завершается с сообщением `bash: UNSET_VAR: unbound variable`.

**Безопасные значения по умолчанию через раскрытие параметров:**

| Синтаксис | Поведение |
|---|---|
| `${VAR:-default}` | Использовать `default`, если VAR не задана **или пуста** |
| `${VAR-default}` | Использовать `default`, только если VAR не задана (пустая строка сохраняется) |
| `${VAR:?error msg}` | Завершиться с сообщением об ошибке, если VAR не задана или пуста |
| `${VAR:=default}` | Присвоить VAR значение `default`, если она не задана или пуста, затем раскрыть её |
| `${VAR:+alternate}` | Использовать `alternate`, если VAR задана и не пуста; иначе пустая строка |

```bash
set -u

DEPLOY_ENV="${DEPLOY_ENV:-staging}"                          # default to staging
LOG_LEVEL="${LOG_LEVEL:-info}"                               # optional with default
CONFIG_FILE="${CONFIG_FILE:?CONFIG_FILE must be set}"        # hard requirement — exits with message
OPTIONAL_FLAG="${OPTIONAL_FLAG:+--flag=${OPTIONAL_FLAG}}"   # only include if set
```

**Особенность `set -u` с массивами:** обращение к незаданному массиву или `$@` без позиционных аргументов вызывает ошибку. Безопасный шаблон раскрытия массива и `$@` — `${array[@]+"${array[@]}"}`.

```bash
set -u

# Wrong — fails if script receives no arguments:
for arg in "$@"; do echo "$arg"; done

# Safe — expands to nothing when $@ is empty:
for arg in "${@+"$@"}"; do echo "$arg"; done

# Same pattern for optional arrays:
EXTRA_ARGS=()
rsync "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}" /src/ /dst/
```

---

### set -o pipefail — обнаружение ошибок в конвейере

```bash
set -o pipefail
```

Без `pipefail` код завершения конвейера равен коду **только последней команды**. Ошибки предыдущих команд незаметно теряются, даже если включён `set -e`:

```bash
# Without pipefail:
cat /nonexistent_file | grep "ERROR" | wc -l
# cat exits 1 (file not found)
# grep exits 1 (no input, no match)
# wc exits 0
# Pipeline exit code = 0 — script continues as if everything succeeded
```

С `pipefail` код конвейера равен коду **самой правой команды, завершившейся с ошибкой**:

```bash
set -eo pipefail
cat /nonexistent_file | grep "ERROR" | wc -l
# Pipeline exit code = 1 (from cat) — script exits here
```

**Взаимодействие `pipefail` с `grep`:** `grep` возвращает 1, если совпадений нет. Это часто нормальное поведение, а не ошибка. При включённом `pipefail` конвейер, заканчивающийся на `grep`, вернёт 1 при отсутствии совпадений, и `set -e` воспримет это как сбой.

```bash
set -eo pipefail

# This exits the script if grep finds no matches — probably not what you want:
journalctl -u nginx | grep "error"

# If "no matches" is acceptable, suppress with || true:
ERROR_COUNT=$(journalctl -u nginx | grep -c "error" || true)
echo "Found $ERROR_COUNT errors"
```

**Проверка кодов завершения этапов конвейера:** массив `PIPESTATUS` содержит код каждой команды последнего конвейера. Используйте его, если нужно определить, какой именно этап завершился с ошибкой.

```bash
set -o pipefail

generate_report | compress | upload_to_s3
pipe_codes=("${PIPESTATUS[@]}")

echo "generate_report: ${pipe_codes[0]}"
echo "compress:        ${pipe_codes[1]}"
echo "upload_to_s3:    ${pipe_codes[2]}"
```

---

### Стандартный заголовок скрипта

Каждый production-скрипт Bash должен начинаться с:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

Использование `/usr/bin/env bash` вместо `/bin/bash` более переносимо: Bash ищется в `$PATH`. Это важно для macOS (где `/bin/bash` — устаревшая версия 3.2), NixOS и контейнеров с нестандартным расположением Bash.

Некоторые команды дополняют этот заголовок:

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'   # safer word splitting: only newline and tab, not space
```

Изменение `IFS` предотвращает ошибки разбиения имён файлов и значений, содержащих пробелы. Без этого цикл вроде `for f in $(ls)` ломается на именах с пробелами. Это особенно полезно в скриптах, обрабатывающих списки файлов, пользовательский ввод или вывод внешних команд. Некоторые шаблоны (разбиение строк по пробелам) перестанут работать, но их обычно лучше заменить массивами.

---

### trap — очистка при завершении

`trap` регистрирует команду или функцию, которая выполняется при получении сигнала или завершении shell. Главное применение — гарантированная очистка: временные файлы, блокировки и частично изменённое состояние убираются как при успехе, так и при ошибке или прерывании скрипта.

```bash
#!/usr/bin/env bash
set -euo pipefail

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT   # runs no matter how the script ends

cp source_data.csv "$TMPDIR/"
process "$TMPDIR/source_data.csv" > output.csv
# $TMPDIR removed automatically — success, error, or signal
```

**События, на которые реагирует trap:**

| Сигнал / псевдосигнал | Когда срабатывает |
|---|---|
| `EXIT` | Скрипт завершился по любой причине (нормально, с ошибкой или по сигналу) |
| `ERR` | Команда вернула ненулевой код (надёжно работает только с `set -e`) |
| `INT` | Пользователь нажал Ctrl+C (SIGINT, сигнал 2) |
| `TERM` | Процесс получил SIGTERM (например, `kill <pid>`) |
| `HUP` | Потеря терминала (SIGHUP, например, разрыв SSH-сессии) |

**Для очистки предпочитайте `EXIT`, а не `ERR`.** `ERR` срабатывает не во всех контекстах ошибок, тогда как `EXIT` выполняется при любом завершении скрипта.

**Особенность `trap`: `$?` в обработчике:** внутри `EXIT` trap переменная `$?` содержит код завершения, который привёл к выходу. Сохраните его первой операцией в функции очистки: любая последующая команда, даже `echo`, перезапишет `$?`.

```bash
cleanup() {
    local exit_code=$?    # capture FIRST — any command below will overwrite $?
    rm -rf "$TMPDIR"
    if [ "$exit_code" -ne 0 ]; then
        echo "Script failed with exit code $exit_code" >&2
    fi
    exit "$exit_code"     # propagate the original exit code to the caller
}
trap cleanup EXIT
```

**Несколько trap:** каждый вызов `trap` заменяет предыдущий обработчик того же сигнала. Чтобы добавить действие, не потеряв существующую очистку, явно объедините функции:

```bash
cleanup_files() { rm -rf "$TMPDIR"; }
release_lock()  { rm -f /var/run/myscript.lock; }

# Wrong: this silently replaces cleanup_files:
trap release_lock EXIT

# Right: define a single handler that calls both in the right order:
cleanup_all() {
    release_lock
    cleanup_files
}
trap cleanup_all EXIT
```

**`trap` и subshell:** обработчики не наследуются subshell, созданными через `(...)`. Если запускаете subshell, задайте обработчики внутри него. Дочерние процессы, созданные через `$(...)` или `&`, также не наследуют trap.

---

### Коды завершения

Коды завершения — универсальный интерфейс взаимодействия процессов в Unix. Каждая команда возвращает такой код. Скрипты, вызываемые из CI/CD, Ansible, Docker или других скриптов, должны возвращать осмысленные коды: возврат 0 при ошибке незаметно ломает вызывающую сторону.

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | General error (convention) |
| `2` | Misuse of shell command or bad arguments |
| `126` | Command found but not executable (permissions) |
| `127` | Command not found |
| `128+n` | Script terminated by signal `n` (e.g., `130` = Ctrl+C = 128+2) |

Коды завершения выше 125 зарезервированы оболочкой. **Не используйте коды выше 125 в собственных скриптах**: они конфликтуют со значениями, зарезервированными оболочкой, и вводят вызывающие процессы в заблуждение.

**Проверка кодов завершения — предпочитайте `if`, а не `$?`:**

```bash
# Fragile: $? is overwritten by every command, including [
cp file.txt /backup/
if [ $? -ne 0 ]; then    # risky: inserting any command between cp and [ breaks this
    echo "Backup failed" >&2
    exit 1
fi

# Idiomatic: test the command directly — no gap for $? to be overwritten
if ! cp file.txt /backup/; then
    echo "Backup failed" >&2
    exit 1
fi

# For chains: use && / || with explicit error handling
cp file.txt /backup/ && echo "Backup OK" || { echo "Backup failed" >&2; exit 1; }
```

**Передача кода завершения:** если скрипт вызывает другой скрипт, сохраняйте его код завершения. Команда `exit` без аргумента завершает работу с кодом последней выполненной команды. В обработчиках `trap` завершайтесь с сохранённым кодом, чтобы вызывающий процесс получил настоящий результат.

---

### Понятные сообщения об ошибках

Хорошее сообщение об ошибке сообщает оператору, *что* сломалось, *где* и, по возможности, *что делать дальше*. Вывод ошибок направляйте в stderr (`>&2`): он не загрязняет stdout, его можно сохранить отдельно, и он не потеряется при перенаправлении stdout в файл или конвейер.

```bash
# Reusable die() helper — include in every production script
die() {
    local exit_code="${1:-1}"
    shift
    echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') ${BASH_SOURCE[1]}:${BASH_LINENO[0]} — $*" >&2
    exit "$exit_code"
}

# Usage patterns:
[ -f "$CONFIG" ]      || die 1 "Config file not found: $CONFIG — copy from config.example"
[ $# -ge 1 ]          || die 2 "Usage: $0 <environment> [version]"
command -v docker     || die 127 "docker not found — install Docker Engine and ensure it is on PATH"
[ "$EUID" -eq 0 ]     || die 1 "This script must be run as root (current UID: $EUID)"
```

**Добавляйте контекст в сообщения об ошибках.** Сообщение `"File not found"` заставляет оператора перечитывать скрипт, чтобы понять, о каком файле речь. Сообщение `"Ожидался конфиг /etc/myapp/config.yml — перед развёртыванием скопируйте /etc/myapp/config.example"` сразу подсказывает действие.

```bash
# Bad:
die "Connection failed"

# Good:
die "Failed to connect to database at ${DB_HOST}:${DB_PORT} — check DB_HOST and DB_PORT environment variables and verify the database is running"
```

---

### Debugging

| Technique | Command | When to use |
|---|---|---|
| Trace execution | `set -x` / `bash -x script.sh` | Step through logic, see variable expansion in real time |
| Syntax check only | `bash -n script.sh` | Catch parse errors without running — safe for production scripts |
| Verbose mode | `set -v` | Print each line before word-splitting (less readable than `-x`) |
| Check exit code inline | `some_cmd; echo "exit: $?"` | After a specific suspect command |
| Trace a section only | `set -x; ...; set +x` | Reduce noise in long scripts |
| Dry-run pattern | `DRY_RUN=true` guard in functions | Simulate destructive actions without executing them |

```bash
#!/usr/bin/env bash
set -euo pipefail

# Trace only the risky section — keeps output manageable:
set -x
rsync -avz /src/ user@host:/dst/
set +x

echo "rsync completed"
```

**`$BASH_SOURCE`, `$LINENO` и `$FUNCNAME`** доступны в обработчиках `trap` и функциях обработки ошибок. Они позволяют выводить сведения в стиле stack trace и точно определять место ошибки в системе из нескольких скриптов:

```bash
err_report() {
    echo "[TRACE] Error on line $1 in ${BASH_SOURCE[0]}" >&2
    # Print a simple call stack if inside nested functions:
    local i
    for i in "${!FUNCNAME[@]}"; do
        echo "  [$i] ${FUNCNAME[$i]} (${BASH_SOURCE[$i+1]:-main}:${BASH_LINENO[$i]})" >&2
    done
}
trap 'err_report $LINENO' ERR
```

**Настройка `PS4`:** переменная `PS4` задаёт префикс, который выводит `set -x`. По умолчанию это `+`. Если добавить имя скрипта и номер строки, трассировка станет значительно полезнее:

```bash
export PS4='+(${BASH_SOURCE}:${LINENO}): ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'
set -x
```

---

## Примеры

### Пример 1. Надёжный скрипт развёртывания с автоматическим откатом

```bash
#!/usr/bin/env bash
# deploy.sh — deploy a versioned release with automatic rollback on failure
# Usage: ./deploy.sh <service> <version>
set -euo pipefail

SERVICE="${1:?Usage: $0 <service> <version>}"
VERSION="${2:?Usage: $0 <service> <version>}"

BACKUP_DIR="/opt/backups/${SERVICE}"
DEPLOY_DIR="/opt/apps/${SERVICE}"
RELEASE_DIR="/opt/releases/${SERVICE}/${VERSION}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/${TIMESTAMP}"

die() {
    local code="${1:-1}"; shift
    echo "[ERROR] $*" >&2
    exit "$code"
}

# Preflight checks — fail early before making any changes
[ -d "$DEPLOY_DIR" ]  || die 1 "Deploy dir not found: $DEPLOY_DIR"
[ -d "$RELEASE_DIR" ] || die 1 "Release not found: $RELEASE_DIR — build it first"
command -v rsync >/dev/null 2>&1 || die 127 "rsync required but not installed"
systemctl is-enabled "$SERVICE" >/dev/null 2>&1 || die 1 "Systemd service '$SERVICE' does not exist"

# cleanup() runs on any exit — checks whether to roll back
cleanup() {
    local exit_code=$?   # capture before any other command overwrites it
    if [ "$exit_code" -ne 0 ]; then
        echo "[ROLLBACK] Deployment failed (exit $exit_code) — rolling back..." >&2
        if [ -d "$BACKUP_PATH" ]; then
            rsync -a --delete "${BACKUP_PATH}/" "${DEPLOY_DIR}/"
            systemctl restart "$SERVICE" || true   # best-effort; don't mask original error
            echo "[ROLLBACK] Complete. Service restored from $BACKUP_PATH" >&2
        else
            echo "[ROLLBACK] No backup at $BACKUP_PATH — manual recovery required" >&2
        fi
    fi
    exit "$exit_code"
}
trap cleanup EXIT

# Step 1: back up current deployment
mkdir -p "$BACKUP_PATH"
rsync -a "${DEPLOY_DIR}/" "${BACKUP_PATH}/"
echo "[1/3] Backed up current deployment → $BACKUP_PATH"

# Step 2: deploy new release
systemctl stop "$SERVICE"
rsync -a --delete "${RELEASE_DIR}/" "${DEPLOY_DIR}/"
systemctl start "$SERVICE"
echo "[2/3] Deployed ${SERVICE}@${VERSION}"

# Step 3: health check — give the service time to initialize
sleep 5
systemctl is-active --quiet "$SERVICE" \
    || die 1 "Service $SERVICE is not active after deployment — check: journalctl -u $SERVICE"

echo "[3/3] Health check passed. ${SERVICE}@${VERSION} is live."
```

**Verify it works:**
```bash
# Test rollback by pointing to a nonexistent version:
./deploy.sh myapp 99.99.99
# Expected: preflight check exits with "Release not found" before any changes

# Test mid-deployment failure by making the release dir unreadable:
chmod 000 /opt/releases/myapp/2.0.0
./deploy.sh myapp 2.0.0
# Expected: rsync fails, cleanup fires, original version restored
echo "Exit code: $?"   # should be non-zero
```

---

### Пример 2. Конвейер обработки журналов с полной обработкой ошибок

```bash
#!/usr/bin/env bash
# parse_errors.sh — extract and count error patterns from an application log
# Usage: ./parse_errors.sh <logfile> [output_file]
set -euo pipefail

LOGFILE="${1:?Usage: $0 <logfile> [output_file]}"
OUTFILE="${2:-/dev/stdout}"

die() { echo "[ERROR] $*" >&2; exit 1; }

[ -f "$LOGFILE" ]    || die "Log file not found: $LOGFILE"
[ -r "$LOGFILE" ]    || die "Log file not readable: $LOGFILE (check permissions)"
command -v awk >/dev/null 2>&1 || die "awk is required"

# Use a temp file so a partial run doesn't corrupt the output file
TMPOUT=$(mktemp)
trap 'rm -f "$TMPOUT"' EXIT

echo "Processing: $LOGFILE" >&2

# grep exits 1 on no matches — || true prevents set -e from treating that as failure
# We capture the count separately so a pipeline failure in grep is distinguishable
# from a failure in awk or sort
ERROR_LINES=$(grep -i "error\|exception\|critical" "$LOGFILE" || true)

if [ -z "$ERROR_LINES" ]; then
    echo "No errors found in $LOGFILE" >&2
    echo "# No errors found — $(date)" > "$TMPOUT"
else
    # Count occurrences of each unique error pattern
    # awk groups by the first field after the log level keyword
    echo "$ERROR_LINES" \
        | awk '{
            # Extract the word immediately after ERROR/EXCEPTION/CRITICAL as the key
            for (i=1; i<=NF; i++) {
                if (tolower($i) ~ /error|exception|critical/) {
                    key = $(i+1)
                    counts[key]++
                    break
                }
            }
          }
          END {
            for (k in counts) printf "%6d  %s\n", counts[k], k
          }' \
        | sort -rn \
        > "$TMPOUT"

    TOTAL=$(wc -l < "$TMPOUT")
    echo "Found $TOTAL distinct error patterns" >&2
fi

# Atomically move temp output to final destination (avoids partial writes)
if [ "$OUTFILE" = "/dev/stdout" ]; then
    cat "$TMPOUT"
else
    mv "$TMPOUT" "$OUTFILE"
    echo "Report written to $OUTFILE" >&2
fi
```

**Verify it works:**
```bash
# Create a sample log:
cat > /tmp/test.log <<'EOF'
2024-01-15 10:01:00 INFO  Server started
2024-01-15 10:01:05 ERROR ConnectionRefused connecting to db:5432
2024-01-15 10:01:06 ERROR ConnectionRefused connecting to db:5432
2024-01-15 10:01:10 CRITICAL DiskFull /var/data has 0 bytes free
2024-01-15 10:01:15 ERROR TimeoutError waiting for upstream
EOF

./parse_errors.sh /tmp/test.log
# Expected: counts for ConnectionRefused, DiskFull, TimeoutError

# Test missing file:
./parse_errors.sh /tmp/nonexistent.log
# Expected: [ERROR] Log file not found — exits 1
```

---

### Пример 3. Предварительная проверка инфраструктуры

```bash
#!/usr/bin/env bash
# preflight.sh — validate environment before running a deployment
# Exits non-zero if any required condition is not met.
# Designed to be sourced or called from a CI pipeline step.
set -euo pipefail

REQUIRED_VARS=(DB_HOST DB_PORT DEPLOY_ENV AWS_REGION)
REQUIRED_CMDS=(aws kubectl helm jq)
MIN_DISK_GB=5
MIN_MEM_GB=2

PASS=0
FAIL=0

check() {
    local description="$1"
    local result="$2"   # "ok" or an error message
    if [ "$result" = "ok" ]; then
        echo "  [PASS] $description"
        (( PASS++ )) || true   # increment even under set -e (arithmetic returns 1 on 0)
    else
        echo "  [FAIL] $description — $result" >&2
        (( FAIL++ )) || true
    fi
}

echo "=== Environment Variables ==="
for var in "${REQUIRED_VARS[@]}"; do
    if [ -n "${!var:-}" ]; then   # indirect expansion: value of variable named by $var
        check "$var is set" "ok"
    else
        check "$var is set" "unset or empty"
    fi
done

echo "=== Required Commands ==="
for cmd in "${REQUIRED_CMDS[@]}"; do
    if command -v "$cmd" >/dev/null 2>&1; then
        check "$cmd available" "ok"
    else
        check "$cmd available" "not found on PATH"
    fi
done

echo "=== System Resources ==="
# Disk: df reports in 1K blocks; convert to GB
DISK_FREE_GB=$(df / | awk 'NR==2 {printf "%d", $4/1024/1024}')
if [ "$DISK_FREE_GB" -ge "$MIN_DISK_GB" ]; then
    check "Disk free >= ${MIN_DISK_GB}GB (found: ${DISK_FREE_GB}GB)" "ok"
else
    check "Disk free >= ${MIN_DISK_GB}GB" "only ${DISK_FREE_GB}GB free"
fi

# Memory: /proc/meminfo in kB
MEM_FREE_GB=$(awk '/MemAvailable/ {printf "%d", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo 0)
if [ "$MEM_FREE_GB" -ge "$MIN_MEM_GB" ]; then
    check "Memory available >= ${MIN_MEM_GB}GB (found: ${MEM_FREE_GB}GB)" "ok"
else
    check "Memory available >= ${MIN_MEM_GB}GB" "only ${MEM_FREE_GB}GB available"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"

if [ "$FAIL" -gt 0 ]; then
    echo "Preflight FAILED — resolve the above issues before deploying." >&2
    exit 1
fi

echo "Preflight PASSED."
exit 0
```

**Verify it works:**
```bash
# Run with a missing variable to trigger a failure:
unset DB_HOST
./preflight.sh
# Expected: [FAIL] DB_HOST is set, Results: X passed, 1+ failed, exit code 1

# Run with all vars set and commands present:
export DB_HOST=db.internal DB_PORT=5432 DEPLOY_ENV=staging AWS_REGION=us-east-1
./preflight.sh
# Expected: all PASSes (assuming tools are installed), exit code 0
```

---

## Практические задания

### Задание 1. Найдите незаметные ошибки

В приведённом ниже скрипте три ошибки обработки сбоев, которые могут привести к незаметным проблемам в production. Не запуская его, найдите каждую ошибку и объясните последствия. Затем исправьте скрипт.

```bash
#!/usr/bin/env bash

BACKUP_DIR="/backups"
DB_NAME="$1"

mkdir -p "$BACKUP_DIR"
pg_dump "$DB_NAME" | gzip > "$BACKUP_DIR/${DB_NAME}.sql.gz"
echo "Backup of $DB_NAME complete: $BACKUP_DIR/${DB_NAME}.sql.gz"
```

**What to find:**
1. Что произойдёт, если вызвать скрипт без аргументов?
2. Что произойдёт, если `pg_dump` завершится с ошибкой посреди конвейера, например, если базы данных не существует?
3. Что произойдёт с выходным файлом, если `gzip` завершится с ошибкой?

После обнаружения ошибок перепишите скрипт с `set -euo pipefail`, обработчиком очистки `trap` и предварительной проверкой аргументов. Проверьте его, передав имя несуществующей базы данных.

---

### Задание 2. Создайте повторно используемую библиотеку обработки ошибок

Create a file called `lib/error.sh` that can be sourced by other scripts. It should provide:

1. A `die <exit_code> <message>` function that prints to stderr and exits
2. A `require_cmd <command>` function that exits with code 127 if the command is not on `$PATH`
3. A `require_var <varname>` function that exits with code 1 if the named variable is unset or empty (use indirect expansion `${!varname}`)
4. A `setup_traps` function that registers an `EXIT` trap printing the exit code and the line number where the script exited (use `$BASH_LINENO`)

Then write a second script `deploy_check.sh` that sources `lib/error.sh`, calls `setup_traps`, uses `require_var` to validate `DEPLOY_ENV` and `APP_VERSION`, uses `require_cmd` to validate `docker` and `kubectl`, and calls `die` with a descriptive message if `DEPLOY_ENV` is not one of `staging`, `production`.

Test it with missing variables, missing commands, and an invalid environment name.

---

### Exercise 3: Debug a Broken Pipeline

The following script is intended to count HTTP 5xx errors in an nginx access log and alert if the count exceeds a threshold. It has a bug related to `pipefail` and `grep` exit codes that causes it to always exit with an error even when the log has no 5xx entries.

```bash
#!/usr/bin/env bash
set -euo pipefail

LOGFILE="${1:?Usage: $0 <logfile>}"
THRESHOLD="${2:-10}"

COUNT=$(grep " 5[0-9][0-9] " "$LOGFILE" | wc -l)

if [ "$COUNT" -gt "$THRESHOLD" ]; then
    echo "ALERT: $COUNT 5xx errors exceed threshold of $THRESHOLD" >&2
    exit 2
fi

echo "OK: $COUNT 5xx errors (threshold: $THRESHOLD)"
```

**Tasks:**
1. Reproduce the bug by creating a log file with no 5xx lines and running the script.
2. Explain exactly which command is failing and why.
3. Fix the script without disabling `pipefail` globally. The fix should preserve error detection for real failures (like the log file not being readable).
4. Add handling for the case where the log file exists but is empty.

---

### Exercise 4: Simulate a Deployment with Staged Failures

Write a script `staged_deploy.sh` that simulates a four-stage deployment (validate → build → push → restart) using functions. Each stage should:

- Print a `[STAGE n/4]` header before executing
- Accept a `FAIL_AT_STAGE` environment variable (1–4) that causes the specified stage to fail with exit code 1
- Use `trap` to print which stage failed and how long the deployment ran before failing (use `$SECONDS` which Bash increments automatically)
- Clean up a temp directory created at startup regardless of which stage fails

Run the script four times, setting `FAIL_AT_STAGE` to 1, 2, 3, and 4 in turn, and verify that:
- The correct stage name appears in the failure message each time
- The temp directory is always removed (check with `ls /tmp/deploy_*` before and after)
- The exit code is non-zero for all four runs
- A fifth run with `FAIL_AT_STAGE` unset completes successfully with exit code 0

---

### Быстрая проверка

5. Run `bash -c 'exit 42'` and immediately print its exit code using `echo $?`. Write both commands semicolon-separated on one line.

```expected_output
42
```

hint: Think about how to capture and display the exit status of the previous command right after it runs.
hint: Use $? immediately after the command to access its exit code, and separate the two commands with a semicolon on the same line.

6. Use `grep -q` to search for `"needle"` in `"haystack"` via a here-string (`<<<`). Use `||` so that if grep finds no match, `"not found"` is printed instead. Write a one-liner.

```expected_output
not found
```
hint: Think about how grep's quiet mode combined with a logical OR operator can trigger a fallback action when no match is found.
hint: Use `grep -q 'needle' <<< 'haystack'` and chain `|| echo` to print your fallback message if the exit code indicates no match.
