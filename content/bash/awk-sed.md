---
title: Обработка текста с awk и sed
module: bash
duration_min: 20
difficulty: intermediate
tags: [bash, awk, sed, text-processing, pipelines]
exercises: 4
---

## Обзор

`awk` и `sed` — основные инструменты обработки текста в Unix, для DevOps-инженера столь же важные, как умение писать циклы. Почти каждая система выдаёт текст: журналы, конфигурации, вывод команд, CSV-экспорты и фрагменты YAML. Умение преобразовать текст на месте — без отдельного скрипта Python, установки зависимостей и выхода из терминала — помогает разбирать production-инциденты за минуты.

`sed` (stream editor) применяет команды редактирования к текстовому потоку построчно. Он особенно удобен для замены, удаления и вставки: изменения значения в конфигурациях на множестве серверов, удаления комментариев перед конвейером или переключения флага с `true` на `false` в каталоге файлов. `awk` — полноценный язык программирования, замаскированный под обработчик полей. Он разбивает строки на столбцы, фильтрует их по значениям, суммирует данные и форматирует отчёты, поэтому подходит для структурированного текста: access-логов, вывода `ps`, CSV и других табличных результатов.

В DevOps эти инструменты постоянно встречаются в CI/CD-скриптах, слоях `RUN` Dockerfile, задачах Ansible, init-контейнерах Kubernetes и дашбордах мониторинга, построенных по журналам. Они доступны почти везде без установки и быстро обрабатывают файлы, на которых простой Python-скрипт мог бы работать медленно. В конвейерах они естественно сочетаются с `sort`, `uniq`, `grep` и `xargs`. Освоив их, вы сможете решать большинство задач обработки текста одной строкой вместо отдельного скрипта.

---

## Основные понятия

### sed — потоковый редактор

#### Как sed обрабатывает входные данные

`sed` читает входные данные построчно в **пространство шаблона (pattern space)**, применяет к нему команды и выводит результат (если вывод не отключён флагом `-n`). Эта модель объясняет некоторые неочевидные особенности: команды работают с уже изменённым пространством шаблона, поэтому две замены одной строки накапливают эффект.

```bash
echo "foo foo foo" | sed 's/foo/bar/; s/bar/baz/'
# Output: baz bar bar
# The first s// changes the first "foo" to "bar",
# then the second s// changes the first "bar" to "baz".
```

**Основные флаги:**

| Флаг | Значение |
|------|---------|
| `-n` | Отключить автоматический вывод; печатать только явно через `p` |
| `-e` | Добавить выражение (позволяет указывать несколько команд в строке) |
| `-i` | Изменить файл на месте |
| `-i.bak` | Изменить файл на месте, сохранив оригинал с суффиксом `.bak` |
| `-E` / `-r` | Использовать расширенные регулярные выражения (ERE), позволяющие писать `+`, `?`, `\|`, `()` без обратной косой черты |
| `-f script` | Читать команды из файла, а не из строки запуска |

**Различие macOS и Linux:** в macOS (BSD sed) флаг `-i` *требует* аргумент суффикса, даже пустой: `sed -i '' 's/a/b/' file`. В GNU sed на Linux достаточно `-i`. Для переносимых скриптов указывайте суффикс или определяйте ОС. Если в macOS опустить суффикс, появится неочевидная ошибка об отсутствующем входном файле.

#### Замена

Команду `s` вы будете использовать в большинстве случаев.

```bash
# Basic form: s/PATTERN/REPLACEMENT/FLAGS
sed 's/old/new/'            # first match per line
sed 's/old/new/g'           # all matches per line (global)
sed 's/old/new/2'           # second match only
sed 's/old/new/gi'          # global + case-insensitive

# Capture groups (with -E for extended regex)
sed -E 's/(ERROR|WARN)/[\1]/g' app.log   # wrap severity in brackets

# Alternate delimiters — use any char when pattern contains /
sed 's|/usr/local|/opt|g' paths.txt
sed 's@http://old.host@https://new.host@g' urls.txt

# In-place substitution — the most common DevOps use
sed -i.bak 's/debug: true/debug: false/' config.yaml
sed -i 's/localhost/db.prod.internal/g' app.conf
```

**Совет по обратным ссылкам:** символ `&` в строке замены обозначает весь найденный фрагмент. Это позволяет обойтись без группы захвата, если нужно лишь обернуть или дополнить совпадение.

```bash
echo "192.168.1.1" | sed 's/[0-9.]*/[&]/'
# Output: [192.168.1.1]

# Prefix every non-blank line with a timestamp placeholder
sed '/./s/^/2024-01-01 /' file.txt
```

#### Адресация — выбор нужных строк

Без адреса команда sed применяется ко всем строкам. Адреса позволяют ограничить область действия.

