---
title: Subprocess и автоматизация
module: python
duration_min: 20
difficulty: intermediate
tags: [python, subprocess, automation, shell, os, shlex]
exercises: 4
---

## Обзор

DevOps-скриптам постоянно приходится выходить за пределы Python и обращаться к операционной системе: перезапускать службу, запускать `kubectl`, проверять использование диска, вызывать `git` или сжимать архив. Стандартный способ делать это — модуль Python `subprocess`. Он раздельно собирает stdout и stderr, предоставляет коды завершения, поддерживает тайм-ауты и помогает избежать shell injection, возможного при использовании устаревших альтернатив вроде `os.system()` или `commands.getoutput()`. Этот модуль пригодится почти в каждом production-скрипте автоматизации.

Философия `subprocess` — явный контроль. Команда задаётся списком строк: без интерполяции shell и без неявного запуска `/bin/sh`, если вы сами этого не запросили. Такой подход соответствует тому, как ядро запускает программы через `execve`, и избавляет от неожиданных эффектов кавычек, glob-шаблонов и раскрытия переменных. Если нужны возможности shell (конвейеры, перенаправления, glob), их следует включать осознанно и учитывать последствия для безопасности.

В цепочке DevOps-инструментов `subprocess` связывает логику Python с любыми CLI-инструментами окружения. Он находится ниже высокоуровневых библиотек вроде `boto3` и `kubernetes-client` (у которых есть собственные HTTP-транспорты), но выше низкоуровневых вызовов `os.fork()` и `os.execve()`. Если отдельного SDK нет или нужно единообразно обернуть существующий CLI-инструмент, используйте `subprocess`. Глубокое понимание модуля позволяет надёжно автоматизировать развёртывания, проверки состояния, запросы к инфраструктуре и конвейеры сборки из одного процесса Python.

---

## Основные понятия

### subprocess.run — рекомендуемый вариант по умолчанию

`subprocess.run()` — высокоуровневая функция, появившаяся в Python 3.5. Она ждёт завершения команды и возвращает объект `CompletedProcess`. Используйте её для большинства задач автоматизации.

```python
import subprocess

result = subprocess.run(
    ["ls", "-la", "/etc"],    # always a list — avoids shell injection
    capture_output=True,      # shorthand for stdout=PIPE, stderr=PIPE
    text=True,                # decode bytes → str using locale encoding
    check=False,              # don't auto-raise on non-zero exit
)

print(result.stdout)          # captured standard output
print(result.stderr)          # captured standard error
print(result.returncode)      # integer: 0 = success, anything else = failure
```

| Параметр | Эффект | Когда использовать |
|-----------|--------|-------------|
| `capture_output=True` | Сохраняет stdout и stderr отдельно в строках | Почти всегда — позволяет анализировать вывод |
| `text=True` | Декодирует байты в str с кодировкой локали | При разборе текстового вывода |
| `check=True` | Вызывает `CalledProcessError` при ненулевом коде завершения | Когда ошибка должна остановить скрипт |
| `timeout=N` | Вызывает `TimeoutExpired` через N секунд | Сетевые запросы, долгие сборки |
| `cwd="/path"` | Задаёт рабочий каталог подпроцесса | Запуск `git`, `make`, `npm` в каталоге проекта |
| `env=dict` | Заменяет окружение, а не дополняет его | Передача секретов, настройка PATH |
| `input="string"` | Передаёт строку в stdin подпроцесса | Передача данных между командами без shell |
| `stdin=DEVNULL` | Закрывает stdin, не позволяя процессу запросить ввод | Неинтерактивные скрипты и CI-конвейеры |

**Предупреждение о `shell=True`:** команда передаётся в `/bin/sh -c`. Если часть команды получена от пользователя или из внешнего источника, возникает риск command injection. Со списком аргументов режим также работает неожиданно: первый элемент становится командой, остальные — позиционными параметрами `$0`, `$1` и т. д. Обычно это не требуется. Используйте список аргументов и `shell=False` (значение по умолчанию), если нет конкретной документированной причины поступить иначе.

**`env` заменяет окружение, а не дополняет его:** если передать `env={"MY_VAR": "value"}`, подпроцесс получит только эту переменную. `PATH`, `HOME`, `USER` и остальные переменные исчезнут. Команды `git` или `kubectl` могут перестать находиться. Чтобы безопасно дополнить текущее окружение:

```python
import os
import subprocess

env = os.environ.copy()       # start from the full current environment
env["MY_SECRET"] = "hunter2"  # add or override specific keys
env.pop("DEBUG", None)        # remove keys you explicitly don't want to pass

subprocess.run(["my-tool"], env=env, check=True)
```

---

### Проверка кодов завершения

Программы Unix сообщают об успехе или ошибке через код завершения: ноль означает успех, ненулевое значение — ошибку. Игнорирование кодов завершения — одна из самых частых ошибок в скриптах автоматизации: скрипт продолжает работу после неудачного `kubectl apply` и оставляет кластер в некорректном состоянии.

```python
import subprocess

# Option 1 — check=True: raises CalledProcessError on failure
# Best when failure should immediately halt the script
try:
    subprocess.run(
        ["systemctl", "restart", "nginx"],
        check=True,
        capture_output=True,
        text=True,
    )
    print("nginx restarted successfully")
except subprocess.CalledProcessError as e:
    # e.returncode, e.stdout, e.stderr all available
    print(f"Restart failed (exit {e.returncode}): {e.stderr.strip()}")
    raise SystemExit(1)

# Option 2 — manual check: gives you branching logic on the result
result = subprocess.run(
    ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
    capture_output=True,
    text=True,
)
if result.returncode == 0:
    print("Host reachable")
else:
    print(f"Host unreachable (exit {result.returncode})")
```

**Атрибуты `CalledProcessError`:** при `check=True` поля `e.stdout` и `e.stderr` заполняются только при использовании `capture_output=True`. Без захвата они равны `None`, и сообщение об ошибке теряется. В production-скриптах сочетайте `check=True` с `capture_output=True`, чтобы точно записывать причину сбоя.

**Полезно знать соглашения о кодах завершения:**

| Инструмент | Exit 0 | Exit 1 | Exit 2+ |
|------|--------|--------|---------|
| Большинство Unix-инструментов | Успех | Общая ошибка | Зависит от инструмента |
| `grep` | Совпадение найдено | Совпадений нет | Ошибка (неверные аргументы) |
| `diff` | Файлы одинаковы | Файлы различаются | Ошибка |
| `curl` | Успех | Ошибка протокола | — |
| `kubectl` | Успех | Ошибка API или аутентификации | — |
| `ansible-playbook` | Все задачи успешны | Одна или несколько задач завершились с ошибкой | — |

**Код завершения `grep` равный 1 — не обязательно ошибка:** распространённая проблема — запускать `grep` с `check=True` для проверки наличия шаблона. Если совпадений нет, возникает `CalledProcessError`, хотя ничего не сломано. Используйте `check=False` и проверяйте `result.returncode` самостоятельно.

---

### Захват и разбор вывода

Главное преимущество `subprocess` в DevOps-автоматизации — преобразование вывода CLI в структурированные данные Python. Типовой процесс: выполнить команду, захватить stdout и разобрать его средствами Python или через `json.loads`.

```python
import subprocess
import json

def get_running_services():
    """Return a list of active systemd service names."""
    result = subprocess.run(
        [
            "systemctl", "list-units",
            "--type=service",
            "--state=running",
            "--no-pager",     # disable pager so output goes to stdout
            "--plain",        # no decorative borders
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    services = []
    for line in result.stdout.splitlines():
        if ".service" in line:
            services.append(line.split()[0])   # first column is the unit name
    return services


def disk_usage_pct(mount="/"):
    """Return disk usage percentage for a mount point as an integer."""
    result = subprocess.run(
        ["df", "--output=pcent", mount],  # --output selects columns (GNU df)
        capture_output=True,
        text=True,
        check=True,
    )
    # Output: "Use%\n 45%\n"
    pct_line = result.stdout.strip().splitlines()[-1]
    return int(pct_line.strip().rstrip("%"))


def get_pod_status(namespace="default"):
    """Return pod names and their statuses from kubectl as a list of dicts."""
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)   # structured output beats string parsing
    return [
        {
            "name": item["metadata"]["name"],
            "phase": item["status"].get("phase", "Unknown"),
        }
        for item in data.get("items", [])
    ]


def git_current_branch(repo_path="."):
    """Return the current git branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=repo_path,   # run git inside the target repo directory
    )
    return result.stdout.strip()
```

**Предпочитайте форматы для машинной обработки:** многие инструменты по умолчанию выводят таблицы для человека. Ищите флаги, отключающие оформление и создающие стабильный вывод для разбора:

| Tool | Human output | Machine-friendly flag |
|------|-------------|----------------------|
| `systemctl` | Bordered table | `--plain --no-pager` |
| `kubectl` | Column-aligned | `-o json` or `-o jsonpath=...` |
| `docker inspect` | JSON by default | `--format '{{json .}}'` |
| `df` | Full table | `--output=pcent` |
| `git log` | Pretty log | `--format="%H %s"` or `--porcelain` |
| `aws cli` | Text table | `--output json` |

**Совет по разбору:** если инструмент поддерживает `--output json` или аналогичный параметр, используйте его и разбирайте результат через `json.loads(result.stdout)`. JSON устойчив к изменениям пробелов, порядка столбцов и версий инструмента. Разбор строк по разделителям может незаметно сломаться при изменении формата вывода.

---

### Тайм-ауты

Без тайм-аута зависший подпроцесс (недоступная сеть, взаимная блокировка или интерактивный запрос ввода) может остановить весь скрипт автоматизации навсегда. В CI/CD это блокирует очередь развёртывания, пока кто-нибудь не отменит задание вручную.

```python
import subprocess

def check_http_health(url, timeout_sec=10):
    """Return True if the URL responds with a 2xx status."""
    try:
        result = subprocess.run(
            [
                "curl",
                "-sf",                          # -s silent, -f fail on HTTP errors
                "--max-time", str(timeout_sec), # curl-level timeout in seconds
                url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout_sec + 2,            # Python-level hard kill, slightly larger
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired as e:
        print(f"Timed out after {e.timeout}s: {url}")
        # e.stdout and e.stderr may contain partial output — useful for debugging
        if e.stdout:
            print(f"Partial output: {e.stdout}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"curl failed (exit {e.returncode}): {e.stderr.strip()}")
        return False


def run_with_timeout(cmd, timeout_sec=30):
    """Run a command with timeout, return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout_sec}s"
```

**Двухуровневый тайм-аут:** задавайте тайм-аут и самому инструменту (например, `curl --max-time`, `ssh -o ConnectTimeout=`), и Python через `timeout=`. Тайм-аут инструмента завершает его штатно с кодом ошибки и сообщением в stderr. Тайм-аут Python принудительно завершает процесс через `SIGKILL`, если сам инструмент завис и игнорирует сигналы. Задайте тайм-аут Python на несколько секунд больше, чтобы инструмент успел завершиться корректно.

**После `TimeoutExpired`:** Python завершает дочерний процесс. Вывод, накопленный до завершения, доступен в `e.stdout` и `e.stderr`; изучайте его при диагностике зависания.

---

### Потоковый вывод без захвата

Для вывода в реальном времени — долгих сборок, тестов и скриптов развёртывания — не захватывайте вывод. Направьте stdout и stderr прямо в терминал. Это поведение по умолчанию: просто не указывайте `capture_output`.

```python
import subprocess

# stdout and stderr go to the terminal in real time
# No capture_output — stdout/stderr default to inheriting from parent process
result = subprocess.run(
    ["docker", "build", "-t", "myapp:latest", "."],
    check=True,
)

# Streaming with error handling: playbooks, migrations, test runners
try:
    subprocess.run(
        ["ansible-playbook", "site.yml", "-v"],
        check=True,
        # stdin=subprocess.DEVNULL prevents the playbook from waiting for input
        stdin=subprocess.DEVNULL,
    )
except subprocess.CalledProcessError as e:
    print(f"Playbook failed with exit code {e.returncode}")
    raise SystemExit(1)

# Redirect stderr to stdout — useful when a tool writes progress to stderr
subprocess.run(
    ["make", "build"],
    stderr=subprocess.STDOUT,  # merge stderr into stdout stream
    check=True,
)
```

**Одновременный вывод и сохранение результата — сложная задача:** если нужно показывать вывод в реальном времени *и* сохранять его для последующего анализа, используйте `subprocess.Popen` с потоками, которые одновременно читают каналы (см. раздел `Popen`). В большинстве DevOps-скриптов выбирайте что-то одно: вывод в терминал для оператора или захват вывода для программной обработки. Попытка сделать и то и другое только через `subprocess.run()` может привести к взаимной блокировке.

**`stdin=DEVNULL` в CI:** всегда задавайте этот параметр при запуске интерактивных инструментов (Ansible, Terraform и некоторых тестовых средств) в CI-конвейерах. Иначе инструмент, случайно запросивший ввод, может зависнуть вместо быстрого завершения с ошибкой.

---

### Передача данных между командами

