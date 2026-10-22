#!/usr/bin/env python3
"""Translate lesson Markdown and seeded SQLite content to Russian using OpenAI.

The localization branch can run this script through GitHub Actions when the
commit message contains [translate] and OPENAI_API_KEY is configured."""
from __future__ import annotations
import argparse, json, os, re, shutil, sqlite3, tempfile
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "hub.db"
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
PROTECTED_RE = re.compile(r"(?s)\x60{3}.*?\x60{3}|~~~.*?~~~|\x60[^\x60\n]+\x60|https?://[^\s)]+|</?[A-Za-z][^>]*>")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
LETTER_RE = re.compile(r"[A-Za-zА-Яа-яЁё]")

def looks_russian(text):
    letters = len(LETTER_RE.findall(text))
    return letters > 0 and len(CYRILLIC_RE.findall(text)) / letters > 0.60

def extract_json(text):
    text = text.strip()
    if text.startswith(chr(96) * 3):
        text = re.sub(r"^\x60{3}(?:json)?\s*", "", text)
        text = re.sub(r"\s*\x60{3}$", "", text)
    if text.startswith("[") or text.startswith(chr(96) * 3 + "json\\n["):
        start, end = text.find("["), text.rfind("]")
    else:
        start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1] if start >= 0 and end > start else text)

def translate_text(client, text):
    if not text.strip():
        return text
    prefix = ""
    frontmatter = re.match(r"(?s)^(---\n.*?\n---\s*\n?)(.*)$", text)
    if frontmatter:
        prefix, text = frontmatter.group(1), frontmatter.group(2)
        title_match = re.search(r"(?m)^title:\s*(.+)$", prefix)
        if title_match:
            original_title = title_match.group(1).strip().strip('"')
            if not looks_russian(original_title):
                title_response = client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", MODEL), temperature=0, max_tokens=120,
                    messages=[
                        {"role": "system", "content": "Переведи название технического урока на русский. Сохрани названия технологий и общепринятые термины. Верни только название."},
                        {"role": "user", "content": original_title},
                    ],
                )
                translated_title = (title_response.choices[0].message.content or "").strip().strip('"')
                if translated_title:
                    start, end = title_match.span(1)
                    prefix = prefix[:start] + translated_title + prefix[end:]
    protected = {}
    def protect(match):
        token = f"ZXQPROTECTED{len(protected):04d}QXZ"
        protected[token] = match.group(0)
        return token
    prepared = PROTECTED_RE.sub(protect, text)
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", MODEL), temperature=0, max_tokens=16000,
        messages=[
            {"role": "system", "content": (
                "Ты профессиональный технический переводчик DevOps-курсов. Переводи оставшиеся англоязычные объяснения "
                "на естественный русский язык, не сокращай и не пересказывай. Уже переведённый русский текст оставляй без изменений. Сохраняй Markdown, "
                "заголовки, списки и таблицы. Не переводи технологии, команды, параметры, env-переменные, "
                "имена файлов, пути и API-идентификаторы. Верни только перевод."
            )},
            {"role": "user", "content": prepared},
        ],
    )
    translated = response.choices[0].message.content or ""
    if not translated.strip():
        raise RuntimeError("OpenAI вернул пустой перевод")
    for token, original in protected.items():
        if translated.count(token) != 1:
            raise RuntimeError(f"OpenAI изменил защищённый маркер {token}; файл не записан")
        translated = translated.replace(token, original)
    return prefix + translated.strip() + ("\n" if text.endswith("\n") else "")

def parse_json_field(value):
    if value is None:
        return None
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (TypeError, json.JSONDecodeError):
        return value