| Синтаксис адреса | Значение |
|----------------|---------|
| `5` | Только строка 5 |
| `3,7` | Строки с 3-й по 7-ю |
| `---
title: Обработка текста с awk и sed
module: bash
duration_min: 20
difficulty: intermediate
tags: [bash, awk, sed, text-processing, pipelines]
exercises: 4
---

## Обзор

`awk` и `sed` — основные инструменты обработки текста в Unix, для DevOps-инженера столь же важные, как умение писать циклы. Почти каждая система выдаёт текст: журналы, конфигурации, вывод команд, CSV-экспорты и фрагменты YAML. Умение преобразовать текст на месте — без отдельного скрипта Python, установки зависимостей и выхода из терминала — помогает разбирать production-инциденты за минуты.

`sed` (stream editor) применяет команды редактирования к текстовому потоку построчно. Он особенно удобен для замены, удаления и вставки: изменения значения в конфигурациях на множестве серверов, удаления комментариев перед конвейером или переключения флага с `true` на `false` в каталоге файлов. `awk` — полноценный язык программирования, замаскированный под обработчик полей. Он разбивает строки на столбцы, фильтрует их по значениям, суммирует данные и форматирует отчёты, поэтому подходит для структурированного текста: access-логов, вывода `ps`, CSV и других табличных результатов.

В DevOps эти инструменты постоянно встречаются в CI/CD-скриптах, слоях `RUN` Dockerfile, задачах Ansible, init-контейнерах Kubernetes и дашбордах мониторинга, построенных по журналам. Они доступны почти везде без установки и быстро обрабатывают файлы, на которых простой Python-скрипт мог бы работать медленно. В конвейерах они естественно сочетаются с `sort`, `uniq`, `grep` и `xargs`. Освоив их, вы сможете решать большинство задач обработки текста одной строкой вместо отдельного скрипта.

---

## Основные понятия

### sed — потоковый редактор

#### Как sed обрабатывает входные данные

`sed` читает входные данные построчно в **пространство шаблона (pattern space)**, применяет к нему команды и выводит результат (если вывод не отключён флагом `-n`). Эта модель объясняет некоторые неочевидные особенности: команды работают с уже изменённым пространством шаблона, поэтому две замены одной строки накапливают эффект.

```bash
echo "foo foo foo" | sed 's/foo/bar/; s/bar/baz/'
# Output: baz bar bar
# The first s// changes the first "foo" to "bar",
# then the second s// changes the first "bar" to "baz".
```

**Основные флаги:**

| Флаг | Значение |
|------|---------|
| `-n` | Отключить автоматический вывод; печатать только явно через `p` |
| `-e` | Добавить выражение (позволяет указывать несколько команд в строке) |
| `-i` | Изменить файл на месте |
| `-i.bak` | Изменить файл на месте, сохранив оригинал с суффиксом `.bak` |
| `-E` / `-r` | Использовать расширенные регулярные выражения (ERE), позволяющие писать `+`, `?`, `\|`, `()` без обратной косой черты |
| `-f script` | Читать команды из файла, а не из строки запуска |

**Различие macOS и Linux:** в macOS (BSD sed) флаг `-i` *требует* аргумент суффикса, даже пустой: `sed -i '' 's/a/b/' file`. В GNU sed на Linux достаточно `-i`. Для переносимых скриптов указывайте суффикс или определяйте ОС. Если в macOS опустить суффикс, появится неочевидная ошибка об отсутствующем входном файле.

#### Замена

Команду `s` вы будете использовать в большинстве случаев.

```bash
# Basic form: s/PATTERN/REPLACEMENT/FLAGS
sed 's/old/new/'            # first match per line
sed 's/old/new/g'           # all matches per line (global)
sed 's/old/new/2'           # second match only
sed 's/old/new/gi'          # global + case-insensitive

# Capture groups (with -E for extended regex)
sed -E 's/(ERROR|WARN)/[\1]/g' app.log   # wrap severity in brackets

# Alternate delimiters — use any char when pattern contains /
sed 's|/usr/local|/opt|g' paths.txt
sed 's@http://old.host@https://new.host@g' urls.txt

# In-place substitution — the most common DevOps use
sed -i.bak 's/debug: true/debug: false/' config.yaml
sed -i 's/localhost/db.prod.internal/g' app.conf
```

**Совет по обратным ссылкам:** символ `&` в строке замены обозначает весь найденный фрагмент. Это позволяет обойтись без группы захвата, если нужно лишь обернуть или дополнить совпадение.

```bash
echo "192.168.1.1" | sed 's/[0-9.]*/[&]/'
# Output: [192.168.1.1]