`subprocess` позволяет явно организовать Unix-конвейер: вывод одной команды становится входом следующей через параметр `input=`. Это безопаснее, чем `shell=True` с shell-конвейером, поскольку каждый этап — отдельный проверяемый процесс, а shell не используется.

```python
import subprocess

def find_process(name):
    """Equivalent to: ps aux | grep <name> | grep -v grep"""
    ps = subprocess.run(
        ["ps", "aux"],
        capture_output=True, text=True, check=True,
    )
    grep = subprocess.run(
        ["grep", name],
        input=ps.stdout,          # pipe ps stdout to grep stdin
        capture_output=True, text=True,
        # check=False — grep exits 1 when no match; that's not an error here
    )
    result = subprocess.run(
        ["grep", "-v", "grep"],   # remove the grep process itself from results
        input=grep.stdout,
        capture_output=True, text=True,
    )
    return result.stdout.strip()
```

**Фильтруйте средствами Python:** для короткого вывода захватите результат целиком и обработайте строковыми операциями Python. Это читабельнее, позволяет избежать нюансов кодов завершения `grep` и ускоряет работу за счёт отсутствия дополнительных процессов:

```python
def find_process_py(name):
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True, check=True)
    lines = [l for l in result.stdout.splitlines() if name in l and "grep" not in l]
    return "\n".join(lines)
```

**Когда использовать конвейеры оболочки, а когда Python:** связывайте процессы средствами Python, если важна безопасность (например, команда содержит данные пользователя) или требуется точная обработка ошибок на каждом этапе. Используйте `shell=True` с конвейером оболочки только для коротких одноразовых скриптов с полностью фиксированной командой, когда нужны возможности оболочки вроде `|`, `>`, `&&` или раскрытия glob-шаблонов.

---

### shlex — безопасное формирование команды из строки

Иногда команда поступает в виде строки — из файла конфигурации, переменной окружения или пользовательского ввода. `shlex.split()` разбивает её на аргументы по правилам POSIX shell, корректно обрабатывая кавычки и экранирование, но не запускает сам shell.

```python
import shlex
import subprocess

# From a config file or environment variable:
cmd_str = 'kubectl get pods -n production -l "app=nginx"'
cmd_list = shlex.split(cmd_str)
# → ['kubectl', 'get', 'pods', '-n', 'production', '-l', 'app=nginx']

result = subprocess.run(cmd_list, capture_output=True, text=True, check=True)

# Going the other direction: quote a list into a safe shell string for logging
safe_str = shlex.join(cmd_list)   # Python 3.8+
print(f"Running: {safe_str}")
# → Running: kubectl get pods -n production -l 'app=nginx'

# Practical use: commands stored in YAML config
import yaml

config = yaml.safe_load("""
health_check: "curl -sf http://localhost:8080/health"
pre_deploy: "python manage.py migrate --no-input"
""")

for name, cmd_str in config.items():
    cmd = shlex.split(cmd_str)
    print(f"Running {name}: {cmd}")
    subprocess.run(cmd, check=True)
```

**`shlex.split` и `str.split()`:** `str.split()` разбивает строку по любому пробельному символу и портит аргументы в кавычках.

```python
cmd = 'kubectl exec pod-123 -- sh -c "echo hello world"'

cmd.split()        # ['kubectl', 'exec', 'pod-123', '--', 'sh', '-c', '"echo', 'hello', 'world"']
                   # 9 tokens — "echo hello world" split in two, quotes included

shlex.split(cmd)   # ['kubectl', 'exec', 'pod-123', '--', 'sh', '-c', 'echo hello world']
                   # 7 tokens — quoted string preserved correctly, quotes stripped
```

**Безопасность:** `shlex.split()` безопасно разбивает строку на аргументы, но не делает безопасным само её содержимое. Если `cmd_str` получен из недоверенного источника, злоумышленник всё ещё может внедрить произвольные команды. Используйте `shlex.split()` только для строк из доверенных источников — собственных конфигураций и переменных окружения.

---

### os.path и pathlib — операции с файловой системой

`subprocess` отвечает за запуск процессов, а `os.path` и `pathlib` — за файловую систему. На практике их часто используют вместе: находят файлы через pathlib, а затем передают пути командам subprocess.

