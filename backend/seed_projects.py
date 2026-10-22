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
                    "Определите, какое поле в выводе, разделённом пробелами, содержит имя образа.",
                    "Используйте `awk '{print $NF}'`, чтобы вывести последнее поле строки.",
                ],
            },
            {
                "order_index": 2,
                "title": "Разобрать JSON состояния Pod",
                "type": "sandbox",
                "prompt": (
                    "Напишите однострочную Bash-команду с Python, которая разбирает этот JSON и выводит фазу Pod:\n\n"
                    '`{"status":{"phase":"Running","hostIP":"10.0.0.1"}}`'
                ),
                "language": "bash",
                "expected_output": "Running",
                "hints": [
                    "Передайте JSON-строку в однострочную команду Python, которая читает stdin и обращается к полям разобранного словаря.",
                    "Try `echo '{...}' | python3 -c \"import sys,json; print(json.loads(sys.stdin.read())['status']['phase'])\"`.",
                ],
            },
            {
                "order_index": 3,
                "title": "Написать манифест Deployment",
                "type": "ai",
                "prompt": (
                    "Напишите полный манифест Deployment Kubernetes для приложения `api-server`, который включает:\n"
                    "- 3 реплики\n"
                    "- Стратегию rolling update: `maxSurge: 1`, `maxUnavailable: 0`\n"
                    "- requests и limits для CPU и памяти\n"
                    "- HTTP readiness probe для `/health` на порту 8080 с подходящим `initialDelaySeconds`\n"
                    "- HTTP liveness probe, предоставляющую Pod 30 секунд на запуск\n\n"
                    "Объясните выбор параметров readiness- и liveness-проб."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Добавьте три ключевые секции: `spec.strategy.rollingUpdate`, `readinessProbe` и `livenessProbe` контейнера; для обеих проб используйте `httpGet` на `/health`, порт 8080.",
                    "Для развёртывания без простоя задайте `maxUnavailable: 0`, чтобы Pod не удалялся до готовности замены. Значение `initialDelaySeconds` для readiness должно соответствовать реальному времени прогрева приложения.",
                ],
            },
            {
                "order_index": 4,
                "title": "Сравнить readiness- и liveness-пробы",
                "type": "ai",
                "prompt": (
                    "Объясните разницу между readiness- и liveness-пробами Kubernetes.\n\n"
                    "Specifically: describe a realistic scenario where a pod fails a readiness check but passes "
                    "a liveness check — and why that distinction matters for zero-downtime deployments.\n\n"
                    "Then write probe definitions for a service that has a 30-second startup warmup "
                    "but must be ready within 60 seconds of launch."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Readiness управляет маршрутизацией трафика (Pod удаляется из endpoints Service), а liveness управляет перезапусками. Ошибка каждой пробы имеет разные последствия.",
                    "Пример: Pod загружает большой кэш, поэтому не проходит readiness (трафик не поступает), но проходит liveness (перезапуск не нужен). Трафик временно не направляется в Pod, но сам Pod продолжает работать.",
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
                    "Разберите YAML-строку с помощью `yaml.safe_load()`, затем пройдите по вложенной структуре до имени оповещения.",
                    "После импорта `yaml` обратитесь к `yaml.safe_load(s)['groups'][0]['rules'][0]['alert']`.",
                ],
            },
            {
                "order_index": 3,
                "title": "Написать запросы PromQL",
                "type": "ai",
                "prompt": (
                    "Напишите запросы PromQL для трёх сценариев:\n"
                    "1. Частота HTTP-запросов в секунду за последние пять минут с группировкой по коду состояния\n"
                    "2. 95-й перцентиль задержки запросов с использованием гистограммы `http_request_duration_seconds`\n"
                    "3. Выражение оповещения, срабатывающее, если любой экземпляр недоступен более пяти минут\n\n"
                    "Объясните разницу между `rate()` и `irate()` и почему для первого запроса вы выбрали одну из этих функций."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Для скорости используйте `rate(metric[5m])` с агрегацией `by (status_code)`. Для перцентиля гистограммы примените `histogram_quantile(0.95, sum(rate(..._bucket[5m])) by (le))`.",
                    "`rate()` усредняет значение по окну (график стабильнее, подходит для оповещений); `irate()` использует две последние точки (быстрее реагирует, подходит для графиков реального времени). Для первого запроса предпочтительнее `rate()`.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать стек целиком",
                "type": "ai",
                "prompt": (
                    "Создайте `docker-compose.yml`, запускающий:\n"
                    "- Prometheus на порту 9090, собирающий метрики с себя и Node Exporter\n"
                    "- Node Exporter на порту 9100\n"
                    "- Grafana на порту 3000 с предварительно настроенным Prometheus в качестве источника данных\n\n"
                    "Include: named volumes for Prometheus data and Grafana dashboards, "
                    "a minimal `prometheus.yml` scrape config as an inline comment, "
                    "and Grafana datasource provisioning via environment variables."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Определите общую сеть, чтобы сервисы обращались друг к другу по имени. Для каждого сервиса нужны секции `ports`, `volumes` и `networks`.",
                    "Для автоматической настройки источника Grafana задайте переменную `GF_DATASOURCES_DEFAULT_URL=http://prometheus:9090` либо подключите файл `provisioning/datasources/prometheus.yml`.",
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
                    "Определите текстовый шаблон, однозначно обозначающий merge-коммит в приведённом выводе git log.",
                    "Используйте `grep -c 'Merge'`, чтобы подсчитать строки, содержащие слово `Merge`.",
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
                    "Разберите строку через `json.loads()`, затем пройдите по вложенному словарю до поля состояния синхронизации.",
                    "После `import json` обратитесь к `json.loads(s)['status']['sync']['status']`.",
                ],
            },
            {
                "order_index": 3,
                "title": "Написать манифест Application для Argo CD",
                "type": "ai",
                "prompt": (
                    "Напишите полный манифест `Application` для Argo CD, который:\n"
                    "- Развёртывает приложение из Git-репозитория `https://github.com/org/k8s-manifests`, каталог `apps/api-server`\n"
                    "- Использует namespace `staging` в локальном кластере\n"
                    "- Использует политику синхронизации `automated` с включёнными self-healing и pruning\n"
                    "- Отслеживает ветку `main`\n\n"
                    "Explain the difference between ArgoCD's `Synced` and `Healthy` status fields, "
                    "and what it means when a resource is `OutOfSync` but `Healthy`."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "CRD `Application` содержит три основные секции `spec`: `source` (repoURL, path, targetRevision), `destination` (server, namespace) и `syncPolicy`.",
                    "Ключевые поля: `spec.source.targetRevision: main`, `spec.syncPolicy.automated.selfHeal: true`, `spec.syncPolicy.automated.prune: true`.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать стратегию продвижения между окружениями",
                "type": "ai",
                "prompt": (
                    "Design a GitOps multi-environment promotion workflow for dev → staging → production "
                    "using a single Git repository.\n\n"
                    "Рассмотрите:\n"
                    "1. Структуру каталогов для манифестов каждого окружения\n"
                    "2. Как запускается продвижение версии образа (ручной PR или автоматический image updater)\n"
                    "3. Как не допустить случайного попадания изменений dev в production\n"
                    "4. Как выполняется откат в GitOps по сравнению с `kubectl rollout undo`\n\n"
                    "Будьте конкретны: укажите имена файлов, веток и инструментов, где это уместно."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Стандартный шаблон — `apps/<service>/overlays/<env>` для Kustomize или `values-<env>.yaml` для Helm. Продвижение означает обновление тега образа в конфигурации целевого окружения через PR.",
                    "Откат в GitOps — это отмена Git-коммита, изменившего тег образа, с полной историей аудита. `kubectl rollout undo` обходит Git и может вызвать drift, поэтому используйте его только в экстренных случаях.",
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
                    "Определите уникальный текстовый шаблон, с которого начинается описание каждой задачи в playbook.",
                    "Используйте `grep -c '- name:'`, чтобы подсчитать строки с шаблоном имени задачи.",
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
                    "Разделите строку по `\\n`, найдите строку `[webservers]`, затем соберите строки до следующего заголовка группы.",
                    "Разделите строку по `\\n`, возьмите фрагмент после `[webservers]` до первой строки, начинающейся с `[`, и подсчитайте непустые строки.",
                ],
            },
            {
                "order_index": 3,
                "title": "Создать роль Ansible для Nginx",
                "type": "ai",
                "prompt": (
                    "Создайте роль Ansible `nginx`, которая:\n"
                    "1. Устанавливает Nginx через менеджер пакетов ОС\n"
                    "2. Развёртывает шаблон Jinja2 для `nginx.conf` с переменными `worker_processes` и `server_name`\n"
                    "3. Включает автозапуск Nginx и запускает службу\n"
                    "4. Использует `handler` для перезагрузки Nginx только при изменении конфигурации\n\n"
                    "Show the full role directory structure with content for: `tasks/main.yml`, "
                    "`handlers/main.yml`, `templates/nginx.conf.j2`, and `defaults/main.yml`.\n\n"
                    "Объясните, почему handler для перезагрузки конфигурации лучше безусловного перезапуска службы."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Покажите четыре файла: tasks/main.yml (установка, шаблон и служба), handlers/main.yml (перезагрузка), templates/nginx.conf.j2 (с `{{ worker_processes }}`) и defaults/main.yml (значения переменных по умолчанию).",
                    "Шаблонная задача вызывает handler через `notify: Reload nginx`. Для применения конфигурации используйте `state: reloaded`, а не `restarted`, чтобы не разрывать соединения.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать идемпотентное управление пользователями",
                "type": "ai",
                "prompt": (
                    "Write an Ansible playbook that manages a team of engineers across a fleet of servers. "
                    "The playbook should:\n"
                    "1. Создавать пользователей из списка `users` (для каждого заданы имя, группы и публичный SSH-ключ)\n"
                    "2. Удалять пользователей из списка `removed_users`\n"
                    "3. Обеспечивать доступ через sudo пользователям группы `admins`\n"
                    "4. Устанавливать авторизованный SSH-ключ каждого пользователя\n\n"
                    "The playbook must be fully idempotent — running it twice must produce no changes on the second run. "
                    "Show the playbook YAML and a sample `group_vars/all.yml`. "
                    "Explain how Ansible's `user` module achieves idempotency for account management."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Используйте `ansible.builtin.user` с `state: present/absent`, `ansible.posix.authorized_key` для SSH-ключей и `loop` по переменным `users` и `removed_users`.",
                    "Идемпотентность обеспечивается декларативной моделью Ansible: модуль `user` проверяет наличие пользователя перед созданием. Проверьте это через `--check`: при отсутствии drift результат должен показывать `changed=0`.",
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
                    "Разберите строку через `json.loads()`, затем найдите общее число совпадений во вложенном словаре.",
                    "После `import json` обратитесь к `json.loads(s)['hits']['total']['value']`.",
                ],
            },
            {
                "order_index": 3,
                "title": "Создать pipeline Logstash для логов Apache",
                "type": "ai",
                "prompt": (
                    "Напишите полную конфигурацию pipeline Logstash (`logstash.conf`), которая:\n"
                    "1. **Input**: читает файл `/var/log/apache2/access.log` с параметром `sincedb_path => /dev/null`\n"
                    "2. **Filter**: uses `grok` to parse the Apache Combined Log Format, extracts `clientip`, `verb`, `request`, `response`, `bytes`; "
                    "uses `date` to parse the timestamp into `@timestamp`; adds a `geoip` lookup on `clientip`; "
                    "drops health-check requests where `request == '/health'`\n"
                    "3. **Output**: отправляет данные в индекс Elasticsearch `apache-logs-%%{+YYYY.MM.dd}`\n\n"
                    "Объясните, что делает настройка `sincedb_path => /dev/null` и почему в production её следует убрать."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Опишите три секции pipeline: `input` (file-плагин с sincedb), `filter` (`grok` с `%{COMBINEDAPACHELOG}`, date, geoip и условным отбрасыванием), `output` (плагин Elasticsearch).",
                    "`sincedb_path => /dev/null` заставляет Logstash перечитывать файл с начала при каждом перезапуске, что удобно для тестов. В production уберите этот параметр, чтобы Logstash сохранял позицию чтения.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать жизненный цикл индекса и дашборд Kibana",
                "type": "ai",
                "prompt": (
                    "Спроектируйте политику Index Lifecycle Management (ILM) для индекса логов Apache, которая:\n"
                    "- Выполняет rollover при достижении 50 ГБ или 30 дней — в зависимости от того, что наступит раньше\n"
                    "- Переводит индекс в фазу warm через 7 дней (force merge до одного сегмента, число реплик — 0)\n"
                    "- Удаляет индекс через 90 дней\n\n"
                    "Then describe a Kibana dashboard for a web ops team — name the panels, "
                    "the visualisation type for each (e.g. area chart, data table, metric), "
                    "and what question each panel answers.\n\n"
                    "Finally, write a Kibana alerting rule that fires when the 5xx error rate "
                    "exceeds 5% over a 5-minute window."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Политика ILM состоит из фаз `hot` (условие rollover), `warm` (force merge и уменьшение числа реплик) и `delete`. В фазе hot для rollover используются `max_size` и `max_age`.",
                    "Для дашборда Kibana добавьте основные панели: метрику общего числа запросов, area chart частоты запросов во времени, таблицу URL с наибольшим количеством ошибок 5xx и bar chart распределения кодов состояния.",
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
                    "Создайте каталог командой `mkdir -p /tmp/mychart/templates`, создайте три файла через `touch`, затем подсчитайте их с помощью `find`.",
                    "Используйте `find /tmp/mychart/templates -name '*.yaml' | wc -l` для подсчёта YAML-файлов; при необходимости уберите лишнее поле через `awk '{print $1}'`.",
                ],
            },
            {
                "order_index": 2,
                "title": "Разобрать YAML values Helm",
                "type": "sandbox",
                "prompt": (
                    "Напишите однострочную команду Python, которая разбирает содержимое Helm `values.yaml` и выводит количество реплик:\n\n"
                    "`replicaCount: 3\\nimage:\\n  repository: nginx\\n  tag: \\\"1.24\\\"\\nservice:\\n  port: 80`"
                ),
                "language": "python",
                "expected_output": "3",
                "hints": [
                    "Передайте строку в `yaml.safe_load()`: последовательности `\\n` становятся переводами строк, а YAML преобразуется во вложенный словарь.",
                    "После `import yaml` обратитесь к `yaml.safe_load(s)['replicaCount']`, где `s` — строка values с реальными переводами строк.",
                ],
            },
            {
                "order_index": 3,
                "title": "Создать Helm chart для stateless-сервиса",
                "type": "ai",
                "prompt": (
                    "Write a Helm chart for a stateless web service called `api-server`. "
                    "Show the content of these files:\n\n"
                    "1. `Chart.yaml` — с `apiVersion: v2`, именем, версией chart и версией приложения\n"
                    "2. `values.yaml` — with defaults for replicaCount, image (repository + tag + pullPolicy), "
                    "service (type + port), resources (requests + limits), and ingress (enabled flag, host, tls)\n"
                    "3. `templates/deployment.yaml` — templated with `{{ .Values.* }}` references, "
                    "including resource limits and a liveness probe\n"
                    "4. `templates/service.yaml` — сервис ClusterIP с использованием `{{ .Values.service.port }}`\n\n"
                    "Use `{{ include \"api-server.fullname\" . }}` for naming and show the `_helpers.tpl` snippet "
                    "that defines it."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "The `_helpers.tpl` defines named templates with `{{- define \"api-server.fullname\" -}}`; the deployment uses `{{ include \"api-server.fullname\" . }}` for the name and `{{ include \"api-server.labels\" . | nindent 4 }}` for labels.",
                    "В `values.yaml` задайте `replicaCount: 1` и `image.pullPolicy: IfNotPresent`. Оберните ingress-раздел в `deployment.yaml` условием `{{- if .Values.ingress.enabled }}` и добавьте ресурсы через `{{ toYaml .Values.resources | nindent 12 }}`.",
                ],
            },
            {
                "order_index": 4,
                "title": "Управление values и релизами в нескольких окружениях",
                "type": "ai",
                "prompt": (
                    "Describe a strategy for deploying the same Helm chart to dev, staging, and production "
                    "environments with different values.\n\n"
                    "1. Покажите структуру файлов values для каждого окружения\n"
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
                    "Стандартная схема: `values.yaml` со значениями по умолчанию, `values-dev.yaml`, `values-staging.yaml`, `values-prod.yaml`. Переопределяйте значения через `helm upgrade --install -f values-<env>.yaml`.",
                    "`helm rollback` восстанавливает состояние кластера по истории релизов Helm и подходит для экстренного отката. Возврат values-файла в Git — подход GitOps с полной историей аудита; для плановых откатов предпочтителен `git revert`.",
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
                    "JWT состоит из трёх частей, разделённых `.`. Можно подсчитать разделители и прибавить 1 либо сразу посчитать поля.",
                    "Используйте `echo 'JWT' | awk -F. '{print NF}'`, чтобы разделить строку по `.` и вывести число полей.",
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
                    "Разделите JWT по `.`, возьмите элемент с индексом 1 (payload) и декодируйте Base64url. Перед вызовом `base64.urlsafe_b64decode` нужно добавить padding.",
                    "Исправление padding: `base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4))`; затем разберите результат через `json.loads()` и обратитесь к `['sub']`.",
                ],
            },
            {
                "order_index": 3,
                "title": "Создать коллекцию Postman для API аутентификации",
                "type": "ai",
                "prompt": (
                    "Создайте коллекцию Postman в формате JSON для API аутентификации с тремя запросами:\n\n"
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
                    "JSON-коллекция Postman содержит блок `info` (name, schema) и массив `item`. Каждый элемент включает `name`, `request` и массив `event` с pre-request- и test-скриптами.",
                    "В тестовом скрипте входа используйте `pm.collectionVariables.set('token', pm.response.json().token)`. В запросе профиля укажите в заголовке `Authorization`: `Bearer {{token}}`.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать стратегию тестирования безопасности API",
                "type": "ai",
                "prompt": (
                    "Спроектируйте стратегию тестирования безопасности API, охватывающую следующие риски OWASP API Security Top 10:\n\n"
                    "- **API1** (Broken Object Level Authorization): опишите сценарий тестирования и его автоматизацию\n"
                    "- **API3** (Broken Object Property Level Authorization): приведите конкретный пример с endpoint PATCH\n"
                    "- **API5** (Broken Function Level Authorization): объясните, как найти и проверить endpoint, доступные только администраторам\n"
                    "- **API8** (Security Misconfiguration): перечислите пять заголовков или настроек, которые нужно проверять в каждом ответе\n\n"
                    "Then describe how you would integrate these checks into a CI pipeline using Newman "
                    "(the Postman CLI runner), so that a failing security test blocks the PR."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Для BOLA (API1) подставьте в URL ID ресурса другого пользователя и проверьте ответ 403. Если приходит 200, авторизация работает неправильно. Автоматизируйте тест, параметризовав ID ресурсов в Postman.",
                    "Для интеграции Newman с CI используйте `newman run collection.json -e env.json --bail`: при провале теста команда вернёт ненулевой код. Добавьте шаг после развёртывания в staging, чтобы ошибки безопасности блокировали PR.",
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
                    "Вспомните ключевое слово, с которого начинается определение каждой переменной в HCL. Можно подсчитать строки, начинающиеся с него.",
                    "Используйте `grep -c '^variable'`, чтобы подсчитать строки, начинающиеся со слова `variable`.",
                ],
            },
            {
                "order_index": 2,
                "title": "Разобрать JSON-вывод Terraform",
                "type": "sandbox",
                "prompt": (
                    "Напишите однострочную команду Python, которая разбирает JSON-вывод Terraform и печатает ID VPC:\n\n"
                    '`{"vpc_id":{"value":"vpc-0abc1234","type":"string"}}`'
                ),
                "language": "python",
                "expected_output": "vpc-0abc1234",
                "hints": [
                    "Разберите строку через `json.loads()`, затем найдите поле `value` во вложенном словаре.",
                    "После `import json` обратитесь к `json.loads(s)['vpc_id']['value']`.",
                ],
            },
            {
                "order_index": 3,
                "title": "Создать повторно используемый модуль VPC",
                "type": "ai",
                "prompt": (
                    "Write a Terraform module for a production AWS VPC. "
                    "The module should accept variables for: CIDR block, environment name, and list of AZs.\n\n"
                    "Модуль должен создавать:\n"
                    "- VPC с включёнными DNS hostnames\n"
                    "- Одну публичную подсеть для каждой AZ\n"
                    "- Одну приватную подсеть для каждой AZ\n"
                    "- Internet Gateway для публичных подсетей\n"
                    "- NAT Gateway в первой публичной подсети с Elastic IP\n"
                    "- Подходящие таблицы маршрутизации для публичных и приватных подсетей\n\n"
                    "Show `main.tf`, `variables.tf`, and `outputs.tf`. "
                    "Use consistent naming with the environment variable."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Для ресурсов подсетей используйте `count = length(var.azs)`. Перед созданием NAT Gateway создайте `aws_eip`. Для подключения таблиц маршрутизации к подсетям нужны отдельные ресурсы `aws_route_table_association`.",
                    "В приватных подсетях направьте `0.0.0.0/0` на `aws_nat_gateway.main.id`, в публичных — на `aws_internet_gateway.main.id`. Для обоих типов нужны `aws_route_table` и `aws_route_table_association`.",
                ],
            },
            {
                "order_index": 4,
                "title": "Спроектировать security group",
                "type": "ai",
                "prompt": (
                    "Создайте ресурсы Terraform `aws_security_group` для трёхуровневого приложения:\n"
                    "1. **Web tier** — разрешает HTTP (80) и HTTPS (443) отовсюду, SSH (22) — только из CIDR bastion-хоста\n"
                    "2. **App tier** — разрешает трафик только от security group веб-уровня на порту 8080\n"
                    "3. **Database tier** — разрешает PostgreSQL (5432) только от security group уровня приложения\n\n"
                    "Use security group references (not CIDR) for inter-tier rules. "
                    "Explain why security group references are preferable to CIDR-based rules for internal traffic."
                ),
                "language": None,
                "expected_output": None,
                "hints": [
                    "Определяйте группы безопасности в порядке зависимостей (web → app → db). В ingress-правиле app-уровня используйте `source_security_group_id = aws_security_group.web.id` вместо `cidr_blocks`.",
                    "Ссылки на security group динамические: они учитывают изменения IP-адресов и устойчивее CIDR-правил, которые могут перестать работать при замене или масштабировании экземпляров.",
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