# Prefix every non-blank line with a timestamp placeholder
sed '/./s/^/2024-01-01 /' file.txt
```

#### Адресация — выбор нужных строк

Без адреса команда sed применяется ко всем строкам. Адреса позволяют ограничить область действия.

| Синтаксис адреса | Значение |
|----------------|---------|
| `5` | Только строка 5 |
| `3,7` | Строки с 3-й по 7-ю |
 | Последняя строка |
| `/pattern/` | Строки, соответствующие регулярному выражению |
| `/start/,/end/` | От первой строки с `start` до следующей строки с `end` |
| `0,/pattern/` (GNU) | От строки 0 до первого совпадения; учитывает строку 1, если она подходит |
| `~N` (GNU) | Каждая N-я строка: `0~2` — чётные строки, `1~2` — нечётные |
| `addr!` | Отрицание: применить к строкам, не соответствующим адресу |

```bash
sed '3s/old/new/'             # substitution on line 3 only
sed '3,7s/old/new/'           # lines 3–7
sed '$d'                      # delete last line
sed '/ERROR/s/$/  <--/g'      # append marker to ERROR lines
sed '/^#/d'                   # delete comment lines
sed '/^$/d'                   # delete blank lines
sed '/START/,/END/d'          # delete blocks between markers (inclusive)
sed '/pattern/!d'             # delete lines that do NOT match pattern
```

**Особенность диапазонов:** `/START/,/END/` выбирает до *следующего* совпадения END после каждого START. Если END не встречается, диапазон продолжается до конца файла. Это удобно для удаления блоков конфигурации, но опечатка в END может незаметно удалить лишнее. Перед коммитом всегда проверяйте diff.

#### Удаление, вывод, вставка и добавление

```bash
# Delete
sed '5d'                      # delete line 5
sed '/pattern/d'              # delete matching lines
sed '/^#/d; /^$/d'            # strip comments and blank lines in one pass

# Print (use -n to suppress default output — otherwise each line prints twice)
sed -n '10,20p' file.txt      # print lines 10–20
sed -n '/ERROR/p' app.log     # equivalent to: grep ERROR app.log
sed -n '/START/,/END/p' file  # print a named block

# Insert before / append after a line
sed '2i\--- inserted line ---'       # insert before line 2
sed '/pattern/a\  new_key: value'    # append YAML key after a matching line
sed '/\[section\]/a\key=value' cfg   # add key under a config section header

# Change a line entirely
sed '/^version:/c\version: "2.0"' config.yaml
```

**`-n` вместе с `p` — хорошая альтернатива grep**, если нужны номера строк или контекст без установки GNU grep в минимальный образ контейнера: `sed -n '/ERROR/{=;p}' app.log` выводит номер строки (`=`), а затем саму строку (`p`).

#### Несколько выражений и файлы скриптов

```bash
# Multiple -e flags — readable for 2–3 commands
sed -e 's/foo/bar/' -e '/^$/d' -e 's/baz/qux/' file.txt

# Semicolon-separated (same effect, more compact)
sed 's/foo/bar/; /^$/d; s/baz/qux/' file.txt

# Script file — the right approach for production automation
cat > fix.sed <<'EOF'
s/debug: true/debug: false/
s/log_level: info/log_level: warn/
/^#.*TODO/d
EOF
sed -i.bak -f fix.sed config.yaml
```

Файлы скриптов делают сложные изменения проверяемыми и версионируемыми. Добавляйте `fix.sed` в репозиторий вместе с вызывающим его playbook Ansible или CI-скриптом.

---

### awk — обработчик полей

#### Модель выполнения

Программы `awk` состоят из правил `pattern { action }`. Для каждой входной строки:
1. Строка разбивается на поля `$1`, `$2`, …, `$NF` с помощью `FS`.
2. Правила проверяются по порядку: если шаблон совпал (или отсутствует), выполняется действие.
3. Блоки `BEGIN` и `END` выполняются один раз до и после обработки всех данных.

```
awk 'BEGIN { setup } pattern { action } END { teardown }' file
```

Это принципиально отличается от sed: awk сохраняет состояние между строками, умеет выполнять арифметику, поддерживает массивы и полноценное управление потоком (`if/else`, `for`, `while`). Его можно представить как движок запросов к базе данных, где строка — запись, а поле — столбец.

#### Справочник встроенных переменных

| Переменная | По умолчанию | Значение |
|----------|---------|---------|
| `$0` | — | Вся текущая строка |
| `$1`…`$NF` | — | Отдельные поля |
| `NF` | — | Число полей в текущей строке |
| `NR` | — | Номер текущей записи (строки) во всех файлах |
| `FNR` | — | Номер записи внутри текущего файла |
| `FS` | `" "` | Разделитель входных полей |
| `OFS` | `" "` | Разделитель выходных полей |
| `RS` | `"\n"` | Разделитель входных записей |
| `ORS` | `"\n"` | Разделитель выходных записей |
| `FILENAME` | — | Имя текущего входного файла |

**Особое поведение `FS=" "`:** пробел по умолчанию означает «разбивать по любой последовательности пробельных символов и удалять пробелы по краям». Это отличается от явно заданного через `-v` `FS="\t"` или `FS=" "`. Благодаря этому `awk '{print $1}'` работает с выводом `ps`, `df` и `ls -l` без дополнительных флагов. Для TSV, где поле может быть пустым, явно задавайте `FS="\t"`.

**Изменение полей:** присваивание `$1` или другого поля приводит к пересборке `$0` с использованием `OFS` в качестве разделителя. Чтобы изменить формат строки, задайте `OFS`, измените поле и выведите `$0`.

```bash
# Change the 3rd field and reprint the whole line
awk 'BEGIN{OFS=":"} {$3="REDACTED"; print $0}' /etc/passwd
```

#### Разделители полей и форматирование вывода

```bash
# Set FS at invocation
awk -F: '{print $1, $7}' /etc/passwd          # colon-delimited
awk -F'\t' '{print $2, $4}' report.tsv        # tab-delimited
awk -F'[,;]' '{print $1}' mixed.csv           # regex separator: comma or semicolon