```python
import os
import subprocess
from pathlib import Path

# pathlib — prefer for new code (Python 3.4+)
p = Path("/etc/nginx/nginx.conf")
p.exists()           # True/False
p.is_file()          # True if it's a regular file
p.is_dir()           # True if it's a directory
p.name               # "nginx.conf"
p.stem               # "nginx"
p.suffix             # ".conf"
p.parent             # PosixPath('/etc/nginx')
p.read_text()        # file contents as str
p.write_text("...")  # overwrite file (creates if not exists)

# Path construction — / operator is cleaner than os.path.join
config = Path("/etc") / "nginx" / "nginx.conf"

# Glob patterns
confs = list(Path("/etc/nginx").glob("*.conf"))        # immediate dir only
all_confs = list(Path("/etc/nginx").rglob("*.conf"))   # recursive

# Find large log files and report them
for path in Path("/var/log").rglob("*"):
    if path.is_file() and path.stat().st_size > 100 * 1024 * 1024:
        size_mb = path.stat().st_size // (1024 * 1024)
        print(f"Large file: {path} ({size_mb} MB)")

# Use pathlib to build subprocess commands cleanly
log_dir = Path("/var/log/nginx")
latest_log = max(log_dir.glob("access.log*"), key=lambda p: p.stat().st_mtime)

subprocess.run(
    ["tail", "-n", "100", str(latest_log)],  # str() for Python < 3.6
    check=True,
)
```

| Задача | `os.path` | `pathlib` |
|------|-----------|-----------|
| Объединить пути | `os.path.join(a, b, c)` | `Path(a) / b / c` |
| Проверить существование | `os.path.exists(p)` | `Path(p).exists()` |
| Это файл? | `os.path.isfile(p)` | `Path(p).is_file()` |
| Прочитать файл | `open(p).read()` | `Path(p).read_text()` |
| Записать файл | `open(p, "w").write(s)` | `Path(p).write_text(s)` |
| Список каталога | `os.listdir(p)` | `Path(p).iterdir()` |
| Рекурсивный поиск по шаблону | `os.walk()` + ручной фильтр | `Path(p).rglob("*.log")` |
| Размер файла | `os.stat(p).st_size` | `Path(p).stat().st_size` |
| Создать каталоги | `os.makedirs(p, exist_ok=True)` | `Path(p).mkdir(parents=True, exist_ok=True)` |

**`pathlib` вместе с subprocess:** в Python 3.6+ `subprocess.run()` принимает объекты `Path` там, где ожидается строковый путь. Явно вызывать `str(p)` не нужно. Для Python 3.5 и ниже преобразуйте путь через `str(p)`.

**Используйте `exist_ok=True`:** при создании каталогов в скриптах автоматизации передавайте этот параметр в `mkdir()`. Иначе при повторном запуске скрипт завершится с ошибкой, потому что каталог уже существует.

---

### subprocess.Popen — низкоуровневое управление

`subprocess.run()` покрывает большинство задач автоматизации. `Popen` — более низкоуровневый класс, на котором построен `run()`. Используйте его, когда нужно взаимодействовать с работающим процессом: постепенно передавать входные данные, читать вывод в реальном времени или выполнять параллельную работу.

```python
import subprocess
import threading

# Pattern 1: Start a long-running process and poll it
proc = subprocess.Popen(
    ["tail", "-f", "/var/log/syslog"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

# Read a fixed number of lines then terminate
for i, line in enumerate(proc.stdout):
    print(line, end="")
    if i >= 9:          # read 10 lines then stop
        break

proc.terminate()        # SIGTERM
proc.wait()             # wait for it to actually exit


# Pattern 2: Simultaneous real-time display + capture
# Requires threads because reading two pipes sequentially can deadlock
def stream_and_capture(cmd):
    """Run cmd, print output in real time, return captured output."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,   # merge stderr into stdout
        text=True,
    )
    captured = []

    def reader():
        for line in proc.stdout:
            print(line, end="", flush=True)   # real-time display
            captured.append(line)             # also capture

    t = threading.Thread(target=reader)
    t.start()
    proc.wait()
    t.join()
    return "".join(captured), proc.returncode


output, rc = stream_and_capture(["docker", "build", "-t", "myapp", "."])
if rc != 0:
    # Now we have the full output to log or send to an alerting system
    send_alert(f"Build failed:\n{output[-2000:]}")   # last 2000 chars
```

**Контекстный менеджер Popen:** всегда используйте `Popen` через `with subprocess.Popen(...) as proc:` либо явно вызывайте `proc.wait()` или `proc.communicate()`. Если не дождаться завершения процесса, он может остаться зомби до завершения скрипта.

