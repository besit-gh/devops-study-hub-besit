---
title: Разбор YAML и JSON на Python
module: python
duration_min: 15
difficulty: beginner
tags: [python, yaml, json, config, pyyaml, parsing]
exercises: 4
---

## Обзор

Работа DevOps неразрывно связана со структурированными текстовыми файлами. Манифесты Kubernetes, values Helm, стеки Docker Compose, выходные данные Terraform, workflow GitHub Actions, inventory Ansible и почти все конфигурации CI/CD описываются в YAML или JSON. Python — основной язык для интеграции этих систем: изменение тега образа в манифесте, сравнение конфигураций и передача выходных значений Terraform в скрипт развёртывания — обычные задачи DevOps-инженера. Надёжный разбор, преобразование и запись обоих форматов — базовый навык.

JSON входит в стандартную библиотеку Python и не требует установки. Для YAML нужен пакет `PyYAML` (`pip install pyyaml`), доступный во многих базовых образах DevOps-контейнеров и CI-runner. Оба формата естественно преобразуются в стандартные структуры Python — словари, списки, строки, числа, булевы значения и `None`. После разбора документа вы работаете с обычными объектами Python без отдельного API или языка запросов.

В DevOps эти навыки связаны с автоматизацией инфраструктуры (Ansible, Terraform), оркестрацией контейнеров (Kubernetes) и GitOps-конвейерами (Argo CD, Flux), где требуется программно создавать и обрабатывать структурированные конфигурации. Они также дополняют shell-скрипты: `jq` и `yq` подходят для простых однострочных команд, а Python удобнее, когда нужны логика, валидация или объединение нескольких файлов.

---

## Основные понятия

### JSON — встроенный разбор и сериализация

Модуль `json` в Python поддерживает полный цикл чтения и записи. Важно различать `json.loads` и `json.load` (буква `s` означает string) и `json.dumps` и `json.dump` (та же буква `s` означает строку).

| Функция | Входные данные | Результат | Когда использовать |
|---|---|---|---|
| `json.loads(s)` | Строка JSON | Объект Python | Разбор ответов API и вывода subprocess |
| `json.load(f)` | Файловый объект | Объект Python | Чтение файла `.json` с диска |
| `json.dumps(obj)` | Объект Python | Строка JSON | Отправка в API и вывод в stdout |
| `json.dump(obj, f)` | Объект Python и файл | Записывает в файл | Сохранение файла `.json` на диске |

```python
import json

# Parse a JSON string (common when reading subprocess output or HTTP responses)
text = '{"host": "db.example.com", "port": 5432, "ssl": true, "tags": null}'
config = json.loads(text)
print(config["host"])    # "db.example.com"
print(config["tags"])    # None  — JSON null maps to Python None
print(config["ssl"])     # True  — JSON boolean maps to Python bool

# Read from a file
with open("config.json") as f:
    data = json.load(f)

# Serialize: indent=2 is the standard choice for human-readable output
print(json.dumps(config, indent=2))

# sort_keys=True makes diffs cleaner — key order is stable across writes
with open("output.json", "w") as f:
    json.dump(config, f, indent=2, sort_keys=True)
```

**Соответствие типов — запомните таблицу:**

| Тип JSON | Тип Python |
|---|---|
| `object` `{}` | `dict` |
| `array` `[]` | `list` |
| `string` `""` | `str` |
| `number` (целое число) | `int` |
| `number` (дробное число) | `float` |
| `true` / `false` | `True` / `False` |
| `null` | `None` |

**Особенность `sort_keys=True`:** ключи сортируются во всём документе. Если downstream-система требует определённого порядка ключей (редкий случай, но такое бывает в устаревших инструментах), не сортируйте. В остальных случаях сортировка делает diff JSON-файлов в Git чище.

---

### Пограничные случаи JSON и обработка ошибок

Реальные JSON-данные из API, Terraform и CI-инструментов часто сложнее учебных примеров.