# OFS controls what print $1,$2 puts between fields
# Note: comma in print → OFS; space in print → literal space
awk 'BEGIN {OFS=","} {print $1,$3,$5}' data.txt     # produces CSV
awk 'BEGIN {OFS="\t"} {print $2,$4}' data.txt       # produces TSV

# printf for fixed-width, aligned output
awk '{printf "%-30s %8.2f MB\n", $1, $2/1024}' sizes.txt

# printf format reference
# %-30s  left-aligned string, 30 chars wide
# %8.2f  right-aligned float, 8 chars wide, 2 decimal places
# %05d   zero-padded integer
```

#### Шаблоны: фильтрация строк

```bash
# Regex pattern
awk '/ERROR/'  app.log                    # print lines matching ERROR
awk '!/DEBUG/' app.log                    # print lines NOT matching DEBUG
awk '$0 ~ /pattern/'  file               # explicit match operator (same as /pattern/)
awk '$3 !~ /SKIP/'    file               # field 3 does not match regex

# Field comparison
awk '$9 >= 500'           access.log      # HTTP 5xx
awk '$3 == "CRITICAL"'    syslog          # exact field match
awk '$5 > 1000'           metrics.txt     # numeric comparison
awk 'NR > 1'              file.txt        # skip header line
awk 'NR==1 || $5 > 80'    df_output.txt  # header + high-usage rows

# Compound conditions
awk '$9 >= 500 && $9 < 600' access.log   # 5xx only
awk '/ERROR/ || /FATAL/'    app.log       # either pattern
awk 'NR>=10 && NR<=20'      file.txt     # line range — sometimes cleaner than sed

# Range pattern (stateful — no braces needed between start and end)
awk '/BEGIN_BLOCK/,/END_BLOCK/' file.txt
```

#### Агрегация и счётчики

```bash
# Sum a column
awk '{sum += $5} END {print "Total:", sum}' data.txt

# Count occurrences
awk '/ERROR/ {count++} END {print "Errors:", count+0}' app.log

# Frequency map using an associative array
awk '{freq[$1]++} END {for (ip in freq) print freq[ip], ip}' access.log \
  | sort -rn | head -10

# Average
awk '{sum += $3; count++} END {printf "Average: %.2f\n", sum/count}' metrics.txt

# Min/max
awk 'NR==1 {min=max=$1} {if($1<min)min=$1; if($1>max)max=$1}
     END {print "min:", min, "max:", max}' values.txt

# Multiple counters — HTTP status breakdown
awk '
  {total++}
  $9 ~ /^2/ {ok++}
  $9 ~ /^4/ {client_err++}
  $9 ~ /^5/ {server_err++}
  END {
    printf "Total:  %d\n2xx:    %d\n4xx:    %d\n5xx:    %d\n",
           total, ok+0, client_err+0, server_err+0
  }
' access.log
```

**Особенность неинициализированных переменных:** в awk числовые переменные без начального значения равны `0`, а строковые — `""`. Выражение `count+0` принудительно задаёт числовой контекст, поэтому при отсутствии совпадений выводится `0`, а не пустая строка. Это особенно важно в блоках `END`, где счётчик мог ни разу не увеличиться.

#### Массивы

Массивы awk ассоциативные (хеш-таблицы): ключами могут быть строки или числа, а сам элемент создаётся при первом присваивании.

```bash
# Build a map of status codes to counts
awk '{codes[$9]++} END {
    for (code in codes)
        printf "%s: %d\n", code, codes[code]
}' access.log | sort