**`communicate()` и ручное чтение:** `proc.communicate()` читает stdout и stderr целиком и ждёт завершения процесса — это аналог `subprocess.run(capture_output=True)`. Используйте его, если вывод в реальном времени не нужен. Если читать `proc.stdout` в цикле и не читать `proc.stderr`, процесс может зависнуть после заполнения буфера stderr. Пример с потоками выше избегает этого, предварительно объединяя stderr со stdout.

---

## Примеры

### Пример 1. Проверка состояния развёртывания

Полный скрипт, который развёртывает Docker-контейнер, ждёт, пока проверка состояния станет успешной, и выполняет откат при сбое.

```python
#!/usr/bin/env python3
"""
deploy.py — rolling deploy with health check and rollback
Usage: python deploy.py <image_tag>
"""
import subprocess
import sys
import time
from pathlib import Path


IMAGE = "myapp"
CONTAINER = "myapp-prod"
HEALTH_URL = "http://localhost:8080/health"
HEALTH_RETRIES = 10
HEALTH_INTERVAL = 3   # seconds between retries


def run(cmd, **kwargs):
    """Wrapper: always capture output, check by default, log the command."""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("check", True)
    print(f"  → {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, **kwargs)


def get_current_image():
    """Return the image currently running in the container, or None."""
    result = run(
        ["docker", "inspect", "--format", "{{.Config.Image}}", CONTAINER],
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def start_container(image_tag):
    run([
        "docker", "run", "-d",
        "--name", CONTAINER,
        "--rm",                          # auto-remove when stopped
        "-p", "8080:8080",
        f"{IMAGE}:{image_tag}",
    ])


def stop_container():
    run(["docker", "stop", CONTAINER], check=False)


def wait_for_healthy():
    """Poll the health endpoint until it responds or retries are exhausted."""
    for attempt in range(1, HEALTH_RETRIES + 1):
        result = subprocess.run(
            ["curl", "-sf", "--max-time", "5", HEALTH_URL],
            capture_output=True,
            timeout=8,
        )
        if result.returncode == 0:
            return True
        print(f"  Health check attempt {attempt}/{HEALTH_RETRIES} failed, waiting...")
        time.sleep(HEALTH_INTERVAL)
    return False


def deploy(new_tag):
    print(f"\n[deploy] Starting deployment: {IMAGE}:{new_tag}")

    # Save current image for rollback
    previous_image = get_current_image()
    print(f"[deploy] Current image: {previous_image or 'none'}")

    # Pull the new image first — fail early before touching the running container
    print("[deploy] Pulling new image...")
    run(["docker", "pull", f"{IMAGE}:{new_tag}"])

    # Stop current container
    if previous_image:
        print("[deploy] Stopping current container...")
        stop_container()

    # Start new container
    print("[deploy] Starting new container...")
    start_container(new_tag)

    # Health check
    print("[deploy] Waiting for health check...")
    if wait_for_healthy():
        print(f"[deploy] ✓ Deployment successful: {IMAGE}:{new_tag}")
        return True

    # Rollback
    print("[deploy] ✗ Health check failed — rolling back")
    stop_container()
    if previous_image:
        tag = previous_image.split(":")[-1]
        start_container(tag)
        print(f"[deploy] Rolled back to {previous_image}")
    return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <image_tag>")
        sys.exit(1)

    success = deploy(sys.argv[1])
    sys.exit(0 if success else 1)
```

**Verify it works:**
```bash
python deploy.py v1.2.3
echo "Exit code: $?"

# Check the running container
docker ps --filter name=myapp-prod --format "{{.Image}} {{.Status}}"
```

---

### Пример 2. Инструмент аудита Git-репозитория

Просканируйте каталог Git-репозиториев и выведите ветку, последний коммит и наличие незакоммиченных изменений.

