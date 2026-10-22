---
title: Создание собственных Helm chart
module: helm
duration_min: 25
difficulty: advanced
tags: [helm, custom-charts, subcharts, hooks, tests, library-charts]
exercises: 4
---

## Обзор
Создание собственных Helm chart позволяет точно контролировать развёртывание, тестирование и обновление приложения в разных окружениях. В уроке рассматриваются практики для production: hooks для миграций базы данных, тесты chart, библиотечные chart с общими шаблонами и управление зависимостями через subcharts.

## Основные понятия

### Hooks — хуки жизненного цикла
Hooks запускают задания Job в определённые моменты жизненного цикла релиза:

| Hook | Когда запускается |
|---|---|
| `pre-install` | До создания ресурсов |
| `post-install` | После создания всех ресурсов |
| `pre-upgrade` | До обновления ресурсов |
| `post-upgrade` | После обновления ресурсов |
| `pre-delete` | До удаления ресурсов |
| `post-delete` | После удаления ресурсов |
| `pre-rollback` | До отката |
| `test` | Только при запуске `helm test` |

```yaml
# templates/hooks/db-migrate.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ .Release.Name }}-db-migrate
  annotations:
    "helm.sh/hook": pre-upgrade,pre-install
    "helm.sh/hook-weight": "-5"           # lower = runs first (can be negative)
    "helm.sh/hook-delete-policy": hook-succeeded   # delete job after success
spec:
  backoffLimit: 3
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: migrate
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          command: ["python", "manage.py", "migrate"]
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: {{ .Release.Name }}-secrets
                  key: DATABASE_URL
```

Политики удаления hook:
- `hook-succeeded` — удалить после успешного завершения Job, запущенного hook
- `hook-failed` — удалить, если hook завершился с ошибкой (при успехе оставить для проверки)
- `before-hook-creation` — удалить предыдущий hook перед запуском нового (значение по умолчанию)

### Тестирование chart
Тесты — это pod с аннотацией `helm.sh/hook: test`. Они запускаются командой `helm test`:

```yaml
# templates/tests/test-connection.yaml
apiVersion: v1
kind: Pod
metadata:
  name: {{ .Release.Name }}-test-connection
  annotations:
    "helm.sh/hook": test
    "helm.sh/hook-delete-policy": hook-succeeded
spec:
  restartPolicy: Never
  containers:
    - name: wget
      image: busybox:1.36
      command: ["wget", "--spider", "--timeout=5",
                "http://{{ .Release.Name }}-{{ .Chart.Name }}/health"]
```

```bash
helm test myapp -n production
# Запущен hook: myapp/templates/tests/test-connection.yaml
# Pod myapp-test-connection: успешно завершился
# НАБОР ТЕСТОВ: myapp
# Статус: УСПЕШНО
```

### Библиотечные chart
Библиотечный chart содержит только шаблоны `_helpers.tpl` — повторно используемые фрагменты без генерируемых манифестов. Другие chart подключают его как зависимость:

```yaml
# library-chart/Chart.yaml
apiVersion: v2
name: common
type: library         # library type — cannot be installed directly
version: 1.0.0
```

```yaml
# library-chart/templates/_labels.tpl
{{- define "common.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
{{- end -}}
```

```yaml
# mychart/Chart.yaml
dependencies:
  - name: common
    version: "1.0.0"
    repository: "file://../common"   # local path or repo URL
```

```yaml
# mychart/templates/deployment.yaml
metadata:
  labels:
    {{- include "common.labels" . | nindent 4 }}
```

### Зависимости chart (subcharts)
```yaml
# Chart.yaml
dependencies:
  - name: postgresql
    version: "14.2.3"
    repository: "https://charts.bitnami.com/bitnami"
    condition: postgresql.enabled   # only deploy if this value is true
    tags:
      - database
  - name: redis
    version: "18.x.x"
    repository: "https://charts.bitnami.com/bitnami"
    condition: redis.enabled
```

```bash
# Загрузить зависимости в charts/
helm dependency update ./mychart
# Creates charts/postgresql-14.2.3.tgz, charts/redis-18.x.x.tgz, and Chart.lock

# Собрать зависимости (использовать версии из Chart.lock)
helm dependency build ./mychart
```