# Check if a key exists before using it
awk '{
    if ($1 in seen) { print "duplicate:", $1 }
    else seen[$1] = 1
}' ids.txt

# Delete a key
awk '{delete seen[$1]}' file.txt

# Multi-dimensional simulation with SUBSEP
# awk does not support true multi-dim arrays; use SUBSEP as a compound key
awk '{count[$1 SUBSEP $9]++}
     END {
       for (key in count) {
         split(key, parts, SUBSEP)
         printf "IP: %-15s  Status: %s  Count: %d\n",
                parts[1], parts[2], count[key]
       }
     }' access.log
```

**Порядок `for (key in array)` не определён.** awk не гарантирует порядок обхода ключей массива. Если порядок вывода важен, передавайте результат в `sort`.

#### Обработка нескольких файлов: FNR и NR

```bash
# NR: global line number across all input files
# FNR: line number within the current file

# Print filename header at start of each file
awk 'FNR==1 {print "--- File:", FILENAME} {print NR, $0}' file1.txt file2.txt

# Merge CSVs: print header from first file, skip headers from rest
awk 'FNR==1 && NR==1 {print; next} FNR==1 {next} {print}' *.csv

# Cross-reference two files: load file1 into array, look up in file2
awk 'NR==FNR {allowed[$1]=1; next}   # runs for first file only
     $1 in allowed {print}' \         # runs for second file
     whitelist.txt access.log
```

Идиома `NR==FNR` — один из самых полезных шаблонов awk в DevOps: она позволяет объединять два файла без `sort` и базы данных.

---

### Совместное использование sed и awk в конвейерах

Главная сила — в совместном использовании. Применяйте каждый инструмент для его лучшей задачи:

- **sed** для построчного редактирования: удаление лишнего, нормализация разделителей, исправление проблем кодировки
- **awk** для анализа полей: извлечение столбцов, агрегация и отчёты
- **sort / uniq** между ними для сортировки и удаления дубликатов

```bash
# Pattern: normalize → extract → aggregate → sort → limit
sed '/^#/d; /^$/d' access.log \          # strip comments and blanks
  | awk '{print $1, $9}' \              # extract IP and status code
  | sort \                              # sort for uniq
  | uniq -c \                           # count unique pairs
  | sort -rn \                          # rank by frequency
  | head -20                            # top 20
```

**Как выбрать инструмент для конвейера:**

| Задача | Лучший инструмент |
|------|-----------|
| Найти строки по шаблону | `grep` |
| Изменить или заменить текст в строках | `sed` |
| Извлечь и переформатировать поля | `awk` |
| Посчитать вхождения | `awk` или `sort \| uniq -c` |
| Отсортировать вывод | `sort` |
| Удалить дубликаты | `sort -u` или `uniq` |
| Выполнить агрегацию по строкам | `awk` |
| Структурированные форматы (JSON, XML) | `jq`, `xmllint` |

**Производительность:** для файлов размером до нескольких сотен МБ awk достаточно быстр, и оптимизация обычно не нужна. Для журналов размером в несколько ГБ сначала сократите объём данных через `grep`, а затем передавайте результат в awk. Для простого поиска шаблона `grep` с алгоритмом Boyer–Moore часто в 5–10 раз быстрее регулярного выражения awk.

---

### Безопасное редактирование файлов на месте

Редактирование на месте с помощью `sed -i` изменяет исходный файл напрямую. Production-скрипты должны корректно обрабатывать ошибки.

```bash
# Always create a backup on first use in a script
sed -i.bak 's/old/new/g' critical.conf

# Verify before applying (dry run: diff stdout vs original)
sed 's/old/new/g' critical.conf | diff critical.conf -

# Abort if diff finds unexpected changes
expected_changes=1
actual_changes=$(sed 's/old/new/g' critical.conf | diff critical.conf - | grep '^[<>]' | wc -l)
[[ "$actual_changes" -eq "$expected_changes" ]] || { echo "Unexpected diff"; exit 1; }

# Use a temp file for multi-step edits — safer than chained -i
tmp=$(mktemp /tmp/config.XXXXXX)
sed 's/foo/bar/g' original.conf \
  | awk '/\[section\]/{found=1} found && /^key=/{$0="key=newvalue"; found=0} {print}' \
  > "$tmp"
