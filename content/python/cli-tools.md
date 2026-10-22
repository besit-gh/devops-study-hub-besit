---
title: Создание CLI-инструментов на Python
module: python
duration_min: 20
difficulty: intermediate
tags: [python, argparse, cli, click, typer, scripts]
exercises: 4
---

## Обзор

CLI-инструменты связывают компоненты DevOps-автоматизации. Скрипты развёртывания, проверки здоровья, парсеры логов и ротации секретов обычно представляют собой программы командной строки, которые вызывают другие инструменты, объединяют в конвейеры или запускают по расписанию через cron и CI. Хороший CLI ведёт себя как полноценная Unix-утилита: при необходимости читает stdin, выводит данные в stdout, диагностику — в stderr, возвращает осмысленные коды завершения и документирует себя через `--help`. Плохо спроектированный инструмент заставляет инженера изучать исходный код перед безопасным использованием в production.

Для начала лучше всего подходит `argparse`: модуль входит в стандартную библиотеку, автоматически формирует справку, проверяет типы и допустимые значения и поддерживает подкоманды. Для более сложных инструментов `click` и `typer` предлагают API на основе декораторов и уменьшают количество шаблонного кода, но добавляют зависимости. Сначала стоит разобраться в `argparse`, чтобы понимать внутреннюю работу высокоуровневых библиотек и создавать инструменты для минимальных окружений без установки дополнительных пакетов.

CLI-инструменты в DevOps — интерфейс автоматизации как для человека, так и для скриптов. Их вызывают CI-конвейеры, Makefile, задачи Ansible и cron. Все они принимают решения на основе кодов завершения и чистого вывода. Правильная реализация этих соглашений отличает скрипт, работающий только на ноутбуке, от инструмента, которому можно доверять в конвейере.

---

## Основные понятия

### Основы argparse

`argparse` автоматически предоставляет три возможности: разбор аргументов, преобразование типов и генерацию справки. Опишите ожидаемые аргументы, затем вызовите `parse_args()`, чтобы получить объект namespace.

```python
import argparse

parser = argparse.ArgumentParser(
    description="Check service health and optionally restart it."
)

# Positional argument — required, no flag prefix
parser.add_argument("service", help="Service name to check")

# Optional arguments — keyword style, prefixed with --
parser.add_argument("--port", type=int, default=80, help="Port to probe (default: 80)")
parser.add_argument("--timeout", type=float, default=5.0, help="Timeout in seconds")

# Boolean flags — store_true sets the value to True when the flag is present
parser.add_argument("--restart", action="store_true", help="Restart if unhealthy")
parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

args = parser.parse_args()

print(args.service)   # "nginx"
print(args.port)      # 80 (int, not string)
print(args.restart)   # True or False
```

Запуск `python check.py --help` выводит:

```
usage: check.py [-h] [--port PORT] [--timeout TIMEOUT] [--restart] [--verbose] service

Check service health and optionally restart it.

positional arguments:
  service               Service name to check

options:
  -h, --help            show this help message and exit
  --port PORT           Port to probe (default: 80)
  --timeout TIMEOUT     Timeout in seconds
  --restart             Restart if unhealthy
  --verbose, -v         Verbose output
```

**Особенность именования:** `argparse` преобразует дефисы в именах флагов в подчёркивания в объекте namespace. `--db-host` становится `args.db_host`. Дефисы в CLI-флагах соответствуют традициям Unix, а подчёркивания в Python — PEP 8; `argparse` автоматически связывает эти соглашения.

---

### Типы аргументов, choices и nargs

`argparse` преобразует значения в заданный тип Python до передачи их вашему коду. Если преобразование не удалось, модуль выводит ошибку использования и завершается с кодом 2, не запуская ваш код.

| Шаблон | Объявление | Поведение |
|---|---|---|
| Строка | `type=str` (по умолчанию) | Без преобразования |
| Целое число | `type=int` | Ошибка при вводе нецелого значения |
| Число с плавающей точкой | `type=float` | Ошибка при вводе нечислового значения |
| Ограниченный набор | `choices=["dev","staging","prod"]` | Ошибка, если значение отсутствует в наборе |
| Открыть файл для чтения | `type=argparse.FileType("r")` | Открывает файл и возвращает дескриптор |
| Stdout или файл | `type=argparse.FileType("w"), default="-"` | `"-"` означает stdout |
| Список значений | `nargs="+"` | Одно или несколько; возвращается список |
| Необязательное значение | `nargs="?"` | Ноль или одно |
| Фиксированное количество | `nargs=2` | Ровно два; возвращается список |