```python
import json
import datetime
from pathlib import Path

# --- Non-serializable types ---
# datetime objects are not JSON-serializable by default
event = {"ts": datetime.datetime.utcnow(), "level": "info"}
# json.dumps(event)  →  TypeError: Object of type datetime is not JSON serializable

# Fix 1: convert before serializing
event["ts"] = event["ts"].isoformat()
json.dumps(event)  # OK: "ts": "2024-01-15T10:30:00"

# Fix 2: custom encoder for systematic handling across a codebase
class DevOpsEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)

json.dumps({"ts": datetime.datetime.utcnow(), "path": Path("/etc/app")}, cls=DevOpsEncoder)

# --- Robust parsing with error context ---
def parse_json_safe(raw: str, source: str = "<unknown>") -> dict | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # e.lineno, e.colno, e.msg give you exact location in the document
        print(f"[ERROR] Invalid JSON from {source} at line {e.lineno} col {e.colno}: {e.msg}")
        return None

result = parse_json_safe('{"broken": }', source="ci-pipeline-output")
# [ERROR] Invalid JSON from ci-pipeline-output at line 1 col 12: Expecting value

# --- Handling large numbers ---
# Python int handles arbitrary precision; JSON spec doesn't cap integers
big = json.loads('{"id": 99999999999999999999}')
print(type(big["id"]))  # <class 'int'> — Python handles it fine

# --- Float precision ---
data = json.loads('{"ratio": 0.1}')
print(data["ratio"] + 0.2)   # 0.30000000000000004 — standard IEEE 754 float behavior
# Use round() or the decimal module when precision matters (e.g., cost calculations)
```

**Завершающие запятые:** JSON не допускает запятую после последнего элемента (`{"a": 1,}` — синтаксическая ошибка). В YAML такой проблемы нет. Если ошибки разбора возникают в JSON-конфигурациях, редактируемых вручную, проверьте завершающие запятые. Для таких файлов можно использовать `json5` или `commentjson`, либо проверять формат в CI через `jsonlint` или `jq .`.

**Пустая строка и отсутствующий ключ:** `json.loads('{"key": ""}')` возвращает `{"key": ""}` — ключ существует, но его значение пустое. Это не то же самое, что отсутствие ключа. Осторожно используйте `data.get("key")`: для отсутствующего ключа вернётся `None`, для пустой строки — `""`; оба значения считаются ложными в Python.

---

### YAML — основы PyYAML

YAML является надмножеством JSON, но гораздо чаще используется в инфраструктурных инструментах, поскольку поддерживает комментарии, многострочные строки и более удобный синтаксис вложенных структур.

```python
import yaml

# safe_load parses a YAML string into a Python dict
text = """
# Database configuration
host: db.example.com
port: 5432
replicas: 3
ssl: true
credentials:
  username: app_user
  password: "${DB_PASSWORD}"   # variable reference — stays as a string
tags:
  - prod
  - eu-west-1
"""

config = yaml.safe_load(text)
print(config["credentials"]["username"])  # "app_user"
print(config["tags"])                     # ["prod", "eu-west-1"]

# Parse from a file
with open("deployment.yaml") as f:
    manifest = yaml.safe_load(f)

# Write YAML — default_flow_style=False forces block style (human-readable)
print(yaml.safe_dump(config, default_flow_style=False))

# Write to file with explicit encoding
with open("output.yaml", "w", encoding="utf-8") as f:
    yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)
```

**Всегда используйте `yaml.safe_load()`, никогда не используйте `yaml.load()`.**
`yaml.load()` с загрузчиком по умолчанию может десериализовать произвольные объекты Python, в том числе выполнить код из YAML, контролируемого злоумышленником. Это реальный класс уязвимостей (CVE-2017-18342 и другие). `safe_load` ограничивает десериализацию базовыми типами. Для DevOps-скриптов нет обоснованной причины использовать `yaml.load()`.

**`default_flow_style=False`:** без этого параметра `safe_dump` может вывести короткие списки и словари в одну строку (`{host: db.example.com, port: 5432}`). Значение `False` принудительно включает блочный стиль, ожидаемый инструментами Kubernetes и Helm и удобный для проверки кода.

**YAML и JSON для файлов конфигурации:**

| Критерий | YAML | JSON |
|---|---|---|
| Поддержка комментариев | ✅ Да | ❌ Нет |
| Многострочные строки | ✅ Встроенная поддержка (`|`, `>`) | Неудобно (`\n` в строке) |
| Стандартная библиотека | ❌ Нужен PyYAML | ✅ Встроен |
| Строгость типов | ❌ Есть ловушки преобразования типов | ✅ Типы заданы явно |
| Инструменты (k8s, Helm, Ansible) | ✅ Основной формат | Вторичный |
| Конфигурация, создаваемая машиной | Оба варианта | ✅ Предпочтительнее (меньше неоднозначности) |