mv "$tmp" original.conf  # atomic on same filesystem
```

**Атомарность `mv`:** в пределах одной файловой системы `mv` выполняет один системный вызов `rename(2)`, который атомарен. Если конвейер аварийно завершится посередине, целевой файл не останется частично записанным. Для критичных конфигураций безопаснее сначала записать временный файл, а затем заменить им целевой, чем редактировать исходник на месте.

**Проверьте, что изменения применены:**
```bash
grep -c 'new_value' critical.conf || { echo "Edit failed to apply"; exit 1; }
```

---

## Примеры

### Пример 1. Анализ журнала доступа nginx с помощью скрипта

Разберите стандартный формат combined журнала nginx и сформируйте сводку для эксплуатации.

```bash
#!/usr/bin/env bash
# analyze_access_log.sh — nginx access log report
# Usage: ./analyze_access_log.sh /var/log/nginx/access.log

LOG="${1:-/var/log/nginx/access.log}"

if [[ ! -f "$LOG" ]]; then
  echo "ERROR: Log file not found: $LOG" >&2
  exit 1
fi

echo "========================================"
echo " nginx Access Log Report"
echo " File: $LOG"
echo " Lines: $(wc -l < "$LOG")"
echo "========================================"

echo ""
echo "--- HTTP Status Code Distribution ---"
# Field 9 in nginx combined log is the status code
awk '{codes[$9]++}
     END {
       for (c in codes)
         printf "%5d  %s\n", codes[c], c
     }' "$LOG" | sort -rn

echo ""
echo "--- Top 10 Client IPs ---"
# Field 1 is the client IP
awk '{ips[$1]++}
     END {for (ip in ips) print ips[ip], ip}' "$LOG" \
  | sort -rn | head -10 \
  | awk '{printf "%5d requests  %s\n", $1, $2}'

echo ""
echo "--- Top 10 Requested URLs ---"
# Field 7 is the request path (strip query string with sed)
awk '{print $7}' "$LOG" \
  | sed 's/?.*$//' \          # strip query strings for grouping
  | sort | uniq -c \
  | sort -rn | head -10 \
  | awk '{printf "%5d  %s\n", $1, $2}'

echo ""
echo "--- 5xx Errors (last 20) ---"
# Show recent server errors with timestamp and URL
awk '$9 >= 500 && $9 < 600 {print $4, $7, $9}' "$LOG" \
  | sed 's/\[//' \            # strip the [ from timestamp field
  | tail -20

echo ""
echo "--- Traffic by Hour ---"
# Field 4 looks like: [01/Jan/2024:14:32:01
awk '{
    # Extract hour from timestamp field: [DD/Mon/YYYY:HH
    match($4, /:[0-9]{2}:/, arr)
    hour = substr($4, RSTART+1, 2)
    hourly[hour]++
}
END {
    for (h in hourly)
        printf "%s:00  %d requests\n", h, hourly[h]
}' "$LOG" | sort
```

**Verify it works:**
```bash
chmod +x analyze_access_log.sh
# Use a sample log if you don't have nginx running:
curl -s https://raw.githubusercontent.com/elastic/examples/master/Common%20Data%20Formats/nginx_logs/nginx_logs \
  -o sample_nginx.log
./analyze_access_log.sh sample_nginx.log
```

---

### Пример 2. Изменение конфигурационных файлов на группе серверов

Типичная задача CI/CD: перед развёртыванием изменить строку версии и переключить feature flag в конфигурационных файлах.

```bash
#!/usr/bin/env bash
# patch_configs.sh — update app configs for a new release
# Usage: ./patch_configs.sh <new_version> <config_dir>

NEW_VERSION="${1:?Usage: $0 <version> <config_dir>}"
CONFIG_DIR="${2:?Usage: $0 <version> <config_dir>}"

# Build a sed script — easier to maintain than multiple -e flags
PATCH_SCRIPT=$(mktemp /tmp/patch.XXXXXX.sed)
cat > "$PATCH_SCRIPT" <<EOF
# Update version string
s/^app_version=.*/app_version=${NEW_VERSION}/

# Enable maintenance mode during deploy
s/^maintenance_mode=false/maintenance_mode=true/

# Rotate to new log path
s|log_path=/var/log/app/old|log_path=/var/log/app/current|g

# Remove deprecated keys (lines starting with legacy_)
/^legacy_/d
EOF

echo "Applying patch to configs in: $CONFIG_DIR"
patched=0
failed=0