```python
# Accept one or more target hosts
parser.add_argument("hosts", nargs="+", help="Hosts to probe")

# Accept a restricted environment name
parser.add_argument("--env", choices=["dev", "staging", "prod"], default="dev")

# Write output to a file, defaulting to stdout
parser.add_argument("--output", type=argparse.FileType("w"), default="-")

# Read a config file
parser.add_argument("--config", type=argparse.FileType("r"))
```

Можно написать собственные функции-валидаторы и передать их в `type=`. Они получают исходную строку и должны вернуть преобразованное значение либо вызвать `argparse.ArgumentTypeError`.

```python
def port_number(value):
    n = int(value)
    if not 1 <= n <= 65535:
        raise argparse.ArgumentTypeError(f"{value} is not a valid port (1-65535)")
    return n

parser.add_argument("--port", type=port_number, default=80)
```

**Особенность FileType:** `argparse.FileType` открывает файл сразу после разбора аргументов, до запуска вашего кода. Если файл отсутствует, `argparse` выводит ошибку и завершает программу. Это удобно для обязательных входных файлов, но не позволяет отложить проверку пути.

---

### Подкоманды

Для инструментов с несколькими операциями (deploy, status, rollback) лучше использовать подкоманды, а не перегружать одну команду множеством флагов. Такой интерфейс уже знаком пользователям по `git`, `kubectl` и `docker`.

```python
parser = argparse.ArgumentParser(description="myapp CLI")
subparsers = parser.add_subparsers(dest="command", required=True)

# --- deploy subcommand ---
deploy_parser = subparsers.add_parser("deploy", help="Deploy the application")
deploy_parser.add_argument("env", choices=["staging", "prod"])
deploy_parser.add_argument("--dry-run", action="store_true",
                           help="Print actions without executing them")
deploy_parser.add_argument("--image-tag", default="latest")

# --- status subcommand ---
status_parser = subparsers.add_parser("status", help="Show deployment status")
status_parser.add_argument("env", nargs="?", default="prod",
                            help="Environment to check (default: prod)")

args = parser.parse_args()

if args.command == "deploy":
    deploy(args.env, dry_run=args.dry_run, tag=args.image_tag)
elif args.command == "status":
    show_status(args.env)
```

**`required=True` для subparsers:** в Python 3.7+ подкоманды по умолчанию необязательны. Если подкоманда не указана, ошибка не возникнет, пока не задано `required=True`. Всегда указывайте этот параметр явно или проверяйте `args.command is None` и выводите справку вручную.

Для больших инструментов удобнее назначать функцию непосредственно каждой подкоманде через `set_defaults(func=...)`. Это избавляет от цепочки if/elif:

```python
deploy_parser.set_defaults(func=deploy)
status_parser.set_defaults(func=show_status)

args = parser.parse_args()
args.func(args)   # dispatches to the right function automatically
```

Такой подход хорошо масштабируется: модуль каждой подкоманды регистрирует себя, а главной точке входа не нужно напрямую импортировать или знать отдельные команды.

---

### Коды завершения

Код завершения — это результат работы CLI-инструмента. Все последующие системы — CI/CD-конвейеры, условия shell и системы мониторинга — используют его для определения успеха или ошибки. Неверные коды могут незаметно скрывать сбои.

| Код | Значение | Соглашение |
|---|---|---|
| `0` | Успех | Универсально |
| `1` | Общая ошибка / нездоровое состояние | Эксплуатационные скрипты |
| `2` | Неверное использование / аргументы | `argparse` использует автоматически |
| `3-125` | Коды ошибок инструмента | Документируйте в `--help` или docstring |
| `126` | Команда не исполняема | Зарезервировано shell |
| `127` | Команда не найдена | Зарезервировано shell |
| `130` | Прервано Ctrl-C | Shell (128 + SIGINT) |