---

### Ловушки преобразования типов YAML

Автоматическое определение типов в YAML удобно, но имеет особенности, которые уже приводили к production-инцидентам.

```python
import yaml

# YAML booleans — these all parse as True/False in YAML 1.1 (PyYAML default)
booleans = yaml.safe_load("""
a: true
b: yes
c: on
d: True
e: YES
f: false
g: no
h: off
""")
print(booleans)
# {'a': True, 'b': True, 'c': True, 'd': True, 'e': True,
#  'f': False, 'g': False, 'h': False}

# Octal integers — YAML 1.1 parses 0-prefixed numbers as octal
octal_trap = yaml.safe_load("mode: 0755")
print(octal_trap["mode"])   # 493 (decimal) — NOT the string "0755"
# For file modes, always quote: mode: "0755"

# Null coercion — three ways to get None
nulls = yaml.safe_load("""
a: null
b: ~
c:          # empty value
""")
print(nulls)  # {'a': None, 'b': None, 'c': None}

# The Norway Problem — country code "NO" parses as False
country = yaml.safe_load("country: NO")
print(country)  # {'country': False}  ← production bug waiting to happen

# Fix: always quote strings that could be confused with booleans
country_fixed = yaml.safe_load("country: 'NO'")
print(country_fixed)  # {'country': 'NO'}

# Coercion in practice — Helm values file pitfall
helm_values = yaml.safe_load("""
replicaCount: 3
featureFlags:
  newCheckout: yes        # parsed as True (bool), not "yes" (str)
  region: NO              # parsed as False (bool), not "NO" (str)
  fileMode: 0644          # parsed as 420 (int), not "0644" (str)
""")
print(helm_values["featureFlags"])
# {'newCheckout': True, 'region': False, 'fileMode': 420}
```

**Проблема Norway:** в YAML 1.1 (по умолчанию в PyYAML) `NO`, `Yes`, `On`, `Off`, `True`, `False` и варианты регистра интерпретируются как булевы значения. С ними могут совпасть коды стран, имена окружений (например, `ON` для Онтарио) и feature flags. **Заключайте в кавычки любую строку, которую можно принять за boolean или null.** YAML 1.2 исправляет это (булевы значения — только `true` и `false`), но PyYAML использует 1.1. Библиотека `ruamel.yaml` поддерживает YAML 1.2.

**Практические правила безопасного использования кавычек:**
- Всегда заключайте в кавычки: `yes`, `no`, `on`, `off`, `true`, `false` и варианты регистра
- Всегда заключайте в кавычки строки прав доступа вроде `"0755"` и `"0644"`
- Всегда заключайте в кавычки версии, похожие на дробные числа (`"1.10"` и `1.10` — это разные значения; второе станет `1.1`)
- Всегда заключайте в кавычки даты ISO, если нужна строка, а не объект `datetime.date`

---

### Multi-Document YAML

Kubernetes manifests routinely bundle multiple resources (Deployment, Service, ConfigMap) in a single file, separated by `---`.

```python
import yaml

# safe_load_all returns a generator — wrap in list() to iterate multiple times
with open("manifests.yaml") as f:
    docs = list(yaml.safe_load_all(f))

# Filter to a specific kind
deployments = [d for d in docs if d and d.get("kind") == "Deployment"]

for doc in docs:
    if doc is None:
        continue  # trailing --- produces a None document; always guard
    kind = doc.get("kind", "Unknown")
    name = doc.get("metadata", {}).get("name", "unnamed")
    ns   = doc.get("metadata", {}).get("namespace", "default")
    print(f"{kind}/{name} in {ns}")

# Write multiple documents back out — dump_all handles the --- separators
with open("patched.yaml", "w") as f:
    yaml.dump_all(docs, f, default_flow_style=False)
```

**`safe_load_all` returns a generator:** if you consume it once (e.g., in a for loop), it's exhausted. Call `list()` on it immediately if you need to iterate more than once or check the length.

**`None` documents:** a file that ends with `---` or has `---` followed immediately by another `---` produces `None` entries in the generator. Always guard with `if doc is None: continue`.

