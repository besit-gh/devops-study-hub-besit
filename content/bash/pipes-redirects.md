---
title: Конвейеры и перенаправление потоков
module: bash
duration_min: 10
difficulty: beginner
tags: [bash, pipes, redirects, stdin, stdout, stderr, tee]
exercises: 4
---

## Обзор

Конвейеры и перенаправления — основа композиционности Unix: небольшие специализированные инструменты можно объединять в более сложные цепочки. Вместо монолитных программ Unix предоставляет механизмы, позволяющие `grep`, `awk`, `sort`, `cut` и сотням других утилит обмениваться потоками данных. Для DevOps это не абстрактная теория: парсеры логов, скрипты развёртывания, health checks и шаги CI-пайплайнов зависят от правильной передачи данных между процессами. Ошибка может незаметно отбросить сообщения об ошибках, сломать конвейер или выдать вводящий в заблуждение результат.

В основе лежит файловый дескриптор — числовой идентификатор открытого ресурса, назначаемый ядром процессу. По умолчанию у каждого процесса есть три стандартных дескриптора: stdin, stdout и stderr. Перенаправление меняет назначение дескриптора, а конвейер соединяет stdout одного процесса со stdin другого через буфер ядра. Эти механизмы работают одинаково в локальном скрипте, удалённой SSH-команде и entrypoint контейнера, поэтому применимы во всём DevOps-стеке.

В DevOps конвейеры и перенаправления используются в скриптах CI/CD (сбор вывода сборки и отделение ошибок от обычных сообщений), обработке логов, автоматизации инфраструктуры (передаче конфигурации в `mysql`, `kubectl` или `terraform`) и процессах наблюдаемости. Владение этими приёмами значительно повышает эффективность любой работы с Bash.

---

## Основные понятия

### Файловые дескрипторы

Каждый процесс наследует от родительского процесса три открытых файловых дескриптора:

| FD | Имя | Назначение по умолчанию | Типичное применение |
|----|--------|---------------------|-------------|
| 0 | stdin | Клавиатура / терминал | Входные данные, запросы ввода |
| 1 | stdout | Терминал | Обычный вывод и результаты |
| 2 | stderr | Терминал | Ошибки, предупреждения и диагностика |

Файловые дескрипторы — это целые числа. Ядро связывает их с ресурсом: терминалом, файлом, каналом, сокетом или `/dev/null`. Перенаправление меняет эту связь. Команда `> file` сообщает ядру: «для этого процесса дескриптор 1 должен указывать на `file`, а не на терминал». Сам процесс продолжает вызывать `write(1, ...)` как обычно и не знает, что назначение изменилось.

**Зачем stderr отделён от stdout:** инструменты выводят результаты в stdout, а диагностику — в stderr, чтобы следующие команды получали чистые данные. Если бы `grep` помещал сообщение «совпадений нет» в поток результатов, конвейеры могли бы незаметно испортить данные. Соблюдайте это соглашение и в своих скриптах: для ошибок используйте `echo "error message" >&2`, а не обычный `echo`.

**Дескрипторы помимо 0/1/2:** Bash позволяет открывать и использовать произвольные FD (3, 4 и далее) через `exec`. Это полезно, когда скрипт одновременно пишет журнал в файл и читает ввод пользователя или поддерживает длительное соединение. Сначала это требуется редко, но знание механизма поможет разобраться в продвинутых скриптах с `>&3`.

---

### Перенаправление вывода

Операторы перенаправления указывают shell, куда направить файловый дескриптор до запуска команды.

```bash
# Overwrite stdout to a file (creates or truncates)
ls -la > files.txt

# Append stdout — never truncates
echo "$(date) deploy ok" >> deploy.log

# Redirect stderr only — stdout still goes to terminal
make 2> build_errors.txt

# Redirect stderr to wherever stdout currently points
ls /nonexistent 2>&1 | grep "No such"

# Redirect both stdout and stderr to the same file (two equivalent forms)
command > output.txt 2>&1   # POSIX-compatible — works in sh and bash
command &> output.txt       # bash shorthand — not available in /bin/sh

# Discard stdout (useful for commands run purely for side effects)
apt-get update > /dev/null

# Discard stderr (suppress error noise from expected failures)
rm -f /tmp/cache 2>/dev/null

# Discard everything (completely silent execution)
noisy_command &>/dev/null
```

**Порядок важен — это самая частая ошибка перенаправления:**

```bash
# WRONG — redirects stderr to terminal (current stdout), THEN moves stdout to file
# Result: stderr still goes to terminal, stdout goes to file
command 2>&1 > file.txt

# RIGHT — redirects stdout to file first, then stderr to wherever stdout now points
# Result: both stdout and stderr go to file
command > file.txt 2>&1
```