```python
import sys

sys.exit(0)    # success
sys.exit(1)    # failure — something went wrong at runtime

# Handle Ctrl-C cleanly — don't print a traceback to the user
try:
    main()
except KeyboardInterrupt:
    print("\nInterrupted", file=sys.stderr)
    sys.exit(130)
```

**Особенность конвейеров:** в Bash `set -e` завершает shell при любом ненулевом коде. Если инструмент возвращает 1 в значении «ничего не найдено», конвейер может неожиданно остановиться. Выбирайте коды в соответствии со смыслом: 0 для ожидаемого результата, ненулевой — для настоящего сбоя. Если отсутствие результата нормально, возвращайте 0 и позволяйте вызывающей стороне проверить вывод.

**Всегда явно вызывайте `sys.exit()`**, а не полагайтесь на естественное завершение скрипта. При обычном завершении Python возвращает 0 независимо от того, была ли работа успешной, что может скрыть ошибки в строгих конвейерах.

---

### stdout и stderr

Unix-инструменты разделяют данные и диагностику между двумя потоками вывода. Благодаря этому вывод можно передавать другим программам через конвейер, не смешивая его с сообщениями журнала.

| Поток | Назначение | Перенаправление |
|---|---|---|
| `stdout` | Данные — результат команды | `> file`, `\| next-command` |
| `stderr` | Ошибки, предупреждения, прогресс и отладка | `2> file`, `2>/dev/null` |

```python
import sys

# Results go to stdout — these can be piped or redirected
print("web01:80 UP")
print("db:5432 DOWN")

# Diagnostics go to stderr — these don't pollute piped output
print("ERROR: connection refused on db:5432", file=sys.stderr)
print(f"[debug] timeout set to {args.timeout}s", file=sys.stderr)

# Helper functions to keep the pattern consistent across a codebase
def info(msg):
    print(msg, file=sys.stderr)

def error(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
```

**Проверка разделения stderr:**

```bash
# Count only data lines — log noise should not appear here
./tool 2>/dev/null | wc -l

# See only diagnostics — data should not appear here
./tool > /dev/null

# Capture both streams separately
./tool > results.txt 2> errors.txt
```

**Буферизация stdout:** Python буферизует stdout, если вывод направлен не в терминал, а в конвейер. Долгоживущий инструмент может не передавать строки потребителю до сброса буфера. Используйте `print(..., flush=True)` или запускайте Python с `PYTHONUNBUFFERED=1`.

---

### Structured Logging with the `logging` Module

For tools that run unattended (cron, CI, systemd), `print` statements are insufficient. The `logging` module adds severity levels, timestamps, and the ability to route output to files or external systems — all configurable without changing your code.

```python
import logging
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--verbose", "-v", action="store_true")
args = parser.parse_args()

logging.basicConfig(
    level=logging.DEBUG if args.verbose else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,   # keep logs off stdout
)

log = logging.getLogger(__name__)

log.debug("Connecting to %s:%d", host, port)   # only shown with --verbose
log.info("Health check started for %d hosts", len(args.hosts))
log.warning("Response time %.1fs exceeds threshold", elapsed)
log.error("Service unreachable: %s", host)
```

**Why `getLogger(__name__)`?** It names the logger after the module, so when your tool grows into a package with multiple files, log messages identify their source. Using the root logger directly (`logging.info(...)`) works for single-file tools but doesn't scale.

| Level | Numeric value | Use for |
|---|---|---|
| `DEBUG` | 10 | Detailed diagnostic info — off by default |
| `INFO` | 20 | Confirmation that things are working |
| `WARNING` | 30 | Something unexpected but non-fatal |
| `ERROR` | 40 | A failure — the operation did not complete |
| `CRITICAL` | 50 | The tool cannot continue at all |

**Format for machine parsing:** If your tool's logs are ingested by a log aggregator (Datadog, Loki, Splunk), consider JSON output instead of a human-readable format. Use `python-json-logger` or write a custom formatter:

```python
import json, logging

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "time": self.formatTime(record),
            "level": record.levelname,
            "msg": record.getMessage(),
        })

handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(JSONFormatter())
logging.getLogger().addHandler(handler)
```

---

### Config from Environment Variables and CLI Flags

The twelve-factor app pattern for configuration: environment variables set the baseline, CLI flags allow per-invocation overrides. This lets the same tool work in CI (where config comes from environment variables) and interactively (where engineers pass flags).