```python
#!/usr/bin/env python3
"""
git_audit.py — report git status for all repos under a root directory
Usage: python git_audit.py /path/to/repos
"""
import subprocess
import sys
from pathlib import Path


def git(cmd, cwd):
    """Run a git command in a specific directory, return stdout or None on error."""
    result = subprocess.run(
        ["git"] + cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=15,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def repo_status(path):
    """Return a dict of status fields for a git repository."""
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    commit = git(["log", "-1", "--format=%h %s", "HEAD"], cwd=path)
    dirty_output = git(["status", "--porcelain"], cwd=path)

    # --porcelain produces one line per changed file; empty = clean
    is_dirty = bool(dirty_output)

    # Count commits ahead/behind the tracking branch
    ahead_behind = git(
        ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
        cwd=path,
    )
    ahead, behind = (0, 0)
    if ahead_behind:
        parts = ahead_behind.split()
        if len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])

    return {
        "path": str(path),
        "branch": branch or "unknown",
        "last_commit": commit or "unknown",
        "dirty": is_dirty,
        "ahead": ahead,
        "behind": behind,
    }


def find_repos(root):
    """Find all directories containing a .git folder."""
    return [p.parent for p in Path(root).rglob(".git") if p.is_dir()]


def main(root):
    repos = find_repos(root)
    if not repos:
        print(f"No git repositories found under {root}")
        sys.exit(1)

    print(f"Found {len(repos)} repositories under {root}\n")
    print(f"{'Repository':<40} {'Branch':<20} {'Dirty':<6} {'↑':<4} {'↓':<4} Last Commit")
    print("-" * 100)

    for repo in sorted(repos):
        s = repo_status(repo)
        dirty_flag = "YES" if s["dirty"] else "no"
        short_path = str(Path(s["path"]).relative_to(root))
        print(
            f"{short_path:<40} {s['branch']:<20} {dirty_flag:<6} "
            f"{s['ahead']:<4} {s['behind']:<4} {s['last_commit']}"
        )


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    main(root)
```

**Verify it works:**
```bash
python git_audit.py ~/projects
# Expected: table with one row per repo showing branch, dirty status, ahead/behind counts
```

---

### Пример 3. Мониторинг дискового пространства с оповещениями

Проверьте использование диска на всех точках монтирования, сохраните результаты в журнал и отправьте оповещение при превышении порога.

```python
#!/usr/bin/env python3
"""
disk_monitor.py — check disk usage and alert on thresholds
Designed to run as a cron job: */5 * * * * python /opt/scripts/disk_monitor.py
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

WARN_PCT = 80
CRIT_PCT = 90
LOG_FILE = Path("/var/log/disk_monitor.json")
ALERT_CMD = ["/usr/local/bin/send-slack-alert"]   # hypothetical alerting tool


def get_disk_usage():
    """Parse `df -P` output into a list of dicts. -P uses POSIX format."""
    result = subprocess.run(
        ["df", "-P", "-x", "tmpfs", "-x", "devtmpfs"],  # exclude virtual fs
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stdout.strip().splitlines()[1:]   # skip header row
    mounts = []
    for line in lines:
        parts = line.split()
        # POSIX df columns: Filesystem, 1024-blocks, Used, Available, Capacity%, Mounted
        pct = int(parts[4].rstrip("%"))
        mounts.append({
            "filesystem": parts[0],
            "mount": parts[5],
            "used_pct": pct,
            "available_kb": int(parts[3]),
        })
    return mounts


def send_alert(message, level="warn"):
    """Send an alert via external tool. Don't crash if alerting fails."""
    try:
        subprocess.run(
            ALERT_CMD + [f"--level={level}", message],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        # Alerting failure should not crash the monitor itself
        print(f"Warning: failed to send alert: {e}", file=sys.stderr)


def main():
    timestamp = datetime.utcnow().isoformat() + "Z"
    mounts = get_disk_usage()
    alerts = []

    for m in mounts:
        entry = {**m, "timestamp": timestamp, "status": "ok"}

        if m["used_pct"] >= CRIT_PCT:
            entry["status"] = "critical"
            msg = f"CRITICAL: {m['mount']} is {m['used_pct']}% full ({m['filesystem']})"
            print(msg)
            send_alert(msg, level="critical")
            alerts.append(msg)

        elif m["used_pct"] >= WARN_PCT:
            entry["status"] = "warning"
            msg = f"WARNING: {m['mount']} is {m['used_pct']}% full ({m['filesystem']})"
            print(msg)
            send_alert(msg, level="warn")
            alerts.append(msg)

        # Append JSON log line (one JSON object per line — easy to parse with jq)
        with LOG_FILE.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    if not alerts:
        print(f"[{timestamp}] All disks OK")

    # Non-zero exit when there are critical alerts — useful for cron monitoring
    critical = any("CRITICAL" in a for a in alerts)
    sys.exit(2 if critical else 0)


if __name__ == "__main__":
    main()
```

**Verify it works:**
```bash
python disk_monitor.py
echo "Exit: $?"

# Check the log output
tail -5 /var/log/disk_monitor.json | python -m json.tool

# Parse with jq to find mounts over 50%
jq 'select(.used_pct > 50)' /var/log/disk_monitor.json
```

---

## Практические задания

### Задание 1: перезапуск службы с проверкой идемпотентности