Shell обрабатывает перенаправления слева направо. `2>&1` означает «направить FD 2 туда, куда FD 1 указывает *в данный момент*». Если написать `2>&1` перед `> file`, FD 1 всё ещё указывает на терминал, поэтому stderr попадёт в терминал. В Bash-скриптах используйте `&>`, чтобы избежать этой путаницы.

**Обрезание файла при перенаправлении:** оператор `>` открывает файл и обнуляет его содержимое до запуска команды. Поэтому `sort file > file` уничтожит содержимое файла ещё до того, как `sort` его прочитает, и результатом станет пустой файл. Для изменения файла используйте временный файл или `sponge` из пакета `moreutils`.

```bash
# Safe in-place sort using a temp file
sort file.txt > file.txt.tmp && mv file.txt.tmp file.txt

# Or with sponge — buffers entire input before writing
sort file.txt | sponge file.txt
```

---

### Перенаправление ввода

Перенаправление ввода передаёт файл (или встроенный текст) в stdin команды.

```bash
# Feed a file as stdin — functionally equivalent to: cat schema.sql | mysql mydb
mysql mydb < schema.sql

# Here-string: pass a single string as stdin (no file needed)
base64 <<< "hello world"
wc -w <<< "count these words"

# Here-document: multiline inline input; delimiter must appear alone on a line
mysql mydb << SQL
  CREATE TABLE IF NOT EXISTS events (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    msg  TEXT NOT NULL,
    ts   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
SQL

# Indented here-doc (<<-): strips leading tabs (not spaces) for readable scripts
cat <<-MSG
	This line has a leading tab that will be stripped.
	So does this one.
MSG
```

**Правила кавычек в here-doc:** если разделитель не заключён в кавычки (`<< EOF`), внутри тела выполняются подстановка переменных и команд. Заключите разделитель в кавычки (`<< 'EOF'`), чтобы трактовать тело как буквальную строку. Это важно, если внутри есть символы `---
title: Конвейеры и перенаправление потоков
module: bash
duration_min: 10
difficulty: beginner
tags: [bash, pipes, redirects, stdin, stdout, stderr, tee]
exercises: 4
---

## Обзор

Конвейеры и перенаправления — основа композиционности Unix: небольшие специализированные инструменты можно объединять в более сложные цепочки. Вместо монолитных программ Unix предоставляет механизмы, позволяющие `grep`, `awk`, `sort`, `cut` и сотням других утилит обмениваться потоками данных. Для DevOps это не абстрактная теория: парсеры логов, скрипты развёртывания, health checks и шаги CI-пайплайнов зависят от правильной передачи данных между процессами. Ошибка может незаметно отбросить сообщения об ошибках, сломать конвейер или выдать вводящий в заблуждение результат.

В основе лежит файловый дескриптор — числовой идентификатор открытого ресурса, назначаемый ядром процессу. По умолчанию у каждого процесса есть три стандартных дескриптора: stdin, stdout и stderr. Перенаправление меняет назначение дескриптора, а конвейер соединяет stdout одного процесса со stdin другого через буфер ядра. Эти механизмы работают одинаково в локальном скрипте, удалённой SSH-команде и entrypoint контейнера, поэтому применимы во всём DevOps-стеке.

В DevOps конвейеры и перенаправления используются в скриптах CI/CD (сбор вывода сборки и отделение ошибок от обычных сообщений), обработке логов, автоматизации инфраструктуры (передаче конфигурации в `mysql`, `kubectl` или `terraform`) и процессах наблюдаемости. Владение этими приёмами значительно повышает эффективность любой работы с Bash.

---

## Основные понятия

### Файловые дескрипторы

Каждый процесс наследует от родительского процесса три открытых файловых дескриптора:

| FD | Имя | Назначение по умолчанию | Типичное применение |
|----|--------|---------------------|-------------|
| 0 | stdin | Клавиатура / терминал | Входные данные, запросы ввода |
| 1 | stdout | Терминал | Обычный вывод и результаты |
| 2 | stderr | Терминал | Ошибки, предупреждения и диагностика |

Файловые дескрипторы — это целые числа. Ядро связывает их с ресурсом: терминалом, файлом, каналом, сокетом или `/dev/null`. Перенаправление меняет эту связь. Команда `> file` сообщает ядру: «для этого процесса дескриптор 1 должен указывать на `file`, а не на терминал». Сам процесс продолжает вызывать `write(1, ...)` как обычно и не знает, что назначение изменилось.

**Зачем stderr отделён от stdout:** инструменты выводят результаты в stdout, а диагностику — в stderr, чтобы следующие команды получали чистые данные. Если бы `grep` помещал сообщение «совпадений нет» в поток результатов, конвейеры могли бы незаметно испортить данные. Соблюдайте это соглашение и в своих скриптах: для ошибок используйте `echo "error message" >&2`, а не обычный `echo`.

**Дескрипторы помимо 0/1/2:** Bash позволяет открывать и использовать произвольные FD (3, 4 и далее) через `exec`. Это полезно, когда скрипт одновременно пишет журнал в файл и читает ввод пользователя или поддерживает длительное соединение. Сначала это требуется редко, но знание механизма поможет разобраться в продвинутых скриптах с `>&3`.

---

### Перенаправление вывода

Операторы перенаправления указывают shell, куда направить файловый дескриптор до запуска команды.

```bash
# Overwrite stdout to a file (creates or truncates)
ls -la > files.txt

