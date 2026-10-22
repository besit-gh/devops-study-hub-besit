import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_conn

PROJECTS = [
    {
        "slug": "containerize-python-app",
        "title": "Контейнеризация приложения на Python",
        "description": "Соберите и контейнеризируйте веб-сервис на Python, затем создайте CI/CD-пайплайн для его тестирования и публикации.",
        "modules": ["Python", "Docker", "CI/CD Pipelines"],
        "difficulty": "intermediate",
        "steps": [
            {
                "order_index": 1,
                "title": "Создать файл requirements",
                "type": "sandbox",
                "prompt": (
                    "Напишите Bash-команду, которая создаёт `/tmp/requirements.txt` ровно с двумя строками:\n\n"
                    "```\nflask==3.0.0\ngunicorn==21.2.0\n```\n\n"
                    "Затем выведите количество строк в файле."
                ),
                "language": "bash",
                "expected_output": "2",
                "hints": [
                    "Используйте `printf` или `echo -e` с `\\n`, чтобы записать обе строки за один раз.",
                    "Подсчитайте строки с помощью `wc -l`, затем передайте результат в `awk '{print $1}'`, чтобы убрать имя файла из вывода.",
                ],
            },
            {
                "order_index": 2,
                "title": "Разобрать конфигурацию приложения",
                "type": "sandbox",
                "prompt": (
                    "Напишите однострочную команду Python, которая разбирает эту строку YAML и выводит значение `port`:\n\n"
                    '`name: my-app\\nport: 8080\\ndebug: false`\n\n'
                    "Импортируйте `yaml` из библиотеки PyYAML."
                ),
                "language": "python",
                "expected_output": "8080",
                "hints": [
                    "Передайте строку в `yaml.safe_load()`: символы `\\n` обозначают реальные переводы строк, которые YAML корректно обработает.",
                    "Обратитесь к результату как к словарю Python: `yaml.safe_load('name: my-app\\nport: 8080\\ndebug: false')['port']`.",
                ],
            },
            {
                "order_index": 3,
                "title": "Написать production Dockerfile",
                "type": "ai",
                "prompt": (
                    "Напишите многоэтапный Dockerfile для приложения Flask на Python.\n\n"
                    "Этап 1 (builder): установите зависимости из requirements.txt в virtualenv.\n"
                    "Этап 2 (runtime): скопируйте в минимальный базовый образ только virtualenv и код приложения.\n\n"
                    "Include best practices: non-root user, no dev packages in the final image, "
                    "a HEALTHCHECK instruction, and explicit EXPOSE."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Опишите два этапа: на первом зависимости устанавливаются в virtualenv, на втором копируется только окружение. Создайте непривилегированного пользователя с помощью `useradd` или `adduser`.",
                    "Добавьте директивы `COPY --from=builder /opt/venv /opt/venv`, `ENV PATH=/opt/venv/bin:$PATH`, `USER`, `EXPOSE` и `HEALTHCHECK CMD curl -f http://localhost/ || exit 1`.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать CI-пайплайн",
                "type": "ai",
                "prompt": (
                    "Создайте workflow GitHub Actions (`.github/workflows/ci.yml`), который:\n"
                    "1. Запускается при push в `main` и при открытии pull request\n"
                    "2. Запускает `pytest` с кэшированием pip\n"
                    "3. Собирает и отправляет Docker-образ в GitHub Container Registry (GHCR) только после слияния в `main`\n"
                    "4. Кэширует слои Docker между запусками\n\n"
                    "Кратко объясните, почему вы разделили задачи именно таким образом."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Разделите workflow на две job: `test` (запускается при всех событиях) и `publish` (только при push в `main`, с `needs: test`, чтобы публикация происходила после успешных тестов).",
                    "Используйте `actions/cache` для pip, `docker/login-action` с `${{ secrets.GITHUB_TOKEN }}` для GHCR и `docker/build-push-action` с `cache-from: type=gha` для кэширования слоёв Docker.",
                ],
            },
        ],
    },
    {
        "slug": "zero-downtime-deploy",
        "title": "Развёртывание в Kubernetes без простоя",
        "description": "Спроектируйте рабочую нагрузку Kubernetes с rolling updates, readiness probes и механизмом самовосстановления.",
        "modules": ["Kubernetes", "Docker", "CI/CD Pipelines"],
        "difficulty": "advanced",
        "steps": [
            {
                "order_index": 1,
                "title": "Извлечь образ из вывода kubectl",
                "type": "sandbox",
                "prompt": (
                    "Use `awk` to extract the container image from this `kubectl get pods -o wide` output line "
                    "and print only the image name:\n\n"
                    "`myapp-6d4b8 1/1 Running 0 10m nginx:1.24`"
                ),
                "language": "bash",
                "expected_output": "nginx:1.24",
                "hints": [
                    "Think about which field in the space-delimited output corresponds to the image name.",
                    "Use `awk '{print $NF}'` to print the last field from the input line.",
                ],
            },
            {
                "order_index": 2,
                "title": "Разобрать JSON состояния Pod",
                "type": "sandbox",
                "prompt": (
                    "Write a bash one-liner (using Python) that parses this JSON and prints the pod phase:\n\n"
                    '`{"status":{"phase":"Running","hostIP":"10.0.0.1"}}`'
                ),
                "language": "bash",
                "expected_output": "Running",
                "hints": [
                    "Pipe the JSON string into a Python one-liner that reads from stdin and navigates the parsed dict.",
                    "Try `echo '{...}' | python3 -c \"import sys,json; print(json.loads(sys.stdin.read())['status']['phase'])\"`.",
                ],
            },
            {
                "order_index": 3,
                "title": "Написать манифест Deployment",
                "type": "ai",
                "prompt": (
                    "Write a complete Kubernetes Deployment manifest for an app called `api-server` with:\n"
                    "- 3 replicas\n"
                    "- Rolling update strategy: `maxSurge: 1`, `maxUnavailable: 0`\n"
                    "- CPU and memory resource requests and limits\n"
                    "- An HTTP readiness probe on `/health` port 8080 with appropriate `initialDelaySeconds`\n"
                    "- An HTTP liveness probe that gives the pod 30 seconds to start\n\n"
                    "Explain your choice of readiness vs liveness probe parameters."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Cover three key sections: `spec.strategy.rollingUpdate`, container `readinessProbe`, and container `livenessProbe`, each with `httpGet` on `/health` port 8080.",
                    "For zero-downtime: set `maxUnavailable: 0` so no pod is removed before a replacement is ready; set `initialDelaySeconds` on readiness to the actual app warmup time.",
                ],
            },
            {
                "order_index": 4,
                "title": "Сравнить readiness- и liveness-пробы",
                "type": "ai",
                "prompt": (
                    "Explain the difference between Kubernetes readiness and liveness probes.\n\n"
                    "Specifically: describe a realistic scenario where a pod fails a readiness check but passes "
                    "a liveness check — and why that distinction matters for zero-downtime deployments.\n\n"
                    "Then write probe definitions for a service that has a 30-second startup warmup "
                    "but must be ready within 60 seconds of launch."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Readiness controls traffic routing (pod removed from Service endpoints); liveness controls restarts — they have different consequences when they fail.",
                    "Key scenario: a pod loading a large cache fails readiness (no traffic) but passes liveness (no restart) — traffic is withheld without killing the pod.",
                ],
            },
        ],
    },
    {
        "slug": "linux-system-hardening",
        "title": "Усиление безопасности Linux",
        "description": "Проведите аудит и защитите Linux-сервер: права доступа, конфигурация SSH, задания cron и управление пользователями.",
        "modules": ["Linux", "DevSecOps"],
        "difficulty": "intermediate",
        "steps": [
            {
                "order_index": 1,
                "title": "Найти файлы, доступные для записи всем",
                "type": "sandbox",
                "prompt": (
                    "Напишите Bash-скрипт, который:\n"
                    "1. Создаёт временный каталог `/tmp/audit_test`\n"
                    "2. Создаёт в нём `safe.conf` с правами 644 и `danger.conf` с правами 777\n"
                    "3. Находит и выводит только имя файла (без полного пути), доступного для записи всем пользователям"
                ),
                "language": "bash",
                "expected_output": "danger.conf",
                "hints": [
                    "У команды `find` есть флаг `-perm` для поиска по правам. World-writable означает, что установлен бит записи для категории «остальные».",
                    "Используйте `find /tmp/audit_test -perm -o+w`, затем передайте результат в `xargs basename`, чтобы убрать путь к каталогу.",
                ],
            },
            {
                "order_index": 2,
                "title": "Найти пользователей с повышенными привилегиями",
                "type": "sandbox",
                "prompt": (
                    "Write a bash one-liner that extracts all users with UID 0 from this `/etc/passwd` snippet "
                    "and prints each username on its own line:\n\n"
                    "```\nroot:x:0:0:root:/root:/bin/bash\n"
                    "daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\n"
                    "admin:x:0:0::/home/admin:/bin/bash\n```"
                ),
                "language": "bash",
                "expected_output": "root\nadmin",
                "hints": [
                    "В формате `/etc/passwd` поля разделены `:`. UID находится в третьем поле, имя пользователя — в первом.",
                    "Используйте `awk -F: '$3 == 0 {print $1}'`, чтобы выбрать строки с нулевым значением третьего поля и вывести имя пользователя.",
                ],
            },
            {
                "order_index": 3,
                "title": "Настроить усиленную конфигурацию SSH",
                "type": "ai",
                "prompt": (
                    "Write a production-ready `/etc/ssh/sshd_config` block with at least 8 hardening settings. "
                    "For each setting, add a one-line comment explaining why it matters.\n\n"
                    "Cover: root login, password authentication, key exchange algorithms, "
                    "session timeouts, allowed users, and port configuration."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Сосредоточьтесь на четырёх направлениях: способ аутентификации (только ключи, без паролей), доступ root, тайм-ауты бездействия и надёжные шифры/алгоритмы.",
                    "Добавьте директивы `PermitRootLogin no`, `PasswordAuthentication no`, `PubkeyAuthentication yes`, `ClientAliveInterval`, `ClientAliveCountMax`, `AllowUsers` и `KexAlgorithms`.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать ротацию журналов",
                "type": "ai",
                "prompt": (
                    "Спроектируйте полную стратегию ротации логов веб-сервера, который записывает их в `/var/log/myapp/`.\n\n"
                    "Включите:\n"
                    "1. Выражение cron для ежедневного запуска в 02:30\n"
                    "2. A bash script that compresses logs older than 7 days, deletes logs older than 30 days, "
                    "and sends a webhook alert if disk usage on the partition exceeds 80%\n\n"
                    "Объясните каждое решение, в том числе выбор сроков хранения."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Охватите все три компонента: расписание cron (поля минут и часов), команды `find -mtime` для сжатия и удаления, а также проверку `df` с передачей результата в `awk` для определения использования диска.",
                    "Выражение cron для ежедневного запуска в 02:30 — `30 2 * * *`. Используйте `find /var/log/myapp -mtime +7 -exec gzip {} \\;` для сжатия и `find ... -mtime +30 -delete` для удаления; webhook отправляйте через `curl -X POST`.",
                ],
            },
        ],
    },
    {
        "slug": "observability-stack",
        "title": "Настройка стека наблюдаемости",
        "description": "Разверните стек наблюдаемости на Prometheus и Grafana, напишите запросы PromQL и настройте оповещения.",
        "modules": ["Prometheus", "Grafana", "Docker"],
        "difficulty": "intermediate",
        "steps": [
            {
                "order_index": 1,
                "title": "Извлечь значение метрики",
                "type": "sandbox",
                "prompt": (
                    "Write a Python one-liner that parses this Prometheus text-format string and prints "
                    "the integer value for `http_requests_total` where `method=\"GET\"`:\n\n"
                    '`http_requests_total{method="GET",status="200"} 1234\\n'
                    'http_requests_total{method="POST",status="200"} 56`'
                ),
                "language": "python",
                "expected_output": "1234",
                "hints": [
                    "Split the string into lines, filter for the line containing `method=\"GET\"`, then extract the numeric value at the end.",
                    "Use a list comprehension to find lines with `method=\"GET\"`, then split on space and convert the last element to int.",
                ],
            },
            {
                "order_index": 2,
                "title": "Разобрать правило оповещения",
                "type": "sandbox",
                "prompt": (
                    "Write a Python one-liner that parses this Prometheus alerting rule YAML "
                    "and prints the alert name:\n\n"
                    "```\ngroups:\n- name: infra\n  rules:\n  - alert: InstanceDown\n"
                    "    expr: up == 0\n    for: 5m\n```"
                ),
                "language": "python",
                "expected_output": "InstanceDown",
                "hints": [
                    "Use `yaml.safe_load()` to parse the YAML string, then navigate the nested structure to find the alert name.",
                    "Access `yaml.safe_load(s)['groups'][0]['rules'][0]['alert']` after importing yaml.",
                ],
            },
            {
                "order_index": 3,
                "title": "Написать запросы PromQL",
                "type": "ai",
                "prompt": (
                    "Write PromQL queries for these three scenarios:\n"
                    "1. HTTP request rate per second over the last 5 minutes, broken down by status code\n"
                    "2. 95th percentile request latency using a histogram metric `http_request_duration_seconds`\n"
                    "3. An alerting expression that fires when any instance has been down for more than 5 minutes\n\n"
                    "Explain the difference between `rate()` and `irate()` and why you chose one over the other for query 1."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "For rate queries use `rate(metric[5m])` with `by (status_code)` aggregation; for histogram percentile use `histogram_quantile(0.95, sum(rate(..._bucket[5m])) by (le))`.",
                    "`rate()` averages over the window (smoother, better for alerting); `irate()` uses the last two points (more reactive, better for real-time graphs) — prefer `rate()` for query 1.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать стек целиком",
                "type": "ai",
                "prompt": (
                    "Write a `docker-compose.yml` that runs:\n"
                    "- Prometheus (port 9090) scraping itself and a Node Exporter\n"
                    "- Node Exporter (port 9100)\n"
                    "- Grafana (port 3000) pre-configured with Prometheus as a data source\n\n"
                    "Include: named volumes for Prometheus data and Grafana dashboards, "
                    "a minimal `prometheus.yml` scrape config as an inline comment, "
                    "and Grafana datasource provisioning via environment variables."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Define a shared network so services reach each other by name; each service needs `ports`, `volumes`, and `networks` sections.",
                    "Grafana datasource auto-provisioning: set `GF_DATASOURCES_DEFAULT_URL=http://prometheus:9090` via environment, or mount a `provisioning/datasources/prometheus.yml` file.",
                ],
            },
        ],
    },
    {
        "slug": "gitops-argocd",
        "title": "GitOps-пайплайн с Argo CD",
        "description": "Реализуйте модель GitOps-развёртывания с Argo CD: создайте манифесты Application, настройте стратегии синхронизации и спроектируйте продвижение между несколькими окружениями.",
        "modules": ["Git & VCS", "Kubernetes", "CI/CD Pipelines"],
        "difficulty": "advanced",
        "steps": [
            {
                "order_index": 1,
                "title": "Подсчитать merge-коммиты",
                "type": "sandbox",
                "prompt": (
                    "Write a bash one-liner that counts the number of merge commits in this "
                    "`git log --oneline` output and prints just the count:\n\n"
                    "```\nabc1234 Merge pull request #12 from org/feature/login\n"
                    "def5678 feat: add user dashboard\n"
                    "ghi9012 Merge pull request #11 from org/feature/signup\n"
                    "jkl3456 fix: typo in README\n```"
                ),
                "language": "bash",
                "expected_output": "2",
                "hints": [
                    "Think about what text pattern uniquely identifies a merge commit in the git log output shown.",
                    "Use `grep -c 'Merge'` to count lines containing the word 'Merge' in the input.",
                ],
            },
            {
                "order_index": 2,
                "title": "Разобрать состояние приложения Argo CD",
                "type": "sandbox",
                "prompt": (
                    "Write a Python one-liner that parses this ArgoCD Application status JSON "
                    "and prints the sync status:\n\n"
                    '`{"status":{"sync":{"status":"Synced"},"health":{"status":"Healthy"}}}`'
                ),
                "language": "python",
                "expected_output": "Synced",
                "hints": [
                    "Use `json.loads()` to parse the string, then navigate the nested dict to find the sync status field.",
                    "Access `json.loads(s)['status']['sync']['status']` after `import json`.",
                ],
            },
            {
                "order_index": 3,
                "title": "Написать манифест Application для Argo CD",
                "type": "ai",
                "prompt": (
                    "Write a complete ArgoCD `Application` manifest that:\n"
                    "- Deploys from a Git repo `https://github.com/org/k8s-manifests` path `apps/api-server`\n"
                    "- Targets the `staging` namespace on the local cluster\n"
                    "- Uses `automated` sync policy with self-healing and pruning enabled\n"
                    "- Tracks the `main` branch\n\n"
                    "Explain the difference between ArgoCD's `Synced` and `Healthy` status fields, "
                    "and what it means when a resource is `OutOfSync` but `Healthy`."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "The `Application` CRD has three main spec sections: `source` (repoURL, path, targetRevision), `destination` (server, namespace), and `syncPolicy`.",
                    "Key fields: `spec.source.targetRevision: main`, `spec.syncPolicy.automated.selfHeal: true`, `spec.syncPolicy.automated.prune: true`.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать стратегию продвижения между окружениями",
                "type": "ai",
                "prompt": (
                    "Design a GitOps multi-environment promotion workflow for dev → staging → production "
                    "using a single Git repository.\n\n"
                    "Cover:\n"
                    "1. Directory structure for environment-specific manifests\n"
                    "2. How image version promotion is triggered (manual PR vs automated image updater)\n"
                    "3. How to prevent dev changes from accidentally reaching production\n"
                    "4. What a rollback looks like in a GitOps model vs `kubectl rollout undo`\n\n"
                    "Be specific: name files, branches, or tools where relevant."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "The standard pattern is `apps/<service>/overlays/<env>` (Kustomize) or `values-<env>.yaml` (Helm); promotion means updating the image tag in the target env's config file via PR.",
                    "GitOps rollback = revert the Git commit that changed the image tag (full audit trail); `kubectl rollout undo` bypasses Git and can cause drift — use it only for emergencies.",
                ],
            },
        ],
    },
    {
        "slug": "ansible-config",
        "title": "Настройка серверов с Ansible",
        "description": "Автоматизируйте подготовку Linux-серверов с Ansible: создайте playbook, определите роли, настройте inventory и обеспечьте идемпотентную конфигурацию парка серверов.",
        "modules": ["Ansible", "Linux"],
        "difficulty": "intermediate",
        "steps": [
            {
                "order_index": 1,
                "title": "Подсчитать задачи в playbook",
                "type": "sandbox",
                "prompt": (
                    "Write a bash one-liner that counts the number of tasks in this Ansible playbook "
                    "snippet and prints just the count:\n\n"
                    "```\n- hosts: webservers\n  tasks:\n"
                    "    - name: Install nginx\n      apt:\n        name: nginx\n"
                    "    - name: Enable nginx\n      service:\n        name: nginx\n        state: started\n"
                    "    - name: Copy config\n      copy:\n        src: nginx.conf\n        dest: /etc/nginx/nginx.conf\n```"
                ),
                "language": "bash",
                "expected_output": "3",
                "hints": [
                    "Think about what unique text pattern marks the start of each task definition in the playbook snippet.",
                    "Use `grep -c '- name:'` to count lines matching the task name pattern in the input.",
                ],
            },
            {
                "order_index": 2,
                "title": "Подсчитать узлы в группе inventory",
                "type": "sandbox",
                "prompt": (
                    "Write a Python one-liner that counts the number of hosts in the `[webservers]` group "
                    "of this Ansible inventory and prints just the count:\n\n"
                    "`[webservers]\\nweb1.example.com\\nweb2.example.com\\nweb3.example.com\\n"
                    "[dbservers]\\ndb1.example.com`"
                ),
                "language": "python",
                "expected_output": "3",
                "hints": [
                    "Split the string on `\\n`, find the `[webservers]` line, then collect lines until the next group header.",
                    "Split on `\\n`, slice from the index after `[webservers]` up to the first line starting with `[`, then count the non-empty lines in that slice.",
                ],
            },
            {
                "order_index": 3,
                "title": "Создать роль Ansible для Nginx",
                "type": "ai",
                "prompt": (
                    "Write an Ansible role called `nginx` that:\n"
                    "1. Installs Nginx via the OS package manager\n"
                    "2. Deploys a Jinja2 template for `nginx.conf` with variables for `worker_processes` and `server_name`\n"
                    "3. Ensures Nginx is enabled and started\n"
                    "4. Uses a `handler` to reload Nginx only when the config changes\n\n"
                    "Show the full role directory structure with content for: `tasks/main.yml`, "
                    "`handlers/main.yml`, `templates/nginx.conf.j2`, and `defaults/main.yml`.\n\n"
                    "Explain why using a handler for config reload is preferable to an unconditional service restart."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Cover the four required files: tasks/main.yml (install + template + service), handlers/main.yml (reload), templates/nginx.conf.j2 (with `{{ worker_processes }}`), defaults/main.yml (variable defaults).",
                    "The handler is triggered by `notify: Reload nginx` on the template task; it uses `state: reloaded` (not restarted) to apply config changes without dropping connections.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать идемпотентное управление пользователями",
                "type": "ai",
                "prompt": (
                    "Write an Ansible playbook that manages a team of engineers across a fleet of servers. "
                    "The playbook should:\n"
                    "1. Create user accounts from a `users` list variable (each with name, groups, and SSH public key)\n"
                    "2. Remove users who appear in a `removed_users` list\n"
                    "3. Ensure sudo access for users in the `admins` group\n"
                    "4. Deploy each user's SSH authorized key\n\n"
                    "The playbook must be fully idempotent — running it twice must produce no changes on the second run. "
                    "Show the playbook YAML and a sample `group_vars/all.yml`. "
                    "Explain how Ansible's `user` module achieves idempotency for account management."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Use `ansible.builtin.user` (state: present/absent), `ansible.posix.authorized_key` for SSH keys, and `loop` over the `users` and `removed_users` variables.",
                    "Idempotency comes from Ansible's declarative model — `user` checks existence before creating; verify with `--check` mode which shows `changed=0` when nothing has drifted.",
                ],
            },
        ],
    },
    {
        "slug": "elk-log-pipeline",
        "title": "Анализ логов в стеке ELK",
        "description": "Создайте полный конвейер сбора логов с Logstash и Elasticsearch, напишите запросы Query DSL и спроектируйте дашборд Kibana с оповещениями.",
        "modules": ["Elasticsearch", "Logstash", "Kibana"],
        "difficulty": "advanced",
        "steps": [
            {
                "order_index": 1,
                "title": "Извлечь HTTP-статус из access-лога",
                "type": "sandbox",
                "prompt": (
                    "Write a Python one-liner that extracts the HTTP status code from this Apache access log line "
                    "and prints it:\n\n"
                    '`192.168.1.100 - admin [29/May/2026:14:22:31 +0000] "POST /api/users HTTP/1.1" 201 412`'
                ),
                "language": "python",
                "expected_output": "201",
                "hints": [
                    "The status code appears after the closing quote of the HTTP request string — think about how to split on `'\" '` to access that part.",
                    "Use `re.search(r'\" (\\d{3}) ', line).group(1)` or split on `'\" '` and take the first token of the second part.",
                ],
            },
            {
                "order_index": 2,
                "title": "Разобрать ответ запроса Elasticsearch",
                "type": "sandbox",
                "prompt": (
                    "Write a Python one-liner that parses this Elasticsearch query response and "
                    "prints the total number of matching documents:\n\n"
                    '`{"hits":{"total":{"value":247,"relation":"eq"},"hits":[]}}`'
                ),
                "language": "python",
                "expected_output": "247",
                "hints": [
                    "Use `json.loads()` to parse the string, then navigate the nested dict to find the total hits count.",
                    "Access `json.loads(s)['hits']['total']['value']` after `import json`.",
                ],
            },
            {
                "order_index": 3,
                "title": "Создать pipeline Logstash для логов Apache",
                "type": "ai",
                "prompt": (
                    "Write a complete Logstash pipeline configuration (`logstash.conf`) that:\n"
                    "1. **Input**: reads from a file `/var/log/apache2/access.log` with `sincedb_path => /dev/null`\n"
                    "2. **Filter**: uses `grok` to parse the Apache Combined Log Format, extracts `clientip`, `verb`, `request`, `response`, `bytes`; "
                    "uses `date` to parse the timestamp into `@timestamp`; adds a `geoip` lookup on `clientip`; "
                    "drops health-check requests where `request == '/health'`\n"
                    "3. **Output**: sends to Elasticsearch index `apache-logs-%%{+YYYY.MM.dd}`\n\n"
                    "Explain what the `sincedb_path => /dev/null` setting does and when you would remove it in production."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Cover the three pipeline sections: `input` (file plugin with sincedb), `filter` (grok with `%{COMBINEDAPACHELOG}` + date + geoip + conditional drop), `output` (elasticsearch plugin).",
                    "`sincedb_path => /dev/null` makes Logstash re-read the file from the start on every restart (useful for testing); remove it in production so Logstash tracks its read position.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать жизненный цикл индекса и дашборд Kibana",
                "type": "ai",
                "prompt": (
                    "Design an Elasticsearch Index Lifecycle Management (ILM) policy for the Apache log index that:\n"
                    "- Rolls over at 50GB or 30 days (whichever comes first)\n"
                    "- Moves to warm phase after 7 days (force merge to 1 segment, set replicas to 0)\n"
                    "- Deletes after 90 days\n\n"
                    "Then describe a Kibana dashboard for a web ops team — name the panels, "
                    "the visualisation type for each (e.g. area chart, data table, metric), "
                    "and what question each panel answers.\n\n"
                    "Finally, write a Kibana alerting rule that fires when the 5xx error rate "
                    "exceeds 5% over a 5-minute window."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "An ILM policy has phases: `hot` (rollover trigger), `warm` (force merge + replica reduction), `delete`; the rollover uses `max_size` and `max_age` on the hot phase.",
                    "For the Kibana dashboard, key panels: a metric tile (total requests), an area chart (request rate over time), a data table (top URLs by 5xx count), and a bar chart (status code distribution).",
                ],
            },
        ],
    },
    {
        "slug": "helm-chart",
        "title": "Разработка Helm chart",
        "description": "Создайте production-ready Helm chart для микросервиса с шаблонами, переопределением values и стратегией развёртывания в нескольких окружениях через Helm upgrade и rollback.",
        "modules": ["Helm", "Kubernetes"],
        "difficulty": "intermediate",
        "steps": [
            {
                "order_index": 1,
                "title": "Создать структуру каталога Helm chart",
                "type": "sandbox",
                "prompt": (
                    "Write a bash script that creates a minimal Helm chart directory at `/tmp/mychart` with "
                    "exactly 3 template files (`deployment.yaml`, `service.yaml`, `ingress.yaml`) inside `templates/`, "
                    "then prints the count of `.yaml` files in that directory."
                ),
                "language": "bash",
                "expected_output": "3",
                "hints": [
                    "Create the directory with `mkdir -p /tmp/mychart/templates`, create the three files with `touch`, then count with `find`.",
                    "Use `find /tmp/mychart/templates -name '*.yaml' | wc -l` to count YAML files, stripping the trailing filename with `awk '{print $1}'` if needed.",
                ],
            },
            {
                "order_index": 2,
                "title": "Разобрать YAML values Helm",
                "type": "sandbox",
                "prompt": (
                    "Write a Python one-liner that parses this Helm `values.yaml` content and prints the replica count:\n\n"
                    "`replicaCount: 3\\nimage:\\n  repository: nginx\\n  tag: \\\"1.24\\\"\\nservice:\\n  port: 80`"
                ),
                "language": "python",
                "expected_output": "3",
                "hints": [
                    "Use `yaml.safe_load()` on the string — the `\\n` sequences are real newlines that YAML parses into a nested dict.",
                    "Access `yaml.safe_load(s)['replicaCount']` after `import yaml`, where `s` is the values string with `\\n` as actual newline characters.",
                ],
            },
            {
                "order_index": 3,
                "title": "Создать Helm chart для stateless-сервиса",
                "type": "ai",
                "prompt": (
                    "Write a Helm chart for a stateless web service called `api-server`. "
                    "Show the content of these files:\n\n"
                    "1. `Chart.yaml` — with `apiVersion: v2`, name, version, and appVersion\n"
                    "2. `values.yaml` — with defaults for replicaCount, image (repository + tag + pullPolicy), "
                    "service (type + port), resources (requests + limits), and ingress (enabled flag, host, tls)\n"
                    "3. `templates/deployment.yaml` — templated with `{{ .Values.* }}` references, "
                    "including resource limits and a liveness probe\n"
                    "4. `templates/service.yaml` — ClusterIP service using `{{ .Values.service.port }}`\n\n"
                    "Use `{{ include \"api-server.fullname\" . }}` for naming and show the `_helpers.tpl` snippet "
                    "that defines it."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "The `_helpers.tpl` defines named templates with `{{- define \"api-server.fullname\" -}}`; the deployment uses `{{ include \"api-server.fullname\" . }}` for the name and `{{ include \"api-server.labels\" . | nindent 4 }}` for labels.",
                    "In `values.yaml` set `replicaCount: 1` and `image.pullPolicy: IfNotPresent`; wrap the ingress section in `deployment.yaml` with `{{- if .Values.ingress.enabled }}` and add resources from `{{ toYaml .Values.resources | nindent 12 }}`.",
                ],
            },
            {
                "order_index": 4,
                "title": "Управление values и релизами в нескольких окружениях",
                "type": "ai",
                "prompt": (
                    "Describe a strategy for deploying the same Helm chart to dev, staging, and production "
                    "environments with different values.\n\n"
                    "1. Show the file structure for per-environment values files\n"
                    "2. Write the `helm upgrade --install` commands for each environment, "
                    "explaining the flags used\n"
                    "3. Explain what `helm rollback` does vs manually reverting the values file in Git — "
                    "when would you use each?\n"
                    "4. What does `helm diff upgrade` (from the helm-diff plugin) tell you, "
                    "and why should it be part of every CI pipeline that deploys via Helm?"
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Standard pattern: `values.yaml` (base defaults), `values-dev.yaml`, `values-staging.yaml`, `values-prod.yaml`; override with `helm upgrade --install -f values-<env>.yaml`.",
                    "`helm rollback` reverts cluster state using Helm's release history (fast, emergency use); reverting the Git values file is the GitOps approach with audit trail — prefer Git revert for planned rollbacks.",
                ],
            },
        ],
    },
    {
        "slug": "api-security-testing",
        "title": "Безопасность и тестирование API",
        "description": "Спроектируйте и реализуйте комплексную стратегию тестирования API: проверьте сценарии аутентификации, уязвимости OWASP API и автоматизируйте проверки безопасности в CI.",
        "modules": ["Postman / API Testing", "DevSecOps"],
        "difficulty": "intermediate",
        "steps": [
            {
                "order_index": 1,
                "title": "Проверить структуру JWT",
                "type": "sandbox",
                "prompt": (
                    "Write a bash one-liner that prints the number of parts in this JWT "
                    "(a valid JWT has exactly 3 parts separated by dots):\n\n"
                    "`eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
                    ".eyJzdWIiOiJ1c2VyMTIzIn0"
                    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c`"
                ),
                "language": "bash",
                "expected_output": "3",
                "hints": [
                    "A JWT has 3 parts separated by `.` — think about counting the separators and adding 1, or counting fields directly.",
                    "Use `echo 'JWT' | awk -F. '{print NF}'` to split on `.` and print the number of fields.",
                ],
            },
            {
                "order_index": 2,
                "title": "Декодировать payload JWT",
                "type": "sandbox",
                "prompt": (
                    "Write a Python one-liner that base64-decodes the middle segment of this JWT "
                    "and prints the value of the `sub` field:\n\n"
                    "`eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
                    ".eyJzdWIiOiJ1c2VyMTIzIn0"
                    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c`\n\n"
                    "Hint: split on `.`, take index 1, use `base64.urlsafe_b64decode` — "
                    "add `'=' * (-len(payload) % 4)` to fix padding."
                ),
                "language": "python",
                "expected_output": "user123",
                "hints": [
                    "Split the JWT on `.`, take index 1 (the payload segment), and base64url-decode it — the standard `base64.urlsafe_b64decode` needs padding added first.",
                    "Padding fix: `base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4))`; then `json.loads()` the result and access `['sub']`.",
                ],
            },
            {
                "order_index": 3,
                "title": "Создать коллекцию Postman для API аутентификации",
                "type": "ai",
                "prompt": (
                    "Write a Postman collection (JSON) for an authentication API with these three requests:\n\n"
                    "1. **POST /auth/login** — body `{email, password}`, test that response status is 200 "
                    "and response body contains a `token` field; save the token to a collection variable\n"
                    "2. **GET /api/profile** — uses the saved token as a Bearer header; "
                    "test that status is 200 and response body contains `email`\n"
                    "3. **POST /auth/login (invalid)** — wrong password; test that status is 401 "
                    "and error message is present\n\n"
                    "Show the pre-request scripts and test scripts for each request. "
                    "Explain why you'd put the token in a collection variable rather than hardcoding it."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "A Postman collection JSON has an `info` block (name, schema) and an `item` array; each item has `name`, `request`, and `event` arrays for pre-request and test scripts.",
                    "In the login test script: `pm.collectionVariables.set('token', pm.response.json().token)`; reference it in the profile request `Authorization` header as `Bearer {{token}}`.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать стратегию тестирования безопасности API",
                "type": "ai",
                "prompt": (
                    "Design an API security testing strategy covering these OWASP API Security Top 10 risks:\n\n"
                    "- **API1** (Broken Object Level Authorization): describe a test scenario and how to automate it\n"
                    "- **API3** (Broken Object Property Level Authorization): give a concrete example using a PATCH endpoint\n"
                    "- **API5** (Broken Function Level Authorization): explain how to find and test admin-only endpoints\n"
                    "- **API8** (Security Misconfiguration): list 5 headers or settings to check in every response\n\n"
                    "Then describe how you would integrate these checks into a CI pipeline using Newman "
                    "(the Postman CLI runner), so that a failing security test blocks the PR."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "For BOLA (API1): substitute another user's resource ID in the URL and assert a 403 response — if you get 200, authorization is broken. Automate by parameterizing resource IDs in Postman.",
                    "For Newman CI integration: `newman run collection.json -e env.json --bail` exits non-zero on test failure; add it as a CI step after deploying to staging so security failures block the PR.",
                ],
            },
        ],
    },
    {
        "slug": "iac-aws-vpc",
        "title": "Infrastructure as Code: AWS VPC",
        "description": "Напишите Terraform-конфигурацию для production-ready AWS VPC с подсетями и security groups, затем выделите конфигурацию в повторно используемый модуль.",
        "modules": ["Terraform", "AWS", "Networking Essentials"],
        "difficulty": "advanced",
        "steps": [
            {
                "order_index": 1,
                "title": "Подсчитать блоки переменных Terraform",
                "type": "sandbox",
                "prompt": (
                    "Write a bash one-liner that counts the number of `variable` blocks in this HCL snippet "
                    "and prints just the count:\n\n"
                    "```\nvariable \"region\" { default = \"us-east-1\" }\n"
                    "variable \"env\" { default = \"prod\" }\n"
                    "variable \"cidr\" { default = \"10.0.0.0/16\" }\n```"
                ),
                "language": "bash",
                "expected_output": "3",
                "hints": [
                    "Think about what unique keyword starts each variable block definition in HCL — you can count lines that begin with it.",
                    "Use `grep -c '^variable'` to count lines where the word `variable` appears at the start.",
                ],
            },
            {
                "order_index": 2,
                "title": "Разобрать JSON-вывод Terraform",
                "type": "sandbox",
                "prompt": (
                    "Write a Python one-liner that parses this Terraform output JSON and prints the VPC ID value:\n\n"
                    '`{"vpc_id":{"value":"vpc-0abc1234","type":"string"}}`'
                ),
                "language": "python",
                "expected_output": "vpc-0abc1234",
                "hints": [
                    "Use `json.loads()` to parse the string, then navigate the nested dict to find the value field.",
                    "Access `json.loads(s)['vpc_id']['value']` after `import json`.",
                ],
            },
            {
                "order_index": 3,
                "title": "Создать повторно используемый модуль VPC",
                "type": "ai",
                "prompt": (
                    "Write a Terraform module for a production AWS VPC. "
                    "The module should accept variables for: CIDR block, environment name, and list of AZs.\n\n"
                    "It should create:\n"
                    "- The VPC with DNS hostnames enabled\n"
                    "- One public subnet per AZ\n"
                    "- One private subnet per AZ\n"
                    "- An internet gateway attached to public subnets\n"
                    "- A NAT gateway in the first public subnet (with an Elastic IP)\n"
                    "- Appropriate route tables for public and private subnets\n\n"
                    "Show `main.tf`, `variables.tf`, and `outputs.tf`. "
                    "Use consistent naming with the environment variable."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Use `count = length(var.azs)` on subnet resources; the NAT gateway requires an `aws_eip` first; route tables need separate `aws_route_table_association` resources to attach to subnets.",
                    "Private subnets route `0.0.0.0/0` to `aws_nat_gateway.main.id`; public subnets route to `aws_internet_gateway.main.id`; both need `aws_route_table` + `aws_route_table_association`.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать security group",
                "type": "ai",
                "prompt": (
                    "Write Terraform `aws_security_group` resources for a 3-tier application:\n"
                    "1. **Web tier** — allows HTTP (80) and HTTPS (443) from anywhere; SSH (22) from a bastion CIDR only\n"
                    "2. **App tier** — allows traffic only from the web tier security group on port 8080\n"
                    "3. **Database tier** — allows PostgreSQL (5432) only from the app tier security group\n\n"
                    "Use security group references (not CIDR) for inter-tier rules. "
                    "Explain why security group references are preferable to CIDR-based rules for internal traffic."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Define security groups in dependency order (web → app → db); use `source_security_group_id = aws_security_group.web.id` in the app tier ingress rule instead of `cidr_blocks`.",
                    "Security group references are dynamic — they follow the group regardless of IP changes, so they're more robust than CIDR rules that break when instances are replaced or scaled.",
                ],
            },
        ],
    },
]


def seed_projects():
    conn = get_conn()
    try:
        for p in PROJECTS:
            existing = conn.execute(
                "SELECT id FROM projects WHERE slug = ?", (p["slug"],)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO projects (slug, title, description, modules, difficulty) VALUES (?, ?, ?, ?, ?)",
                    (p["slug"], p["title"], p["description"], json.dumps(p["modules"]), p["difficulty"]),
                )
                project_id = conn.execute(
                    "SELECT id FROM projects WHERE slug = ?", (p["slug"],)
                ).fetchone()["id"]
                for step in p["steps"]:
                    conn.execute(
                        "INSERT INTO project_steps "
                        "(project_id, order_index, title, type, prompt, language, expected_output, hints) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            project_id,
                            step["order_index"],
                            step["title"],
                            step["type"],
                            step["prompt"],
                            step.get("language"),
                            step.get("expected_output"),
                            json.dumps(step.get("hints", [])),
                        ),
                    )
            else:
                project_id = existing["id"]

            # Always apply hint updates (idempotent — safe to re-run)
            for step in p["steps"]:
                conn.execute(
                    "UPDATE project_steps SET hints = ? WHERE project_id = ? AND order_index = ?",
                    (json.dumps(step.get("hints", [])), project_id, step["order_index"]),
                )

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    seed_projects()
    print("Projects seeded.")
