# Python — краткая справка

## Встроенные типы и операции

| Шаблон | Описание |
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

| Шаблон | Описание |
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
| `Path("f").read_text()` | Прочитать файл одним вызовом |
| `Path("f").write_text(s)` | Записать файл одним вызовом |

## subprocess

| Шаблон | Описание |
|---------|-------------|
| `subprocess.run(["ls", "-l"])` | Запустить команду и дождаться завершения |
| `subprocess.run(cmd, check=True)` | Выбросить исключение при ненулевом коде завершения |
| `subprocess.run(cmd, capture_output=True, text=True)` | Сохранить stdout и stderr |
| `result.stdout` | Строка захваченного stdout |
| `result.returncode` | Код завершения |
| `subprocess.run(cmd, shell=True)` | Команда через shell (по возможности избегать) |

## Обработка ошибок

| Шаблон | Описание |
|---------|-------------|
| `try: ... except ValueError as e:` | Перехватить конкретное исключение |
| `except (TypeError, KeyError):` | Несколько типов исключений |
| `except Exception as e:` | Перехватить любое исключение |
| `finally: ...` | Выполняется всегда |
| `raise ValueError("msg")` | Выбросить исключение |
| `raise` | Повторно выбросить текущее исключение |

## Common CLI & DevOps Шаблонs

| Шаблон | Описание |
|---------|-------------|
| `import argparse` | Разбор аргументов командной строки |
| `import os; os.environ.get("VAR")` | Прочитать переменную окружения |
| `import sys; sys.exit(1)` | Завершить с указанным кодом |
| `import logging; logging.basicConfig(level=logging.INFO)` | Базовое журналирование |
| `import re; re.findall(r"\d+", s)` | Найти все совпадения |
| `import yaml; yaml.safe_load(fh)` | Разобрать YAML |
| `import requests; requests.get(url).json()` | Выполнить HTTP GET и разобрать JSON |

## pip & Environments

| Command | Описание |
|---------|-------------|
| `python -m venv .venv` | Создать виртуальное окружение |
| `source .venv/bin/activate` | Активировать виртуальное окружение |
| `pip install package` | Установить пакет |
| `pip install -r requirements.txt` | Установить зависимости из файла |
| `pip freeze > requirements.txt` | Сохранить список зависимостей |
| `pip list --outdated` | Показать устаревшие пакеты |
| `python -m pytest` | Запустить тесты |