**Building a multi-doc manifest programmatically:**

```python
import yaml

deployment = {
    "apiVersion": "apps/v1",
    "kind": "Deployment",
    "metadata": {"name": "api-server", "namespace": "production"},
    "spec": {"replicas": 3}
}

service = {
    "apiVersion": "v1",
    "kind": "Service",
    "metadata": {"name": "api-server", "namespace": "production"},
    "spec": {"type": "ClusterIP", "ports": [{"port": 80}]}
}

with open("stack.yaml", "w") as f:
    yaml.dump_all([deployment, service], f, default_flow_style=False)
# Produces a valid two-document YAML file with --- separator
```

---

### Practical Patterns

#### Read → Modify → Write

The most common DevOps scripting task: load a config, change one value, write it back.

```python
import yaml

def patch_image_tag(values_path: str, new_tag: str) -> None:
    with open(values_path) as f:
        values = yaml.safe_load(f)

    # Navigate nested structure safely
    if "image" not in values:
        raise KeyError(f"'image' key not found in {values_path}")

    old_tag = values["image"].get("tag", "<unset>")
    values["image"]["tag"] = new_tag
    print(f"Tag: {old_tag} → {new_tag}")

    with open(values_path, "w") as f:
        # sort_keys=False preserves original key order (important for Helm values)
        yaml.safe_dump(values, f, default_flow_style=False, sort_keys=False)

patch_image_tag("helm/values.yaml", "v2.3.1")
```

**Comment stripping warning:** PyYAML does not preserve comments. Loading and re-dumping a YAML file will silently strip all `#` comments. If your values files have important inline documentation, consider `ruamel.yaml` instead — it round-trips comments and key order faithfully. For files you own and control, prefer keeping comments in a template and generating the output file rather than round-tripping.

#### Deep Merge for Environment Overrides

A base config plus per-environment overrides is a standard pattern in Ansible group_vars, Helm value files, and custom deployment scripts.

```python
import json
from typing import Any

def deep_merge(base: dict, override: dict) -> dict:
    """
    Recursively merge override into base.
    - override values win on conflict
    - nested dicts are merged recursively
    - lists are replaced entirely, not concatenated (matches Helm behavior)
    """
    result = base.copy()
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value  # override wins, including for lists
    return result

# Load base + environment-specific override
with open("config.base.json") as f:
    base = json.load(f)

with open("config.prod.json") as f:
    override = json.load(f)

merged = deep_merge(base, override)

# Write result — sort_keys ensures stable output for version control
with open("config.merged.json", "w") as f:
    json.dump(merged, f, indent=2, sort_keys=True)
```

#### Validate Required Keys (with Nested Path Support)

```python
import yaml
from typing import Any

def get_nested(data: dict, dotted_key: str) -> tuple[bool, Any]:
    """Resolve a dotted key path like 'database.host' into nested dict."""
    parts = dotted_key.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current

def validate_config(config: dict, required: list[str]) -> list[str]:
    """Return list of missing or null required keys (supports dot notation)."""
    missing = []
    for key in required:
        found, value = get_nested(config, key)
        if not found or value is None:
            missing.append(key)
    return missing

with open("app.yaml") as f:
    config = yaml.safe_load(f)

required_keys = [
    "host",
    "port",
    "database.host",
    "database.port",
    "auth.secret_key",
]
missing = validate_config(config, required_keys)

if missing:
    raise ValueError(f"Config missing required keys: {missing}")

print("Config validation passed.")
```

#### Parse Terraform Output

Terraform's `-json` flag produces structured output that's straightforward to consume from Python, making it easy to pass infrastructure values (VPC IDs, load balancer hostnames, RDS endpoints) into downstream deployment scripts.