В `values.yaml` значения subchart располагаются внутри секции с именем подчинённого chart:
```yaml
postgresql:
  enabled: true
  auth:
    postgresPassword: secret
    database: myapp
  primary:
    persistence:
      size: 20Gi

redis:
  enabled: false
```

### Продвинутые шаблоны

#### Именованные шаблоны с аргументами
```yaml
# _helpers.tpl
{{- define "myapp.env" -}}
{{- range $key, $val := . }}
- name: {{ $key }}
  value: {{ $val | quote }}
{{- end }}
{{- end }}
```

```yaml
# deployment.yaml
env:
  {{- include "myapp.env" .Values.env | nindent 12 }}
```

#### Обязательные значения и проверка
```yaml
# Сразу завершиться, если отсутствуют обязательные значения
image: {{ required "image.repository is required" .Values.image.repository }}

# Пользовательская проверка
{{- if and .Values.ingress.enabled (not .Values.ingress.host) }}
{{- fail "ingress.host must be set when ingress.enabled=true" }}
{{- end }}
```

#### Вычисляемые значения
```yaml
# Объединить значения в строку подключения
env:
  - name: DATABASE_URL
    value: {{ printf "postgresql://%s:%s@%s:%d/%s"
      .Values.db.user
      .Values.db.password
      .Values.db.host
      (.Values.db.port | int)
      .Values.db.name | quote }}
```

### Упаковка и публикация
```bash
# Упаковать chart в архив .tgz
helm package ./mychart

# Упаковать в указанный выходной каталог
helm package ./mychart --destination ./dist

# Обновить индекс репозитория (для собственного репозитория chart)
helm repo index ./dist --url https://charts.example.com

# Отправить в реестр OCI
helm push mychart-0.1.0.tgz oci://registry.example.com/charts
```

## Примеры

### Production chart с hook для миграции
```yaml
# templates/hooks/migrate.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "myapp.fullname" . }}-migrate-{{ .Release.Revision }}
  annotations:
    "helm.sh/hook": pre-upgrade,pre-install
    "helm.sh/hook-weight": "-5"
    "helm.sh/hook-delete-policy": before-hook-creation,hook-succeeded
spec:
  backoffLimit: 2
  activeDeadlineSeconds: 300
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: {{ .Release.Name }}-migrator
      containers:
        - name: migrate
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          command: {{ .Values.migration.command | toJson }}
          envFrom:
            - secretRef:
                name: {{ .Release.Name }}-secrets
```

## Практические задания

1. Добавьте в существующий chart hook `pre-upgrade`, запускающий Job для миграции базы данных. Используйте `helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded`. Проверьте работу командой `helm upgrade` и убедитесь, что Job выполнился.
2. Напишите тест chart, проверяющий, что endpoint `/health` приложения возвращает HTTP 200. Запустите его через `helm test` и убедитесь, что тест проходит, а тестовый pod удаляется.
3. Создайте библиотечный chart с шаблоном `common.labels`, затем chart приложения, который зависит от него. Убедитесь, что `helm template` добавляет общие метки ко всем ресурсам.
4. Добавьте `postgresql` от Bitnami как зависимость chart с условием `condition: postgresql.enabled`. Проверьте, что `helm install --set postgresql.enabled=false` разворачивает приложение без экземпляра PostgreSQL.


---

### Быстрая проверка

5. Посчитайте файлы шаблонов в каталоге chart. Выполните: `printf 'deployment.yaml\nservice.yaml\ningress.yaml\nconfigmap.yaml\nserviceaccount.yaml\n' | grep -c '\.yaml$'`

```expected_output
5
```

Подсказка: отфильтруйте строки по шаблону и автоматически подсчитайте совпадения.
Подсказка: используйте `grep -c` для подсчёта строк, заканчивающихся на расширение `.yaml`.

6. Извлеките тип chart из примера `Chart.yaml` библиотечного chart. Выполните: `printf 'apiVersion: v2\nname: mylib\ntype: library\n' | awk '/^type:/{print $2}'`

```expected_output
library
```

Подсказка: используйте `awk`, чтобы найти строку по шаблону и вывести определённое поле.
Подсказка: используйте `awk` с шаблоном `/^type:/`, затем обратитесь ко второму полю через `$2`.