```python
import os
import argparse

# Read from environment, with hard-coded fallback
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
API_TOKEN = os.environ.get("API_TOKEN")  # no default — must be provided

parser = argparse.ArgumentParser()
parser.add_argument("--db-host", default=DB_HOST,
                    help=f"Database host (default: $DB_HOST or '{DB_HOST}')")
parser.add_argument("--db-port", type=int, default=DB_PORT,
                    help=f"Database port (default: $DB_PORT or {DB_PORT})")
parser.add_argument("--token", default=API_TOKEN,
                    help="API token (default: $API_TOKEN)")

args = parser.parse_args()

# Validate required values early — fail before doing any work
if not args.token:
    parser.error("--token is required (or set $API_TOKEN)")
```

**`parser.error()`** prints a usage message and exits with code 2 — the standard exit code for argument errors. Use it for validation failures that are conceptually argument problems (missing required config, invalid combinations).

**Security note:** Never put secrets in CLI flags in production. Flags appear in `ps aux` output and shell history. Environment variables are better, but still visible in `/proc/<pid>/environ` to root. For highest security use file-based secrets: `--token-file /run/secrets/api_token` with `type=argparse.FileType("r")`.

**Precedence order** (most to least specific): CLI flag → environment variable → config file → hard-coded default. Document this order explicitly in your `--help` text so operators know what takes priority when things don't behave as expected.

---

### Dry-Run Pattern

Dry-run is a first-class feature for any tool that modifies state. The pattern: wrap all side-effecting operations in helper functions that either execute or log based on a flag. The rest of your business logic stays unaware of the mode.

```python
import subprocess
import shutil
import sys

def run_cmd(cmd, dry_run=False):
    """Execute a shell command, or print it if dry_run is True."""
    if dry_run:
        print(f"[dry-run] would run: {' '.join(cmd)}", file=sys.stderr)
        return 0
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("Command failed: %s\n%s", " ".join(cmd), result.stderr.strip())
    return result.returncode

def move_file(src, dst, dry_run=False):
    """Move a file, or print what would happen."""
    if dry_run:
        print(f"[dry-run] would move: {src} → {dst}", file=sys.stderr)
        return
    shutil.move(src, dst)

def delete_resource(name, dry_run=False):
    """Delete a resource via API, or print what would happen."""
    if dry_run:
        print(f"[dry-run] would delete resource: {name}", file=sys.stderr)
        return
    api.delete(name)
```

**Key design principle:** The same code path runs in both modes. Do not scatter `if not dry_run: do_thing(); else: log_thing()` throughout your business logic — that leads to divergence between modes and bugs where dry-run tests a different execution path than real runs. Push the conditional into the side-effecting primitives and let the rest of the code be unaware of it.

A common extension is adding a `--yes` / `--confirm` flag for destructive operations: require explicit confirmation unless `--yes` is passed, and make `--dry-run` imply no confirmation prompt.

---

### Making a Script Installable

A script that lives as a single `.py` file is fine for personal use, but for team tools it should be installable via pip. This makes it available on `$PATH` without activating a virtualenv or knowing where the file lives.

**Minimal `pyproject.toml`:**

```toml
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "myapp-cli"
version = "1.0.0"
requires-python = ">=3.9"
dependencies = ["requests>=2.28"]

[project.scripts]
# "myapp" becomes the command name on $PATH
myapp = "myapp.cli:main"
```

**Package structure:**

```
myapp/
├── __init__.py
└── cli.py       # contains def main(): ...
pyproject.toml
```

**Install and use:**

```bash
pip install -e .        # editable install — changes to source take effect immediately
myapp deploy staging    # available as a real command
which myapp             # /usr/local/bin/myapp or ~/.local/bin/myapp
```

**`if __name__ == "__main__":` guard:** Always include this at the bottom of your entry-point module. It allows the file to be imported without executing, which is required for testing and for the installed script entry point to work correctly.

```python
def main():
    args = parse_args()
    # ...

if __name__ == "__main__":
    main()
```

---

## Примеры

### Example 1: Production Health Check Tool

A complete, runnable tool that checks TCP connectivity for multiple hosts, supports retries, and exits correctly for use in CI.