```python
import subprocess
import json

def get_terraform_outputs(working_dir: str = ".") -> dict:
    """
    Run `terraform output -json` and return parsed outputs.
    Each key maps to {"value": ..., "type": ...} — extract .value for the data.
    """
    result = subprocess.run(
        ["terraform", "output", "-json"],
        capture_output=True,
        text=True,
        check=True,       # raises CalledProcessError on non-zero exit
        cwd=working_dir   # run in the correct Terraform workspace
    )
    raw_outputs = json.loads(result.stdout)

    # Terraform wraps each output: {"vpc_id": {"value": "vpc-abc123", "type": "string"}}
    # Flatten to {"vpc_id": "vpc-abc123"} for convenience
    return {k: v["value"] for k, v in raw_outputs.items()}

def update_deployment_config(tf_dir: str, config_path: str) -> None:
    outputs = get_terraform_outputs(tf_dir)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Inject Terraform outputs into deployment config
    config.setdefault("infrastructure", {})
    config["infrastructure"]["vpc_id"]       = outputs.get("vpc_id")
    config["infrastructure"]["db_endpoint"]  = outputs.get("rds_endpoint")
    config["infrastructure"]["alb_dns"]      = outputs.get("alb_dns_name")

    with open(config_path, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)

    print(f"Updated {config_path} with Terraform outputs.")

# Usage
import yaml
update_deployment_config("infra/terraform", "deploy/config.yaml")
```

---

## Примеры

### Example 1 — Patch a Kubernetes Deployment Image Tag

**Scenario:** A CI pipeline builds a new Docker image and needs to update the image tag in a Kubernetes Deployment manifest before applying it.

```bash
# Setup: create a sample manifest
cat > deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
  namespace: production
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: api
          image: myregistry/api:v1.0.0
          ports:
            - containerPort: 8080
EOF
```

```python
# patch_deployment.py
import yaml
import sys

def patch_image(manifest_path: str, container_name: str, new_tag: str) -> None:
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)

    containers = (
        manifest
        .get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )

    patched = False
    for container in containers:
        if container["name"] == container_name:
            repo = container["image"].rsplit(":", 1)[0]  # strip existing tag
            old_image = container["image"]
            container["image"] = f"{repo}:{new_tag}"
            print(f"  {old_image}  →  {container['image']}")
            patched = True

    if not patched:
        raise ValueError(f"Container '{container_name}' not found in {manifest_path}")

    with open(manifest_path, "w") as f:
        yaml.safe_dump(manifest, f, default_flow_style=False, sort_keys=False)

if __name__ == "__main__":
    # Usage: python patch_deployment.py deployment.yaml api v2.1.0
    patch_image(sys.argv[1], sys.argv[2], sys.argv[3])
```

```bash
# Run it
python patch_deployment.py deployment.yaml api v2.1.0

# Verify the change
grep "image:" deployment.yaml
#   image: myregistry/api:v2.1.0

# Apply to the cluster
kubectl apply -f deployment.yaml
```

---

### Example 2 — Scan All Manifests in a Directory for Missing Resource Limits

**Scenario:** A pre-commit hook or CI check that flags any Kubernetes Deployment whose containers lack CPU/memory resource limits — a common misconfiguration that causes noisy neighbor issues.

```python
# check_resource_limits.py
import yaml
import sys
from pathlib import Path

def check_manifest(path: Path) -> list[str]:
    """Return list of violation messages for this manifest file."""
    violations = []
    with open(path) as f:
        docs = list(yaml.safe_load_all(f))

    for doc in docs:
        if not doc or doc.get("kind") != "Deployment":
            continue
        name = doc.get("metadata", {}).get("name", "unnamed")
        containers = (
            doc.get("spec", {})
               .get("template", {})
               .get("spec", {})
               .get("containers", [])
        )
        for c in containers:
            limits = c.get("resources", {}).get("limits", {})
            if not limits.get("cpu") or not limits.get("memory"):
                violations.append(
                    f"{path}  Deployment/{name}  container={c['name']}  missing resource limits"
                )
    return violations

def scan_directory(directory: str) -> int:
    """Scan all YAML files. Returns number of violations found."""
    all_violations = []
    for path in Path(directory).rglob("*.yaml"):
        try:
            all_violations.extend(check_manifest(path))
        except Exception as e:
            print(f"[WARN] Could not parse {path}: {e}")

    for v in all_violations:
        print(f"[FAIL] {v}")

    if not all_violations:
        print("[PASS] All Deployments have resource limits defined.")

    return len(all_violations)

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    violations = scan_directory(target)
    sys.exit(1 if violations else 0)  # non-zero exit fails the CI step
```

```bash
# Run against a manifests directory
python check_resource_limits.py ./k8s/

# [FAIL] ./k8s/api.yaml  Deployment/api-server  container=api  missing resource limits
# Exit code 1 — CI pipeline fails

# Fix: add limits to the manifest, re-run to verify
python check_resource_limits.py ./k8s/
# [PASS] All Deployments have resource limits defined.
```

