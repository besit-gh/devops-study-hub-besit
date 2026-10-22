# Python — краткая справка

## Встроенные типы и операции

| Pattern | Description |
|---------|-------------|
| `[x for x in lst if cond]` | Генератор списка |
| `{k: v for k, v in d.items()}` | Генератор словаря |
| `{x for x in lst}` | Генератор множества |
| `(x for x in lst)` | Генераторное выражение |
| `*args, **kwargs` | Переменное число позиционных и именованных аргументов |
| `a, *rest = lst` | Распаковка с остатком |
| `d.get("key", default)` | Получить значение словаря с умолчанием |
| `sorted(lst, key=lambda x: x.val)` | Сортировать по атрибуту |
| `zip(a, b)` | Параллельный обход |
| `enumerate(lst)` | Обход с индексом и значением |
| `any(cond for x in lst)` | Хотя бы один элемент удовлетворяет условию |
| `all(cond for x in lst)` | Все элементы удовлетворяют условию |

## Файлы и ввод-вывод

| Pattern | Description |
|---------|-------------|
| `with open("f") as fh:` | Безопасно открыть файл |
| `fh.read()` | Прочитать файл целиком |
| `fh.readlines()` | Прочитать как список строк |
| `for line in fh:` | Читать строки последовательно |
| `json.load(fh)` | Разобрать JSON-файл |
| `json.dump(obj, fh, indent=2)` | Записать JSON-файл |
| `json.loads(s)` | Разобрать строку JSON |
| `json.dumps(obj)` | Сериализовать в строку JSON |
| `pathlib.Path("dir") / "file"` | Объединить части пути |
| `Path("f").read_text()` | Read file in one call |
| `Path("f").write_text(s)` | Write file in one call |

## subprocess

| Pattern | Description |
|---------|-------------|
| `subprocess.run(["ls", "-l"])` | Run command, wait |
| `subprocess.run(cmd, check=True)` | Raise on non-zero exit |
| `subprocess.run(cmd, capture_output=True, text=True)` | Capture stdout/stderr |
| `result.stdout` | Captured stdout string |
| `result.returncode` | Exit code |
| `subprocess.run(cmd, shell=True)` | Shell string (avoid if possible) |

## Обработка ошибок

| Pattern | Description |
|---------|-------------|
| `try: ... except ValueError as e:` | Catch specific exception |
| `except (TypeError, KeyError):` | Multiple exception types |
| `except Exception as e:` | Catch any exception |
| `finally: ...` | Always executes |
| `raise ValueError("msg")` | Raise exception |
| `raise` | Re-raise current exception |

## Common CLI & DevOps Patterns

| Pattern | Description |
|---------|-------------|
| `import argparse` | CLI argument parsing |
| `import os; os.environ.get("VAR")` | Read env variable |
| `import sys; sys.exit(1)` | Exit with code |
| `import logging; logging.basicConfig(level=logging.INFO)` | Basic logging |
| `import re; re.findall(r"\d+", s)` | Find all matches |
| `import yaml; yaml.safe_load(fh)` | Parse YAML |
| `import requests; requests.get(url).json()` | HTTP GET + parse JSON |

## pip & Environments

| Command | Description |
|---------|-------------|
| `python -m venv .venv` | Create virtual environment |
| `source .venv/bin/activate` | Activate venv |
| `pip install package` | Install package |
| `pip install -r requirements.txt` | Install from file |
| `pip freeze > requirements.txt` | Capture dependencies |
| `pip list --outdated` | Show outdated packages |
| `python -m pytest` | Run tests |