```python
#!/usr/bin/env python3
"""
healthcheck — probe TCP endpoints and report status.

Exit codes:
  0  All hosts reachable
  1  One or more hosts unreachable
  2  Invalid arguments
"""
import argparse
import socket
import sys
import time
import logging

def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__,
        # RawDescriptionHelpFormatter preserves the exit codes block as-is
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("hosts", nargs="+", metavar="HOST:PORT",
                   help="Endpoints to probe, e.g. web01:80 db:5432")
    p.add_argument("--timeout", type=float, default=3.0,
                   help="TCP connection timeout in seconds (default: 3.0)")
    p.add_argument("--retries", type=int, default=0,
                   help="Retry failed connections N times before marking down (default: 0)")
    p.add_argument("--retry-delay", type=float, default=1.0,
                   help="Seconds between retries (default: 1.0)")
    p.add_argument("--output", choices=["text", "json"], default="text",
                   help="Output format (default: text)")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def check_tcp(host, port, timeout):
    """Return True if TCP connection succeeds, False otherwise."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def probe(endpoint, timeout, retries, retry_delay):
    """Probe an endpoint with retries. Returns (up: bool, attempts: int)."""
    try:
        host, port_str = endpoint.rsplit(":", 1)
        port = int(port_str)
    except ValueError:
        logging.error("Invalid endpoint format (expected HOST:PORT): %s", endpoint)
        sys.exit(2)

    for attempt in range(1 + retries):
        if attempt > 0:
            logging.debug("Retry %d/%d for %s", attempt, retries, endpoint)
            time.sleep(retry_delay)
        if check_tcp(host, port, timeout):
            return True, attempt + 1

    return False, 1 + retries


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    results = {}
    for endpoint in args.hosts:
        up, attempts = probe(endpoint, args.timeout, args.retries, args.retry_delay)
        results[endpoint] = {"up": up, "attempts": attempts}

    # Output goes to stdout so it can be piped or redirected
    if args.output == "json":
        import json
        print(json.dumps(results, indent=2))
    else:
        for endpoint, info in results.items():
            status = "UP" if info["up"] else "DOWN"
            print(f"{endpoint:<30} {status}")

    # Exit 1 if any host is down — CI will catch this
    all_up = all(v["up"] for v in results.values())
    sys.exit(0 if all_up else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
```

**Setup and verification:**

```bash
chmod +x healthcheck.py

# All up — exits 0
./healthcheck.py google.com:80 github.com:443
# google.com:80                  UP
# github.com:443                 UP
echo $?   # 0

# One down — exits 1 (useful in CI: the pipeline step fails)
./healthcheck.py google.com:80 localhost:9999
echo $?   # 1

# JSON output for downstream parsing
./healthcheck.py google.com:80 --output json 2>/dev/null
# {
#   "google.com:80": {"up": true, "attempts": 1}
# }

# Verbose shows debug messages on stderr, clean data on stdout
./healthcheck.py localhost:9999 --retries 2 --retry-delay 0.5 -v 2>&1
```

---

### Example 2: Multi-Subcommand Deploy Tool

A realistic deployment tool with `deploy`, `status`, and `rollback` subcommands, demonstrating the `set_defaults(func=...)` dispatch pattern.