---

### Example 3 — Merge Base and Environment Configs, Write Final JSON

**Scenario:** A deployment system maintains a `config.base.json` shared across all environments, with per-environment overrides in `config.prod.json`. The pipeline merges them and writes `config.final.json` for the app to consume at startup.

```bash
# Setup
cat > config.base.json << 'EOF'
{
  "app": {"log_level": "info", "timeout_s": 30},
  "database": {"port": 5432, "ssl": true, "pool_size": 5},
  "cache": {"ttl_s": 300, "max_entries": 1000}
}
EOF

cat > config.prod.json << 'EOF'
{
  "database": {"host": "prod-db.internal", "pool_size": 20},
  "cache": {"ttl_s": 60}
}
EOF
```

```python
# merge_config.py
import json
import sys
from pathlib import Path

def deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def merge_configs(base_path: str, override_path: str, output_path: str) -> None:
    with open(base_path) as f:
        base = json.load(f)
    with open(override_path) as f:
        override = json.load(f)

    merged = deep_merge(base, override)

    with open(output_path, "w") as f:
        json.dump(merged, f, indent=2, sort_keys=True)

    print(f"Written: {output_path}")
    print(json.dumps(merged, indent=2, sort_keys=True))

merge_configs("config.base.json", "config.prod.json", "config.final.json")
```

```bash
python merge_config.py
# Written: config.final.json
# {
#   "app": {"log_level": "info", "timeout_s": 30},
#   "cache": {"max_entries": 1000, "ttl_s": 60},       ← overridden
#   "database": {"host": "prod-db.internal", "pool_size": 20, "port": 5432, "ssl": true}
# }                            ↑ new key                 ↑ overridden

# Verify with jq
jq '.database.pool_size' config.final.json   # 20 (not 5 from base)
jq '.cache.max_entries' config.final.json    # 1000 (preserved from base)
```

---

### Example 4 — Extract and Pretty-Print Terraform Outputs as YAML

**Scenario:** After `terraform apply`, a release script extracts outputs and writes them as a YAML file that Ansible consumes as extra vars.

```python
# tf_to_ansible_vars.py
import subprocess
import json
import yaml
import sys

def terraform_output_to_yaml(tf_dir: str, output_path: str) -> None:
    # Run terraform output and capture structured JSON
    result = subprocess.run(
        ["terraform", "output", "-json"],
        capture_output=True, text=True, check=True, cwd=tf_dir
    )
    tf_outputs = json.loads(result.stdout)

    # Flatten from {key: {value: ..., type: ...}} to {key: value}
    flat = {k: v["value"] for k, v in tf_outputs.items()}

    # Write as YAML for Ansible --extra-vars @vars.yaml
    with open(output_path, "w") as f:
        yaml.safe_dump(flat, f, default_flow_style=False, sort_keys=True)

    print(f"Wrote {len(flat)} Terraform outputs to {output_path}")
    for k, v in sorted(flat.items()):
        print(f"  {k}: {v}")

if __name__ == "__main__":
    tf_dir     = sys.argv[1] if len(sys.argv) > 1 else "."
    output_yml = sys.argv[2] if len(sys.argv) > 2 else "tf_vars.yaml"
    terraform_output_to_yaml(tf_dir, output_yml)
```

```bash
python tf_to_ansible_vars.py infra/ tf_vars.yaml

# Wrote 4 Terraform outputs to tf_vars.yaml
#   alb_dns_name: api-prod-1234567890.us-east-1.elb.amazonaws.com
#   db_endpoint: prod-db.abc123.us-east-1.rds.amazonaws.com
#   rds_port: 5432
#   vpc_id: vpc-0abc123456def7890

cat tf_vars.yaml
# alb_dns_name: api-prod-1234567890.us-east-1.elb.amazonaws.com
# db_endpoint: prod-db.abc123.us-east-1.rds.amazonaws.com
# rds_port: 5432
# vpc_id: vpc-0abc123456def7890

# Use directly in Ansible
ansible-playbook deploy.yml --extra-vars @tf_vars.yaml
```

---

## Практические задания

### Exercise 1 — Fix the YAML Coercion Bugs