def translate_database(client):
    specs = {
        "modules": (["title", "group_name"], []),
        "lessons": (["title"], []),
        "quiz_questions": (["question", "options", "explanation"], ["options"]),
        "interview_questions": (["question", "hints", "model_answer"], ["hints"]),
        "projects": (["title", "description"], []),
        "project_steps": (["title", "prompt", "hints"], ["hints"]),
    }
    stats = {}
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        for table, (wanted, json_fields) in specs.items():
            available = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            fields = [f for f in wanted if f in available]
            if not fields:
                continue
            rows = conn.execute(f"SELECT id, {', '.join(fields)} FROM {table}").fetchall()
            records = []
            for row in rows:
                item = {"id": row["id"]}
                for field in fields:
                    value = row[field]
                    item[field] = parse_json_field(value) if field in json_fields else value
                records.append(item)
            count = 0
            for offset in range(0, len(records), 8):
                batch = records[offset:offset + 8]
                prompt = (
                    "Переведи на русский все значения для чтения человеком в JSON-массиве. Верни только "
                    "JSON-массив той же длины и порядка. Не меняй id, ключи, числа, порядок вариантов, "
                    "названия технологий, команды, пути, переменные и код. В options/modules/hints "
                    "переводи только естественный текст. Сохрани структуру объектов.\n\n"
                    + json.dumps(batch, ensure_ascii=False)
                )
                raw = client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", MODEL), temperature=0, max_tokens=12000,
                    messages=[
                        {"role": "system", "content": "Ты точный переводчик технического контента DevOps на русский."},
                        {"role": "user", "content": prompt},
                    ],
                ).choices[0].message.content or ""
                translated = extract_json(raw)
                if not isinstance(translated, list) or len(translated) != len(batch):
                    raise RuntimeError(f"Некорректный JSON-пакет таблицы {table}")
                for item in translated:
                    if not isinstance(item, dict) or item.get("id") not in {r["id"] for r in batch}:
                        raise RuntimeError(f"Потерян идентификатор записи таблицы {table}")
                    values, assignments = [], []
                    for field in fields:
                        if field not in item:
                            raise RuntimeError(f"В переводе отсутствует поле {table}.{field}")
                        value = json.dumps(item[field], ensure_ascii=False) if field in json_fields else item[field]
                        assignments.append(f"{field} = ?")
                        values.append(value)
                    values.append(item["id"])
                    conn.execute(f"UPDATE {table} SET {', '.join(assignments)} WHERE id = ?", values)
                    count += 1
                conn.commit()
            stats[table] = count
    finally:
        conn.close()
    return stats

def main():
    parser = argparse.ArgumentParser(description="Перевод учебного контента DevOps Study Hub на русский")
    parser.add_argument("--apply", action="store_true", help="перевести и записать изменения")
    parser.add_argument("--dry-run", action="store_true", help="показать объём работ без вызова API")
    parser.add_argument("--markdown-only", action="store_true", help="переводить только Markdown-файлы")
    parser.add_argument("--database-only", action="store_true", help="переводить только записи существующей базы данных")
    args = parser.parse_args()
    load_dotenv(ROOT / "backend" / ".env")
    if args.markdown_only and args.database_only:
        raise SystemExit("Выберите только один режим: --markdown-only или --database-only.")
    files = [] if args.database_only else sorted((ROOT / "content").rglob("*.md")) + sorted((ROOT / "reference").rglob("*.md"))
    if args.dry_run or not args.apply:
        print(f"Markdown-файлов для проверки: {len(files)}")
        print(f"База данных: {DB_PATH}")
        print("Без --apply API не вызывается и файлы не изменяются.")
        if not args.dry_run:
            print("Для запуска укажите --apply. Требуется OPENAI_API_KEY в backend/.env.")
        return
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Не задан OPENAI_API_KEY. Укажите его в backend/.env.")
    if args.database_only and not DB_PATH.exists():
        raise SystemExit(f"Не найдена база данных: {DB_PATH}. Сначала запустите backend один раз.")
    backup = Path(tempfile.mkdtemp(prefix="devops-hub-translation-backup-"))
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, backup / "hub.db")
    for path in files:
        target = backup / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    print(f"Резервная копия: {backup}")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    translated_count = 0
    for path in files:
        original = path.read_text(encoding="utf-8")
        path.write_text(translate_text(client, original), encoding="utf-8")
        translated_count += 1
        print(f"[Markdown] {path.relative_to(ROOT)}")
    stats = translate_database(client) if not args.markdown_only and DB_PATH.exists() else {}
    print(f"Обработано Markdown-файлов: {translated_count}/{len(files)}")
    if args.markdown_only:
        print("Режим --markdown-only: база данных пропущена.")
    elif stats:
        print("Обработаны записи БД: " + ", ".join(f"{k}={v}" for k, v in stats.items()))
    else:
        print(f"База данных не найдена ({DB_PATH}); переведены Markdown-файлы. После первого запуска backend выполните --database-only --apply.")
    print("Проверьте изменения и выполните тесты перед коммитом.")

if __name__ == "__main__":
    main()