```python
#!/usr/bin/env python3
"""deploy — application deployment tool."""
import argparse
import sys
import logging

log = logging.getLogger(__name__)

# ── subcommand handlers ────────────────────────────────────────────────────────

def cmd_deploy(args):
    log.info("Deploying %s to %s (tag: %s)", args.app, args.env, args.image_tag)
    if args.dry_run:
        print(f"[dry-run] kubectl set image deployment/{args.app} "
              f"{args.app}=registry/{args.app}:{args.image_tag} -n {args.env}",
              file=sys.stderr)
        return 0
    # real deploy logic here
    log.info("Deploy complete")
    return 0


def cmd_status(args):
    # Simulate fetching status — in reality call kubectl or an API
    print(f"{'APP':<20} {'ENV':<12} STATUS")
    print(f"{args.app:<20} {args.env:<12} Running (3/3 replicas)")
    return 0


def cmd_rollback(args):
    log.warning("Rolling back %s in %s to revision %s",
                args.app, args.env, args.revision or "previous")
    if not args.yes and not args.dry_run:
        confirm = input("This will cause a brief outage. Continue? [y/N] ")
        if confirm.lower() != "y":
            print("Aborted.", file=sys.stderr)
            return 1
    log.info("Rollback initiated")
    return 0


# ── argument parsing ───────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verbose", "-v", action="store_true")

    sub = p.add_subparsers(dest="command", required=True)

    # deploy
    dp = sub.add_parser("deploy", help="Deploy an application")
    dp.add_argument("app", help="Application name")
    dp.add_argument("env", choices=["staging", "prod"])
    dp.add_argument("--image-tag", default="latest")
    dp.add_argument("--dry-run", action="store_true")
    dp.set_defaults(func=cmd_deploy)

    # status
    sp = sub.add_parser("status", help="Show deployment status")
    sp.add_argument("app", help="Application name")
    sp.add_argument("--env", default="prod", choices=["staging", "prod"])
    sp.set_defaults(func=cmd_status)

    # rollback
    rp = sub.add_parser("rollback", help="Roll back to a previous revision")
    rp.add_argument("app")
    rp.add_argument("env", choices=["staging", "prod"])
    rp.add_argument("--revision", help="Revision to roll back to (default: previous)")
    rp.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    rp.add_argument("--dry-run", action="store_true")
    rp.set_defaults(func=cmd_rollback)

    return p.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
        stream=sys.stderr,
    )
    sys.exit(args.func(args))   # each handler returns an exit code


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(130)
```

**Usage:**

```bash
./deploy.py deploy myapi staging --image-tag v1.4.2 --dry-run
# [dry-run] kubectl set image deployment/myapi myapi=registry/myapi:v1.4.2 -n staging

./deploy.py status myapi
# APP                  ENV          STATUS
# myapi                prod         Running (3/3 replicas)

./deploy.py rollback myapi prod --yes
# WARNING  Rolling back myapi in prod to revision previous
# INFO     Rollback initiated
```

---

### Example 3: Log Parser That Reads from stdin or File

A tool that parses nginx access logs, counts status codes, and outputs a summary. Demonstrates the stdin-or-file pattern that makes tools composable in pipelines.

```python
#!/usr/bin/env python3
"""
logsummary — summarise HTTP status codes from nginx access logs.

Usage:
  ./logsummary.py access.log
  cat access.log | ./logsummary.py
  ./logsummary.py access.log --min-count 10 --output json
"""
import argparse
import sys
import re
import json
from collections import Counter

# nginx default log format — captures the status code in group 1
LOG_PATTERN = re.compile(r'"\w+ \S+ HTTP/\d\.\d" (\d{3})')


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    # nargs="?" with default="-" means: use stdin if no file is given
    p.add_argument("logfile", nargs="?", type=argparse.FileType("r"),
                   default="-", help="Log file to parse (default: stdin)")
    p.add_argument("--min-count", type=int, default=1,
                   help="Only show status codes appearing at least N times")
    p.add_argument("--output", choices=["text", "json"], default="text")
    return p.parse_args()


def summarise(stream, min_count):
    counts = Counter()
    for line in stream:
        m = LOG_PATTERN.search(line)
        if m:
            counts[m.group(1)] += 1
    return {k: v for k, v in sorted(counts.items()) if v >= min_count}


def main():
    args = parse_args()
    summary = summarise(args.logfile, args.min_count)

    if args.output == "json":
        print(json.dumps(summary))
    else:
        print(f"{'STATUS':<10} {'COUNT':>8}")
        print("-" * 20)
        for status, count in summary.items():
            print(f"{status:<10} {count:>8}")

    sys.exit(0)


if __name__ == "__main__":
    main()
```

**Usage — composability in action:**

```bash
# Parse a file directly
./logsummary.py /var/log/nginx/access.log

# Pipe from another tool — stdin mode activates automatically
tail -f /var/log/nginx/access.log | ./logsummary.py

# Chain with other Unix tools — only data on stdout
./logsummary.py access.log --output json 2>/dev/null | jq '.["500"]'

# Filter to only high-volume status codes
./logsummary.py access.log --min-count 100

# STATUS        COUNT
# --------------------
# 200           84321
# 304            9102
# 404             211
```

---

## Практические задания

### Exercise 1: Build a Service Checker with Proper Exit Codes