Напишите функцию Python `ensure_service_running(service_name)`, которая:
1. Проверяет, активна ли служба systemd, командой `systemctl is-active`
2. Если служба уже работает, выводит сообщение и завершает функцию без изменений
3. Если служба остановлена или завершилась с ошибкой, пытается запустить её через `systemctl start`
4. После запуска повторно проверяет состояние и вызывает исключение, если служба не стала активной

**Ограничения:** для проверки состояния используйте `check=False` (если служба неактивна, команда возвращает ненулевой код). Для запуска используйте `check=True`. Обработайте `CalledProcessError` и включите stderr в сообщение об ошибке.

**Проверка:** вызовите `ensure_service_running("cron")` (или `crond` в системах на базе RHEL). Затем передайте несуществующее имя службы и проверьте обработку ошибки.

---

### Задание 2: поиск процессов, превышающих порог памяти

Напишите скрипт, который:
1. Запускает `ps aux` и захватывает вывод
2. Разбирает строки, извлекая имя процесса и RSS (в выводе `ps aux` это шестой столбец, значение в КБ)
3. Отбирает процессы, использующие более 100 МБ ОЗУ
4. Выводит отсортированную таблицу (сначала самое большое потребление) с PID, именем процесса и памятью в МБ

**Ограничения:** выполняйте фильтрацию и сортировку средствами Python, не используйте `grep`, `awk` или `sort` через конвейер. Обработайте строку заголовка (`USER PID ...`), чтобы скрипт не падал.

**Дополнительное задание:** добавьте флаг `--kill`, отправляющий `SIGTERM` процессу с именем, указанным в командной строке, с помощью `subprocess.run(["kill", pid])`.

---

### Задание 3: резервная копия конфигурации перед изменением

Напишите функцию `safe_edit(config_path, new_content)`, которая:
1. Проверяет через `pathlib`, что файл существует, прежде чем изменять его
2. Создаёт резервную копию с временной меткой, запуская `cp` через subprocess (например, `nginx.conf.bak.20240115-143022`)
3. Записывает `new_content` в исходный файл с помощью `pathlib.write_text()`
4. Повторно читает файл и сравнивает содержимое, проверяя успешную запись
5. При ошибке проверки восстанавливает резервную копию через subprocess и вызывает исключение

**Ограничения:** сформируйте имя резервной копии в Python с помощью `datetime.now()` и операций `pathlib`. Для команды `cp` задайте `check=True`. Проверьте функцию на временном файле в `/tmp`.

---

### Задание 4: обновление нескольких Git-репозиториев с тайм-аутом и сводкой ошибок

Напишите скрипт, который:
1. Принимает путь к каталогу как аргумент командной строки
2. Находит все Git-репозитории внутри каталога (директории с `.git/`)
3. Выполняет `git pull --ff-only` в каждом репозитории с тайм-аутом 30 секунд
4. Собирает результаты: успех, ошибка (ненулевой код) или тайм-аут
5. Выводит итоговую таблицу с репозиторием и результатом

**Ограничения:** используйте `subprocess.run()` с `capture_output=True` и `timeout=30`. Отдельно обрабатывайте `CalledProcessError` и `TimeoutExpired`, обозначая их разными статусами. Не используйте `check=True`; проверяйте код возврата вручную. Выполняйте обновления последовательно, без потоков.

**Дополнительное задание:** измените скрипт, чтобы запускать все `git pull` параллельно через `subprocess.Popen`: сначала соберите дескрипторы всех процессов, затем дождитесь каждого.

---

### Быстрая проверка

1. Run a command with `subprocess.run` and capture its output.

   ```python
   import subprocess; r = subprocess.run(['echo', 'hello'], capture_output=True, text=True); print(r.stdout.strip())
   ```

   ```expected_output
   hello
   ```

Подсказка: `subprocess.run` может захватывать вывод команды вместо прямой печати в терминал.
Подсказка: задайте `capture_output=True` (или `stdout=subprocess.PIPE`), затем используйте атрибут `.stdout` и при необходимости вызовите `.decode()`.

2. Capture the exit code of a failing command.

   ```python
   import subprocess; r = subprocess.run(['bash', '-c', 'exit 42'], capture_output=True); print(r.returncode)
   ```

   ```expected_output
   42
   ```
Подсказка: модуль `subprocess` запускает команду и предоставляет её код возврата.
Подсказка: вызовите `subprocess.run()` и прочитайте атрибут `.returncode` объекта результата.