# Append stdout — never truncates
echo "$(date) deploy ok" >> deploy.log

# Redirect stderr only — stdout still goes to terminal
make 2> build_errors.txt

# Redirect stderr to wherever stdout currently points
ls /nonexistent 2>&1 | grep "No such"

# Redirect both stdout and stderr to the same file (two equivalent forms)
command > output.txt 2>&1   # POSIX-compatible — works in sh and bash
command &> output.txt       # bash shorthand — not available in /bin/sh

# Discard stdout (useful for commands run purely for side effects)
apt-get update > /dev/null

# Discard stderr (suppress error noise from expected failures)
rm -f /tmp/cache 2>/dev/null

# Discard everything (completely silent execution)
noisy_command &>/dev/null
```

**Порядок важен — это самая частая ошибка перенаправления:**

```bash
# WRONG — redirects stderr to terminal (current stdout), THEN moves stdout to file
# Result: stderr still goes to terminal, stdout goes to file
command 2>&1 > file.txt

# RIGHT — redirects stdout to file first, then stderr to wherever stdout now points
# Result: both stdout and stderr go to file
command > file.txt 2>&1
```

Shell обрабатывает перенаправления слева направо. `2>&1` означает «направить FD 2 туда, куда FD 1 указывает *в данный момент*». Если написать `2>&1` перед `> file`, FD 1 всё ещё указывает на терминал, поэтому stderr попадёт в терминал. В Bash-скриптах используйте `&>`, чтобы избежать этой путаницы.

**Обрезание файла при перенаправлении:** оператор `>` открывает файл и обнуляет его содержимое до запуска команды. Поэтому `sort file > file` уничтожит содержимое файла ещё до того, как `sort` его прочитает, и результатом станет пустой файл. Для изменения файла используйте временный файл или `sponge` из пакета `moreutils`.

```bash
# Safe in-place sort using a temp file
sort file.txt > file.txt.tmp && mv file.txt.tmp file.txt

# Or with sponge — buffers entire input before writing
sort file.txt | sponge file.txt
```

---

### Перенаправление ввода

Перенаправление ввода передаёт файл (или встроенный текст) в stdin команды.

```bash
# Feed a file as stdin — functionally equivalent to: cat schema.sql | mysql mydb
mysql mydb < schema.sql

# Here-string: pass a single string as stdin (no file needed)
base64 <<< "hello world"
wc -w <<< "count these words"