Create the following file and write a Python script that loads it, identifies which values parsed as unexpected types, and prints a corrected version where all values are the intended strings.

```yaml
# broken_values.yaml
country_code: NO
feature_flag: yes
environment: ON
file_permission: 0644
api_version: 1.10
debug_mode: off
```

Your script should:
1. Load the file with `yaml.safe_load`
2. Print each key, its Python type, and its value
3. Identify which values are `bool` or `int` instead of `str`
4. Write a corrected YAML file where all values are quoted strings
5. Reload the corrected file and confirm every value is now `str`

**Hint:** `yaml.safe_dump` will not re-add quotes automatically. You need to convert values to strings in Python before dumping.

---

### Exercise 2 — Multi-Document Manifest Inventory

Write a script that accepts a directory path as a command-line argument, scans all `.yaml` files recursively, parses each as a multi-document YAML file, and prints a summary table of every Kubernetes resource found.

Expected output format:
```
FILE                        KIND         NAME              NAMESPACE
k8s/api/deployment.yaml     Deployment   api-server        production
k8s/api/service.yaml        Service      api-server        production
k8s/db/configmap.yaml       ConfigMap    db-config         production
```

Requirements:
- Use `yaml.safe_load_all` for each file
- Skip `None` documents (from trailing `---`)
- Skip files that aren't Kubernetes resources (no `kind` or `apiVersion` key)
- Handle parse errors gracefully — print a warning and continue to the next file
- Sort output by file path, then by kind

---

### Exercise 3 — Config Differ

Write a Python script that takes two JSON or YAML config files as arguments and prints a human-readable diff of what changed between them. It should handle nested structures.

```bash
python config_diff.py config.v1.yaml config.v2.yaml
```

Expected output:
```
CHANGED  database.pool_size        5  →  20
ADDED    database.read_replica     prod-replica.internal
REMOVED  cache.legacy_mode
```

Requirements:
- Auto-detect format from file extension (`.json` vs `.yaml`/`.yml`)
- Use recursion to traverse nested dicts
- Categorize each change as `ADDED`, `REMOVED`, or `CHANGED`
- Lists that differ should be shown as `CHANGED` (no need to diff list contents)
- Do not use any external diff library — implement the comparison yourself

---

### Exercise 4 — GitHub Actions Workflow Validator

GitHub Actions workflows are YAML files in `.github/workflows/`. Write a validator that checks a workflow file for common mistakes.

```bash
python validate_workflow.py .github/workflows/deploy.yml
```

Checks to implement:
1. **Top-level keys:** `name`, `on`, and `jobs` must all be present
2. **Job names:** every job must have a `runs-on` key
3. **Step names:** every step in every job should have a `name` key (warn if missing, don't fail)
4. **Secrets in env:** scan all `env` blocks at any level; warn if any value contains `${{secrets.` but the key name doesn't suggest it's a secret (i.e., key doesn't contain `SECRET`, `TOKEN`, `KEY`, or `PASSWORD` case-insensitively)
5. **Boolean trap:** check if any key named `on` parsed as `True` instead of the string `"on"` — this is a real PyYAML trap with GitHub Actions files

Exit with code 0 if only warnings, code 1 if any errors.

**Hint for the `on` trap:** `yaml.safe_load` will parse the top-level `on:` key in a GitHub Actions file as `True` because `on` is a YAML 1.1 boolean. Check `if True in workflow:` rather than `if "on" in workflow:`.

---

### Быстрая проверка

1. Serialize a dict to a JSON string.

   ```python
   import json; print(json.dumps({'name': 'devops', 'version': 3}))
   ```

   ```expected_output
   {"name": "devops", "version": 3}
   ```

hint: Think about which Python standard library module handles conversion between Python objects and JSON format.
hint: Use json.dumps() with a dictionary argument to produce a JSON-formatted string from your Python dict.

2. Detect Python types after JSON parsing.

   ```python
   import json; d = json.loads('{"enabled": true, "count": 5}'); print(type(d['enabled']).__name__, type(d['count']).__name__)
   ```

   ```expected_output
   bool int
   ```
hint: Think about how Python's json module parses JSON values and what built-in function reveals the type of any parsed object.
hint: Use json.loads() to parse your JSON string, then call type() on each value and print the resulting type names using their __name__ attribute.