for cfg in "$CONFIG_DIR"/*.conf; do
  [[ -f "$cfg" ]] || continue

  # Dry run: count changed lines
  changes=$(sed -f "$PATCH_SCRIPT" "$cfg" | diff "$cfg" - | grep -c '^[<>]')

  if [[ "$changes" -gt 0 ]]; then
    sed -i.bak -f "$PATCH_SCRIPT" "$cfg"
    echo "  PATCHED ($changes changes): $cfg"
    ((patched++))
  else
    echo "  SKIPPED (no changes): $cfg"
  fi
done

rm -f "$PATCH_SCRIPT"
echo ""
echo "Done. Patched: $patched configs."

# Verify: no file should still contain legacy_ keys
legacy_count=$(grep -rl '^legacy_' "$CONFIG_DIR"/*.conf 2>/dev/null | wc -l)
if [[ "$legacy_count" -gt 0 ]]; then
  echo "WARNING: $legacy_count files still contain legacy_ keys" >&2
  exit 1
fi
```

---

### Пример 3. Отчёт о ресурсах Pod Kubernetes

Извлеките запросы CPU и памяти из вывода `kubectl` и сформируйте отформатированную сводку.

```bash
#!/usr/bin/env bash
# pod_resources.sh — summarize resource requests by namespace
# Requires: kubectl configured with cluster access

NAMESPACE="${1:---all-namespaces}"
KUBECTL_ARGS=("--all-namespaces")
[[ "$NAMESPACE" != "--all-namespaces" ]] && KUBECTL_ARGS=("-n" "$NAMESPACE")

# kubectl top pods output format:
# NAMESPACE   NAME                          CPU(cores)   MEMORY(bytes)
# default     nginx-7d6b84c9f5-xk9p2        2m           18Mi

kubectl top pods "${KUBECTL_ARGS[@]}" 2>/dev/null \
  | awk '
    NR == 1 { next }   # skip header

    {
      ns   = $1
      name = $2
      cpu  = $3
      mem  = $4

      # Strip units: "42m" → 42 (millicores), "128Mi" → 128
      sub(/m$/, "", cpu)
      sub(/Mi$/, "", mem)

      # Accumulate per-namespace
      ns_cpu[ns]  += cpu
      ns_mem[ns]  += mem
      ns_pods[ns]++

      total_cpu += cpu
      total_mem += mem
      total_pods++
    }

    END {
      printf "%-20s  %6s  %8s  %8s\n", "NAMESPACE", "PODS", "CPU(m)", "MEM(Mi)"
      printf "%-20s  %6s  %8s  %8s\n", "---", "---", "---", "---"
      for (ns in ns_pods)
        printf "%-20s  %6d  %8d  %8d\n", ns, ns_pods[ns], ns_cpu[ns], ns_mem[ns]
      printf "%-20s  %6d  %8d  %8d\n", "TOTAL", total_pods, total_cpu, total_mem
    }
  ' | sort -k1

# Also flag any pod using more than 500m CPU
echo ""
echo "--- High CPU Pods (>500m) ---"
kubectl top pods "${KUBECTL_ARGS[@]}" 2>/dev/null \
  | awk 'NR>1 { cpu=$3; sub(/m$/,"",cpu); if(cpu+0 > 500) print $1, $2, $3, $4 }' \
  | awk '{printf "  %-20s %-40s CPU: %s  MEM: %s\n", $1, $2, $3, $4}'
```

---

### Пример 4. Обнаружение аномалий в журналах с помощью awk

Обнаруживайте всплески ошибок в скользящем временном окне — этот приём используют в скриптах оповещения, пока полноценный стек мониторинга ещё не развёрнут.

```bash
#!/usr/bin/env bash
# error_burst.sh — alert if error rate exceeds threshold in any 60-second window
# Usage: ./error_burst.sh /var/log/app/app.log
# Log format: 2024-01-15T14:32:01 ERROR [module] message

LOG="${1:-/var/log/app/app.log}"
THRESHOLD=10   # errors per 60-second window
WINDOW=60      # seconds

awk -v threshold="$THRESHOLD" -v window="$WINDOW" '
# Parse ISO 8601 timestamp into epoch seconds (GNU awk only — uses mktime)
function parse_ts(ts,    parts, t) {
    # ts format: 2024-01-15T14:32:01
    gsub(/[-T:]/, " ", ts)
    split(ts, parts, " ")
    t = mktime(parts[1] " " parts[2] " " parts[3] " " \
               parts[4] " " parts[5] " " parts[6])
    return t
}

/ERROR/ {
    epoch = parse_ts($1)
    # Slide a window: keep only errors within last `window` seconds
    times[NR] = epoch
    error_count++

    # Expire old entries outside the window
    for (i in times) {
        if (epoch - times[i] > window) {
            delete times[i]
            error_count--
        }
    }

    # Check threshold
    if (error_count >= threshold) {
        printf "ALERT: %d errors in %d seconds ending at %s (line %d)\n",
               error_count, window, $1, NR
        # Reset to avoid repeated alerts for the same burst
        delete times
        error_count = 0
    }
}
' "$LOG"
```

---

## Практические задания

### Exercise 1: Parsing df Output

Команда `df -h` выводит использование файловых систем в удобном для чтения виде. В выводе есть строка заголовка и столбцы: файловая система, размер, занято, доступно, процент использования и точка монтирования.

**Задача:** напишите одну команду `awk`, которая:
1. Пропускает строку заголовка.
2. Выводит только файловые системы с использованием более 80%.
3. Формирует таблицу `MOUNT_POINT  USE%  AVAILABLE` с помощью `printf`.
4. Добавляет завершающий блок `END`, выводящий количество файловых систем выше порога.

Поле процента использования содержит символ `%`: перед числовым сравнением удалите его с помощью `sub(/%/, "", $5)` или среза строки.

**Проверка:** выполните `df -h | ваша_команда` и убедитесь, что отображаются только точки монтирования с высоким использованием. На чистой системе смоделируйте данные: `echo -e "Filesystem Size Used Avail Use% Mount\n/dev/sda1 20G 17G 2G 86% /\ntmpfs 2G 100M 1.9G 5% /tmp" | ваша_команда`.

---

### Задание 2. Нормализация файла конфигурации

У вас есть устаревший файл конфигурации с непоследовательным форматированием: вокруг `=` где-то стоят пробелы, где-то табуляции, комментарии начинаются с `#` или `;`, а между строками встречаются пустые строки.

**Setup:**
```bash
cat > legacy.conf <<'EOF'
; old comment style
# new comment style

  host = localhost
port=5432
  db_name   =   myapp
  ssl = true

; deprecated
old_key = ignored
EOF
```

**Задача:** с помощью `sed` (не `awk`) подготовьте нормализованную версию, которая:
1. Удаляет все строки комментариев (начинающиеся с `;` или `#`, возможно после пробелов).
2. Удаляет пустые строки.
3. Удаляет пробельные символы вокруг `=` (например, превращает `  host = localhost` в `host=localhost`).
4. Записывает результат в `normalized.conf` через временный файл и `mv` (не используя `-i`).

**Verify:** `cat normalized.conf` should produce exactly:
```
host=localhost
port=5432
db_name=myapp
ssl=true
old_key=ignored
```

---

### Exercise 3: Log Join Across Two Files

You have two files: `requests.log` (request ID and URL) and `errors.log` (request ID and error message). You need to find which URLs produced errors.

**Setup:**
```bash
cat > requests.log <<'EOF'
req001 /api/users
req002 /api/orders
req003 /healthz
req004 /api/users/42
req005 /api/payments
EOF

cat > errors.log <<'EOF'
req002 "database connection timeout"
req005 "payment gateway unreachable"
req004 "user not found"
EOF
```

**Task:** Using a single `awk` command with both files as input, print lines in the format:
```
req002  /api/orders  "database connection timeout"
```
Only request IDs that appear in `errors.log` should be printed. Use the `NR==FNR` idiom to load one file into an array, then look up from the second.

**Stretch goal:** Sort the output by request ID and add a count at the end: `Total errors: N`.

---

### Exercise 4: Rolling Metric Summarizer

You have a metrics dump where each line contains a Unix timestamp and a response time in milliseconds:

```bash
# Generate sample data
awk 'BEGIN {
    srand(42)
    ts = 1700000000
    for (i = 0; i < 200; i++) {
        ts += int(rand() * 10) + 1
        ms = int(rand() * 500) + 10
        print ts, ms
    }
}' > metrics.txt
```

**Task:** Write an `awk` script (not a one-liner — use a file) that:
1. Group response times into 30-second buckets based on the timestamp field
2. For each bucket, print: `BUCKET_START  COUNT  AVG_MS  MAX_MS`
3. Flag any bucket where average response time exceeds 250ms with `[SLOW]` at the end of the line
4. At the end, print the overall average across all samples

**Hint:** Compute bucket start with `bucket = int($1 / 30) * 30`. Use separate arrays for count, sum, and max keyed by bucket. Iterate over buckets in sorted order in the `END` block — collect keys into an array and use `asort()` (GNU awk) or pipe the output to `sort -n`.

---

### Быстрая проверка

5. Using `awk`, sum the values piped from `printf '10\n20\n30\n40\n'` and print the total. Write a one-liner: `printf '10\n20\n30\n40\n' | awk ...`

```expected_output
100
```

hint: Think about how awk can accumulate a running total across all input lines using a variable.
hint: Use an awk pattern with a variable like `sum += $1` in the main block and an END rule to print the accumulated total.

6. Using `sed`, replace every space in the string `"the quick brown fox"` with a hyphen and print the result. Write a one-liner: `echo "the quick brown fox" | sed ...`

```expected_output
the-quick-brown-fox
```
hint: Think about how sed can be used to find and replace characters using a substitution pattern.
hint: Use sed's substitution command in the form s/old/new/g, where the g flag applies the replacement to every occurrence on the line.