# Here-document: multiline inline input; delimiter must appear alone on a line
mysql mydb << SQL
  CREATE TABLE IF NOT EXISTS events (
    id   INT AUTO_INCREMENT PRIMARY KEY,
    msg  TEXT NOT NULL,
    ts   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
SQL

# Indented here-doc (<<-): strips leading tabs (not spaces) for readable scripts
cat <<-MSG
	This line has a leading tab that will be stripped.
	So does this one.
MSG
```

, которые нельзя раскрывать (SQL-запросы, YAML Kubernetes, конфигурации Terraform).

```bash
# Variables expand — $USER and $(hostname) are substituted at runtime
cat << EOF
Deploying as $USER on $(hostname) at $(date)
EOF

# Literal — $USER is printed as-is, no substitution occurs
cat << 'EOF'
No expansion: $USER $(hostname)
This is useful for generating scripts that contain their own variables.
EOF
```

**`< file` и `cat file |`:** перенаправление `< file` не запускает дополнительный процесс `cat`; это называют «бесполезным использованием cat» (UUOC). Это не катастрофа, но добавляет накладные расходы и считается плохим стилем. Если команда читает stdin, предпочитайте `command < file`.

---

### Конвейеры

Конвейер (`|`) соединяет stdout левой команды со stdin правой через буфер ядра. Оба процесса работают одновременно: левый записывает, правый читает, а ядро управляет потоком данных. Это принципиально отличается от сохранения вывода в переменную: конвейеры передают данные потоково и экономно используют память на больших входах.

```bash
# Count error lines in an application log
grep "ERROR" /var/log/app.log | wc -l

# Find the 10 largest directories under /var/log
du -sh /var/log/* | sort -rh | head -10

# Show listening TCP ports sorted numerically
ss -tlnp | awk '{print $4}' | sort -t: -k2 -n

# Top 20 IPs hitting an nginx server (common during incident triage)
awk '{print $1}' /var/log/nginx/access.log \
    | sort \
    | uniq -c \
    | sort -rn \
    | head -20

# Count HTTP status code distribution from nginx access log
awk '{print $9}' /var/log/nginx/access.log \
    | sort \
    | uniq -c \
    | sort -rn
```

**Коды завершения в конвейерах:** по умолчанию код конвейера равен коду *последней* команды. Если `grep` ничего не нашёл (код 1), но `wc -l` завершился успешно (код 0), весь конвейер вернёт 0 — ошибка предыдущей команды останется незаметной. Это опасно в скриптах с `set -e`.

```bash
# Default behavior — pipeline exit code = exit code of wc -l (0), grep failure ignored
grep "PATTERN" file.log | wc -l
echo $?   # prints 0 even if grep found nothing

# Fix: set pipefail — pipeline fails if ANY command in it fails
set -o pipefail

# Now the pipeline exits non-zero if grep exits non-zero
grep "PATTERN" file.log | wc -l
```

**Взаимодействие `set -o pipefail` с grep:** `grep` возвращает 1, если совпадений нет. Это не ошибка программы, но код ненулевой. Если одновременно включены `pipefail` и `set -e`, `grep` без совпадений в конвейере остановит скрипт. Обрабатывайте такой случай явно, если отсутствие совпадений допустимо:

```bash
# || true prevents a no-match from aborting the script
count=$(grep "PATTERN" file.log | wc -l || true)
echo "Found $count matches"
```

**Конвейеры и subshell:** каждая сторона конвейера выполняется в отдельном subshell. Переменные, установленные внутри этапа конвейера, не передаются родительской оболочке. Это одна из частых ошибок Bash-скриптов в production:

```bash
count=0
grep "ERROR" app.log | while read -r line; do
    count=$((count + 1))   # modifies the subshell's copy of count, not the parent's
done
echo "$count"  # always prints 0 — the subshell's changes are discarded

# Fix: use process substitution to avoid the subshell on the reading side
count=0
while read -r line; do
    count=$((count + 1))
done < <(grep "ERROR" app.log)
echo "$count"  # correctly prints the error count
```

---

### tee — запись в файл с продолжением конвейера

`tee` читает stdin и одновременно записывает данные в stdout и один или несколько файлов. Название происходит от Т-образного соединителя труб. Инструмент незаменим, когда нужно сохранить вывод в файл для последующего анализа и одновременно видеть его в реальном времени, либо разветвить конвейер.

```bash
# Show output on terminal AND save to file
./deploy.sh | tee deploy.log

# Append to file instead of overwriting (safe for ongoing logs)
./deploy.sh | tee -a deploy.log

# Write to multiple files simultaneously, suppress terminal output
command | tee file1.log file2.log > /dev/null

# Branch a pipeline: save raw API response AND continue processing it
curl -s https://api.example.com/metrics \
    | tee raw_metrics.json \
    | jq '.[] | select(.value > 100)'
```

**Захват stderr через tee:** `tee` получает только данные из stdin, связанного со stdout предыдущей команды. Чтобы захватить stderr, объедините его со stdout до конвейера:

```bash
# Without 2>&1: stderr bypasses tee and goes directly to terminal, not the log
./deploy.sh | tee -a deploy.log          # stderr missing from log

# With 2>&1: both streams are captured
./deploy.sh 2>&1 | tee -a deploy.log     # stderr and stdout both in log
```

**Использование tee для журналирования всего скрипта:** встроенная команда `exec` может перенаправить дескрипторы самого скрипта и направлять весь последующий вывод через `tee`, без добавления перенаправления к каждому `echo`:

```bash
#!/usr/bin/env bash
set -euo pipefail

LOGFILE="/var/log/myapp/deploy-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$(dirname "$LOGFILE")"

# From this point on, all stdout AND stderr go to terminal AND logfile
exec > >(tee -a "$LOGFILE") 2>&1

echo "Deployment started at $(date)"
# All subsequent output — including errors — is automatically logged
```

**Как работает `> >(tee ...)`:** `>(tee -a "$LOGFILE")` — это подстановка процесса: Bash создаёт фоновый процесс `tee` и возвращает путь вроде `/dev/fd/63`. Затем `exec > /dev/fd/63` направляет stdout скрипта в этот канал. Это стандартный способ добавить журналирование существующему скрипту без изменения каждого оператора вывода.

---

### Подстановка процесса

Подстановка процесса позволяет использовать вывод команды как файл. Bash создаёт именованный канал или дескриптор `/dev/fd/N` и передаёт его путь внешней команде. Это полезно, если команда принимает имена файлов, но не stdin, либо если нужно передать два потока данных команде, ожидающей два файла.

```bash
# Compare /etc/hosts across two servers without creating temp files
diff <(ssh web1 cat /etc/hosts) <(ssh web2 cat /etc/hosts)

# Find lines present in file2 but not file1 (both must be sorted)
comm -13 <(sort file1.txt) <(sort file2.txt)

# Compare current installed packages against a known-good baseline
diff <(dpkg --get-selections | sort) <(sort baseline_packages.txt)

# Merge two sorted error logs by timestamp
sort -m <(grep "ERROR" app1.log) <(grep "ERROR" app2.log)
```

**`<(...)`, `$(...)` и `|` — выбор подходящей формы:**

| Форма | Что создаёт | Когда использовать |
|------|-----------------|----------|
| `$(cmd)` | Строка (захваченный вывод) | Результат нужен как переменная или встроенный аргумент |
| `\| cmd` | Канал в stdin следующей команды | Обычный линейный конвейер с одним потоком данных |
| `<(cmd)` | Путь, похожий на файл, к потоку вывода команды | Команда ожидает имя файла или два входных потока |
| `>(cmd)` | Путь, похожий на файл, к входу команды | Команда ожидает имя файла для записи вывода |

**Подстановка процесса специфична для Bash.** В POSIX `sh` она не работает. Если нужна переносимость и shebang — `#!/bin/sh`, используйте временные файлы через `mktemp`. Если нужна подстановка процесса, укажите `#!/usr/bin/env bash`.

---

### Именованные каналы (FIFO)

FIFO (First In, First Out) — специальный файл, работающий как канал, но имеющий имя в файловой системе. Он позволяет взаимодействовать несвязанным процессам, даже запущенным в разное время, через общий путь. Анонимные каналы так работать не могут.

```bash
# Create a named pipe
mkfifo /tmp/logpipe

# Writer: send log data into the FIFO (runs in background)
tail -f /var/log/app.log > /tmp/logpipe &

# Reader: consume from the FIFO and filter
grep --line-buffered "ERROR" < /tmp/logpipe >> /tmp/errors.log

# Clean up when done
rm /tmp/logpipe
```

FIFO блокирует операции: писатель ждёт, пока читатель откроет другой конец, и наоборот. Поэтому FIFO удобно использовать для синхронизации producer/consumer.

**Когда использовать FIFO, а когда анонимный канал:**

| Сценарий | Решение |
|----------|-----|
| Линейный конвейер в одном скрипте | Анонимный канал (`\|`) |
| Обмен данными между несвязанными процессами | FIFO (`mkfifo`) |
| Команда ожидает имя файла, а не stdin | Подстановка процесса `<(...)` |
| Канал между сессиями | FIFO |

В большинстве DevOps-скриптов подстановка процесса заменяет FIFO. Используйте FIFO, когда нужно связать отдельные процессы, которые нельзя выразить одним Bash-конвейером.

---

### Комбинирование перенаправлений в скриптах

В реальных скриптах сочетаются разные способы перенаправления. Ниже приведены наиболее распространённые схемы, с которыми вы столкнётесь и которые будете использовать:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Pattern 1: Separate stdout and stderr to different files
./build.sh > build_output.txt 2> build_errors.txt

# Pattern 2: Capture stdout to variable; let stderr pass through to terminal
output=$(./check_health.sh)   # stderr still visible to operator; only stdout captured

# Pattern 3: Capture stdout, silently discard stderr
output=$(./noisy_command.sh 2>/dev/null)

# Pattern 4: Capture stdout to variable AND show it on terminal simultaneously
output=$(./deploy.sh | tee /dev/tty)   # /dev/tty always refers to the real terminal

# Pattern 5: Pipe clean stdout downstream, append errors to a log file
./lint.sh 2>> /var/log/lint_errors.log | jq .

# Pattern 6: Start background job with redirected streams, then wait on it
./long_job.sh > /tmp/job.out 2>&1 &
JOB_PID=$!
echo "Job running as PID $JOB_PID, output in /tmp/job.out"
wait "$JOB_PID" && echo "Job succeeded" || echo "Job failed with code $?"
```

**Всегда сочетайте `set -euo pipefail` с продуманной обработкой ошибок.** Комбинация `-e` (завершаться при ошибке), `-u` (завершаться при обращении к неопределённой переменной) и `-o pipefail` (считать ошибку в конвейере ошибкой всего конвейера) обнаруживает большинство незаметных сбоев production-скриптов.

---

## Примеры

### Пример 1. Разбор журналов доступа Nginx во время инцидента

**Сценарий:** сработало оповещение о росте количества ошибок 5xx. Нужно быстро определить по текущему журналу, какие эндпоинты и IP-адреса клиентов создают ошибки.

```bash
#!/usr/bin/env bash
# incident-triage.sh — run against a live or archived nginx access log
# Usage: ./incident-triage.sh /var/log/nginx/access.log

set -euo pipefail

LOGFILE="${1:?Usage: $0 <logfile>}"
REPORT="/tmp/incident-report-$(date +%Y%m%d-%H%M%S).txt"

echo "=== Incident Triage Report: $(date) ===" | tee "$REPORT"
echo "Log file: $LOGFILE" | tee -a "$REPORT"
echo "" | tee -a "$REPORT"

# Extract only 5xx responses (field 9 in combined log format is the status code)
echo "--- Top 5xx endpoints (method + URI) ---" | tee -a "$REPORT"
awk '$9 ~ /^5/ {print $6, $7}' "$LOGFILE" \
    | sort \
    | uniq -c \
    | sort -rn \
    | head -20 \
    | tee -a "$REPORT"

echo "" | tee -a "$REPORT"

# Find the client IPs generating the most 5xx errors
echo "--- Top client IPs generating 5xx errors ---" | tee -a "$REPORT"
awk '$9 ~ /^5/ {print $1}' "$LOGFILE" \
    | sort \
    | uniq -c \
    | sort -rn \
    | head -10 \
    | tee -a "$REPORT"

echo "" | tee -a "$REPORT"

# Count total 5xx vs total requests for a quick error rate
total=$(wc -l < "$LOGFILE")
errors=$(awk '$9 ~ /^5/' "$LOGFILE" | wc -l || true)
echo "--- Summary ---" | tee -a "$REPORT"
echo "Total requests : $total" | tee -a "$REPORT"
echo "5xx errors     : $errors" | tee -a "$REPORT"

echo ""
echo "Full report saved to: $REPORT"
```

**Verify it worked:**
```bash
chmod +x incident-triage.sh
./incident-triage.sh /var/log/nginx/access.log

# Check the report file was created and has content
wc -l /tmp/incident-report-*.txt
```

---

### Пример 2. Скрипт развёртывания с полным журналированием действий

**Сценарий:** скрипт развёртывания записывает весь stdout и stderr в файл с временной меткой, одновременно показывая вывод оператору в реальном времени. При сбое путь к журналу выводится для последующего разбора.

```bash
#!/usr/bin/env bash
# deploy.sh — deploys a Docker image and logs all output
set -euo pipefail

APP="${1:?Usage: $0 <app-name>}"
IMAGE_TAG="${2:?Usage: $0 <app-name> <image-tag>}"
LOGDIR="/var/log/deploys"
LOGFILE="${LOGDIR}/${APP}-$(date +%Y%m%d-%H%M%S).log"

mkdir -p "$LOGDIR"

# Wire all subsequent stdout and stderr to both terminal and logfile
exec > >(tee -a "$LOGFILE") 2>&1

echo "[$(date)] Starting deployment: $APP @ $IMAGE_TAG"

# Pull the image and capture any pull errors
echo "[$(date)] Pulling image..."
docker pull "$IMAGE_TAG"

# Rolling update — stderr from kubectl goes to log too
echo "[$(date)] Applying rollout..."
kubectl set image "deployment/$APP" "$APP=$IMAGE_TAG" --record

# Wait for rollout to complete (times out after 3 minutes)
echo "[$(date)] Waiting for rollout to complete..."
kubectl rollout status "deployment/$APP" --timeout=3m

echo "[$(date)] Deployment succeeded."
echo "[$(date)] Log saved to: $LOGFILE"
```

**Verify it worked:**
```bash
# Run the deployment
./deploy.sh my-api registry.example.com/my-api:v1.2.3

# Confirm the log file was created and contains both stdout and any errors
ls -lh /var/log/deploys/
tail -20 /var/log/deploys/my-api-*.log

# Simulate a failure and confirm it was captured in the log
kubectl set image deployment/nonexistent foo=bar:latest 2>&1 || true
grep "Error\|error\|failed" /var/log/deploys/my-api-*.log
```

---

### Пример 3. Передача динамической конфигурации работающему контейнеру

**Сценарий:** нужно применить миграцию SQL-схемы к контейнеру MySQL с помощью here-document, не создавая временный SQL-файл на диске. Тело схемы содержит переменные окружения, которые должны подставляться во время выполнения.

```bash
#!/usr/bin/env bash
# migrate.sh — applies a schema migration using a here-document
set -euo pipefail

DB_HOST="${DB_HOST:?DB_HOST not set}"
DB_NAME="${DB_NAME:?DB_NAME not set}"
DB_USER="${DB_USER:?DB_USER not set}"
DB_PASS="${DB_PASS:?DB_PASS not set}"
APP_ENV="${APP_ENV:-production}"

echo "Applying migration to $DB_NAME on $DB_HOST (env: $APP_ENV)..."

# The heredoc delimiter is unquoted, so $APP_ENV expands at script runtime.
# The resulting SQL is piped directly into mysql — no temp file needed.
mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" << SQL
  -- Migration applied by: $USER at $(date)
  -- Environment: $APP_ENV

  CREATE TABLE IF NOT EXISTS feature_flags (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    flag_name   VARCHAR(128) NOT NULL UNIQUE,
    enabled     TINYINT(1)   NOT NULL DEFAULT 0,
    environment VARCHAR(64)  NOT NULL DEFAULT '$APP_ENV',
    updated_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
  );

  INSERT IGNORE INTO feature_flags (flag_name, environment)
  VALUES ('new_dashboard', '$APP_ENV'),
         ('beta_api',      '$APP_ENV');
SQL

echo "Migration complete."
```

**Verify it worked:**
```bash
export DB_HOST=localhost DB_NAME=myapp DB_USER=root DB_PASS=secret APP_ENV=staging
./migrate.sh

# Confirm the table and rows exist
mysql -h localhost -u root -psecret myapp -e "SELECT * FROM feature_flags;"
```

---

### Пример 4. Сравнение фактического состояния Kubernetes с эталоном

**Сценарий:** во время проверки соответствия нужно убедиться, что набор работающих Pod в пространстве имён совпадает с проверенным эталоном, сохранённым на прошлой неделе, и вывести только различия.

```bash
#!/usr/bin/env bash
# k8s-drift-check.sh — detect pod image drift from a baseline snapshot
set -euo pipefail

NAMESPACE="${1:?Usage: $0 <namespace>}"
BASELINE="${2:?Usage: $0 <namespace> <baseline-file>}"

echo "Checking pod image drift in namespace: $NAMESPACE"
echo "Baseline file: $BASELINE"
echo ""

# Use process substitution to avoid temp files.
# <(...) gives diff two "files" to compare without writing to disk.
# Both sides are sorted so diff produces a stable comparison.
DIFF_OUTPUT=$(diff \
    <(kubectl get pods -n "$NAMESPACE" \
        -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}' \
        | sort) \
    <(sort "$BASELINE") \
    || true)   # diff exits 1 when files differ — don't abort with set -e

if [[ -z "$DIFF_OUTPUT" ]]; then
    echo "✓ No drift detected. Live state matches baseline."
else
    echo "✗ Drift detected:"
    echo ""
    # Lines starting with < are in live state but not baseline (new/changed)
    # Lines starting with > are in baseline but not live (removed)
    echo "$DIFF_OUTPUT" | grep "^<" | sed 's/^< /  LIVE (not in baseline): /'
    echo "$DIFF_OUTPUT" | grep "^>" | sed 's/^> /  BASELINE (not in live): /'
    exit 1
fi
```

**Verify it worked:**
```bash
# Capture current state as a baseline
kubectl get pods -n production \
    -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}' \
    | sort > baseline-production.txt

# Run the check against itself — should report no drift
./k8s-drift-check.sh production baseline-production.txt

# Manually edit the baseline to simulate drift, then re-run
echo "fake-pod	registry.example.com/old-image:v0.9" >> baseline-production.txt
./k8s-drift-check.sh production baseline-production.txt
```

---

## Практические задания

### Задание 1. Порядок перенаправлений и настройка файловых дескрипторов

**Цель:** усвоить порядок обработки перенаправлений слева направо и различие между `2>&1 > file` и `> file 2>&1`.

1. Создайте скрипт `fd-test.sh`, который намеренно пишет и в stdout, и в stderr:
   ```bash
   #!/usr/bin/env bash
   echo "this is stdout"
   echo "this is stderr" >&2
   ```
2. Запустите скрипт тремя способами и проследите, куда попадает каждый поток:
   ```bash
   ./fd-test.sh > out.txt 2>&1          # both to file
   ./fd-test.sh 2>&1 > out.txt          # only stdout to file; where does stderr go?
   ./fd-test.sh > stdout.txt 2> stderr.txt  # separated
   ```
3. После каждого запуска выполните `cat out.txt`, `cat stdout.txt`, `cat stderr.txt` и проверьте свои предположения. Одним предложением объясните, *почему* во втором варианте stderr направляется в терминал.
4. Измените скрипт, добавив `set -euo pipefail` и конвейер `grep`, который ничего не находит. Сравните, завершается ли скрипт с ненулевым кодом при включённом и выключенном `pipefail`.

---

### Задание 2. Конвейер анализа журналов

**Цель:** построить многоэтапный конвейер, который извлекает, преобразует и обобщает данные из журнала без временных файлов.

1. Создайте искусственный журнал доступа:
   ```bash
   for i in $(seq 1 200); do
       STATUS=$(shuf -n1 -e 200 200 200 404 500 502)
       IP="10.0.0.$(( RANDOM % 10 + 1 ))"
       echo "$IP - - [$(date '+%d/%b/%Y:%H:%M:%S +0000')] \"GET /path/$i HTTP/1.1\" $STATUS 512"
   done > access.log
   ```
2. Write a single pipeline (no intermediate files) that:
   - Extracts only 5xx status code lines
   - Counts how many times each unique IP appears in those lines
   - Sorts by frequency descending
   - Shows only the top 5
3. Extend the pipeline with `tee` so the raw 5xx lines are saved to `errors_raw.log` while the sorted summary still prints to the terminal.
4. Confirm `errors_raw.log` contains only 5xx lines: `awk '{print $9}' errors_raw.log | sort -u` should output only 5xx codes.

---

### Exercise 3: Here-Documents and Input Redirection

**Goal:** Practice heredoc quoting rules and understand when variable expansion should and should not occur.

1. Write a script that uses a heredoc to generate an nginx `location` block config. The script should accept `$APP_NAME` and `$UPSTREAM_PORT` as environment variables and expand them into the config body:
   ```
   location /api {
       proxy_pass http://127.0.0.1:8080;
       proxy_set_header Host $host;   # <- this $ must NOT be expanded
   }
   ```
   The challenge: `$APP_NAME` and `$UPSTREAM_PORT` must expand, but `$host` must appear literally. Solve this by escaping `$host` as `\$host` inside an unquoted heredoc — do not quote the entire delimiter.

2. Write a second version using a quoted delimiter (`<< 'EOF'`) and explain why that approach fails for this use case.

3. Use a here-string to test a one-liner: pass the string `"Error: disk full on /dev/sda1"` as stdin to `grep` and extract just the device path using only a pipe and `grep -oP` (or `sed`).

---

### Exercise 4: Subshell Variable Scope and Process Substitution

**Goal:** Directly experience the pipe subshell gotcha and fix it using process substitution.

1. Run this snippet and observe that the final `echo` prints `0`:
   ```bash
   total=0
   echo -e "apple\nbanana\napple\norange\napple" | while read -r fruit; do
       if [[ "$fruit" == "apple" ]]; then
           total=$((total + 1))
       fi
   done
   echo "Apples counted: $total"
   ```
2. Rewrite the loop to use process substitution (`< <(...)`) so `total` is correctly incremented in the parent shell.

---

### Быстрая проверка

3. Count the number of unique words in the string `"one two three two one"` using a pipeline. Print only the integer count. Hint: `echo "..." | tr ' ' '\n' | sort -u | wc -l | awk '{print $1}'`

```expected_output
3
```

hint: Think about how you can split the string into individual words, remove duplicates, and then count what remains using a pipeline.
hint: Use `tr ' ' '\n'` to put each word on its own line, then pipe through `sort -u` to deduplicate, and finally `wc -l` to count the lines.

4. Extract the second column from each row of this CSV using `awk -F,`. Pipe from: `printf 'alice,30,engineer\nbob,25,designer\ncarol,35,manager\n'`

```expected_output
30
25
35
```
hint: Think about how awk uses field separators to split each line into numbered columns you can reference.
hint: Use awk -F, '{print $2}' to tell awk the comma is the delimiter and to print the second field of each line.