Write a CLI tool called `svccheck.py` that accepts one or more `HOST:PORT` arguments and a `--timeout` flag. For each host, attempt a TCP connection. Print results to stdout (`HOST:PORT UP/DOWN`), print any errors to stderr, and exit 0 only if all hosts are reachable.

Test that your exit codes are correct:

```bash
python svccheck.py google.com:80; echo "Exit: $?"       # should print 0
python svccheck.py localhost:9999; echo "Exit: $?"      # should print 1
python svccheck.py --timeout abc google.com:80          # should print usage error and exit 2
```

**Constraint:** Do not use the healthcheck example directly. Write the argument parsing and TCP logic yourself, then compare.

---

### Exercise 2: Add Subcommands to an Existing Script

Take any single-function script you have (or write a minimal one that has a `check` operation). Refactor it to support two subcommands: `check` (existing behavior) and `report` (prints a summary of the last N results from a log file). Requirements:

- Use `set_defaults(func=...)` dispatch — no if/elif on `args.command`.
- `check` must accept `--dry-run` and honor it by printing what it would do without doing it.
- `report` must accept `--lines` (integer, default 100) controlling how many log lines to read.
- Running the tool with no subcommand must print help and exit 2.

Verify with:

```bash
python mytool.py                          # prints help, exits 2
python mytool.py check web01:80 --dry-run # prints [dry-run] message, exits 0
python mytool.py report --lines 50        # prints summary, exits 0
```

---

### Exercise 3: Environment Variable + CLI Flag Precedence

Write a script that configures a hypothetical database connection from three sources: a hard-coded default, an environment variable, and a CLI flag. The CLI flag must win over the environment variable, which must win over the default.

```bash
# Should use default: localhost
python dbconn.py --show-config

# Should use environment variable
DB_HOST=db.internal python dbconn.py --show-config

# CLI flag overrides env var
DB_HOST=db.internal python dbconn.py --db-host override.host --show-config
```

Add a `--password-file` argument that uses `argparse.FileType("r")` to read a password from a file. Verify that a missing file causes `argparse` to exit with code 2 before your code runs — add a `print("my code ran")` at the start of `main()` to confirm it is never reached.

---

### Exercise 4: stdin/stdout Pipeline Tool

Write a tool called `jsonfilter.py` that reads JSON lines (one JSON object per line) from either a file argument or stdin, filters to lines where a specified field matches a value, and writes matching lines to stdout or a file.

```bash
# Generate test data
echo '{"level":"ERROR","msg":"disk full"}' > test.jsonl
echo '{"level":"INFO","msg":"started"}' >> test.jsonl
echo '{"level":"ERROR","msg":"OOM"}' >> test.jsonl

# Filter by field value
python jsonfilter.py --field level --value ERROR test.jsonl
# {"level":"ERROR","msg":"disk full"}
# {"level":"ERROR","msg":"OOM"}

# Stdin mode — composable in a pipeline
cat test.jsonl | python jsonfilter.py --field level --value INFO
# {"level":"INFO","msg":"started"}

# Write output to a file instead of stdout
python jsonfilter.py --field level --value ERROR test.jsonl --output errors.jsonl
```

**Requirements:** Use `argparse.FileType` for both input and output. Ensure log/error messages go to stderr so the stdout output stays clean for piping. Non-matching lines must be silently skipped — do not print warnings for them. Malformed JSON lines should print a warning to stderr and be skipped without aborting.

---

### Быстрая проверка

1. Split a shell command string into a list of arguments.

   ```python
   import shlex; print(shlex.split('grep -r "error log" /var/log'))
   ```

   ```expected_output
   ['grep', '-r', 'error log', '/var/log']
   ```

hint: Think about Python's standard library module designed specifically for parsing shell-like syntax, which handles quoted strings and spaces correctly.
hint: Look into the shlex module and its split() function, which treats quoted substrings like 'error log' as single tokens.

2. Parse a flag with a default using `argparse`.

   ```python
   import argparse; p = argparse.ArgumentParser(); p.add_argument('--count', type=int, default=5); args = p.parse_args([]); print(args.count)
   ```

   ```expected_output
   5
   ```
hint: Think about how argparse lets you define optional arguments that fall back to a preset value when not provided by the user.
hint: Use parser.add_argument('--number', type=int, default=5) to register a flag that returns a specific integer when the flag is omitted from the command line.
