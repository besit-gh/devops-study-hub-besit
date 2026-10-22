---
title: Уверенная работа с kubectl
module: kubernetes
duration_min: 25
difficulty: intermediate
tags: [kubernetes, kubectl, commands, debugging, context, jsonpath]
exercises: 4
---

## Обзор

`kubectl` — основной интерфейс между инженером и control plane кластера Kubernetes. Через него выполняют все основные операции: развёртывают приложения, исследуют неисправные Pod, откатывают релизы и выводят узлы из обслуживания. Для DevOps-инженера уверенное владение kubectl обязательно: это инструмент наблюдения за состоянием системы и точечного вмешательства. Во время инцидента опытного инженера часто отличает скорость и уверенность, с которой он может исследовать кластер.

kubectl взаимодействует с Kubernetes API server по HTTPS. Каждая подкоманда соответствует REST-операции: `get` выполняет GET, `apply` — серверный PATCH или POST, `delete` — DELETE. Это помогает понимать сообщения об ошибках и показывает, что почти любую операцию kubectl можно выполнить напрямую через `curl` к API server. Сам kubectl не хранит состояние кластера: оно находится в etcd и доступно через API server.

В DevOps kubectl используется на стыке CI/CD, реагирования на инциденты и управления инфраструктурой как кодом. Пайплайны выполняют `kubectl apply` для развёртывания, дежурные инженеры используют `kubectl describe` и `kubectl logs` для диагностики, а платформенные команды применяют JSONPath и пользовательские столбцы для построения панелей состояния. Глубокое знание форматов вывода, управления контекстами и средств отладки ускоряет развёртывание и сокращает среднее время восстановления.

---

## Основные понятия

### Контексты и кластеры

Файл kubeconfig (по умолчанию `~/.kube/config`) содержит три типа объектов: **кластеры** (адреса API-сервера и сертификаты CA), **пользователи** (учётные данные) и **контексты** (именованный набор из кластера, пользователя и пространства имён). При переключении контекста меняются все три параметра одновременно.

```bash
# List all configured contexts (cluster + user + namespace combos)
kubectl config get-contexts

# Show current context
kubectl config current-context

# Switch context (switch cluster)
kubectl config use-context prod-cluster

# Set default namespace for current context (avoids -n flag everywhere)
kubectl config set-context --current --namespace=production

# Quick context info — shows API server URL and CoreDNS endpoint
kubectl cluster-info
```

**Несколько файлов kubeconfig:** вместо объединения всех настроек в один файл можно задать несколько конфигураций через переменную `KUBECONFIG`:

```bash
# Merge two configs temporarily
export KUBECONFIG=~/.kube/staging.yaml:~/.kube/prod.yaml
kubectl config get-contexts   # shows contexts from both files

# Permanently merge into a single file
kubectl config view --flatten > ~/.kube/merged.yaml
```

**kubectx и kubens** позволяют переключать контексты и пространства имён одной короткой командой:

```bash
kubectx prod-cluster     # switch context
kubens production        # switch namespace
kubectx -                # switch back to previous context (like cd -)
```

**Подводный камень — сохранение пространства имён:** команда `kubectl config set-context --current --namespace=production` изменяет kubeconfig на диске. Если забыть об этой настройке, все команды будут незаметно обращаться не к тому пространству имён. Подключаясь к расследованию чужого инцидента, всегда проверяйте столбец NAMESPACE в выводе `kubectl config get-contexts`.

| Field | Where it lives | What it controls |
|-------|----------------|-----------------|
| `cluster` | kubeconfig `clusters:` | API server URL, CA certificate |
| `user` | kubeconfig `users:` | Auth method (token, cert, exec plugin) |
| `context` | kubeconfig `contexts:` | Binds cluster + user + default namespace |
| `current-context` | kubeconfig root | Which context kubectl uses by default |

---

### Получение ресурсов

`kubectl get` — основная команда для просмотра ресурсов. Хорошо разберитесь с её параметрами: различие между `-o wide`, `-o yaml` и `-o jsonpath` определяет, насколько быстро вы получите нужные данные.

```bash
# Basic listing
kubectl get pods
kubectl get pods -n kube-system
kubectl get pods -A                  # all namespaces; adds NAMESPACE column
kubectl get pods -o wide             # adds NODE, IP, NOMINATED NODE, READINESS GATES

# Multiple resource types in one call (single API round-trip per type)
kubectl get deployments,services,ingress -n production

# Get all "standard" resources: deployments, replicasets, pods, services, etc.
kubectl get all -n production

# Watch mode — live updates without polling manually
kubectl get pods -w

# describe: human-readable deep view including Events section
kubectl describe pod myapp-abc123
kubectl describe node ip-10-0-1-5

# Raw YAML/JSON of the live resource — what the API server actually stores
kubectl get deployment myapp -o yaml
kubectl get pod myapp-abc123 -o json
```

**`describe` и `get -o yaml`:** `describe` добавляет вычисляемые поля и список Events, которых нет в сохранённом YAML. При диагностике сначала запускайте `describe`: внизу, в разделе Events, Kubernetes объясняет, *почему* возникла ошибка (например, `FailedScheduling`, `BackOff`, `Failed to pull image`).

**Важно: `kubectl get all` — это не буквально все ресурсы.** Несмотря на название, команда не выводит все типы ресурсов. В частности, она пропускает CRD, PersistentVolume, ServiceAccount, ConfigMap, Secret и другие объекты. Чтобы перечислить ресурсы пространства имён, используйте:

```bash
# List every resource type present in a namespace
kubectl api-resources --verbs=list --namespaced -o name \
  | xargs -I{} kubectl get {} -n production --ignore-not-found
```

---

### Фильтрация и выборка

Фильтрация на клиенте через `grep` работает, но фильтрация на стороне сервера с помощью меток и селекторов полей быстрее и лучше масштабируется в больших кластерах.

```bash
# Label selectors — match pods by label key=value
kubectl get pods -l app=myapp
kubectl get pods -l app=myapp,env=production      # AND logic
kubectl get pods -l 'env in (staging,production)' # set-based selector
kubectl get pods -l 'app!=myapp'                  # negation

# Field selectors — filter by resource fields (limited set supported server-side)
kubectl get pods --field-selector status.phase=Running
kubectl get pods --field-selector spec.nodeName=ip-10-0-1-5
kubectl get pods --field-selector status.phase!=Running,status.phase!=Succeeded

# Sort output by any JSONPath expression
kubectl get pods --sort-by='.metadata.creationTimestamp'
kubectl get pods --sort-by='.status.startTime'
kubectl get events --sort-by='.lastTimestamp'
```

**Метки и селекторы полей:** метки — это произвольные метаданные, задаваемые вами; селекторы полей фильтруют реальные поля объекта. Поддержка селекторов полей ограничена: не каждое поле индексируется на сервере. Если возникает `Error: field label not supported`, фильтруйте по этому полю на клиенте.

| Selector type | Syntax | Evaluated where | Performance |
|--------------|--------|-----------------|-------------|
| Label selector | `-l app=myapp` | API server (indexed) | Fast, use freely |
| Field selector | `--field-selector status.phase=Running` | API server (limited fields) | Fast for supported fields |
| JSONPath filter | `-o jsonpath='{...}'` | Client-side | Scans full response |
| `grep` on output | `kubectl get pods \| grep name` | Client-side text | Fragile, avoid |

---

### Форматирование вывода

Обычный вывод `kubectl get` предназначен для человека. Скриптам и конвейерам нужны структурированные данные. Освойте три следующих формата.

```bash
# Custom columns — define exactly what to show and what to name it
kubectl get pods -o custom-columns=\
NAME:.metadata.name,\
STATUS:.status.phase,\
NODE:.spec.nodeName,\
IP:.status.podIP

# JSONPath — extract a single field from one resource
kubectl get pod myapp-abc123 -o jsonpath='{.status.podIP}'

# JSONPath — extract from all items in a list
kubectl get pods -o jsonpath='{.items[*].metadata.name}'

# JSONPath — multi-field with tab/newline formatting (most useful in scripts)
kubectl get pods -o jsonpath=\
'{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\t"}{.spec.nodeName}{"\n"}{end}'

# Real-world: get every deployment name and its running image across all namespaces
kubectl get deployments -A -o jsonpath=\
'{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{.spec.template.spec.containers[0].image}{"\n"}{end}'

# Real-world: find every pod NOT on a specific node
kubectl get pods -A -o jsonpath=\
'{range .items[?(@.spec.nodeName!="ip-10-0-1-5")]}{.metadata.name}{"\n"}{end}'
```

Краткая справка по JSONPath:

| Expression | Meaning |
|-----------|---------|
| `.metadata.name` | Single field access |
| `.items[*]` | All elements of an array |
| `.items[0]` | First element |
| `.items[-1:]` | Last element |
| `.spec.containers[?(@.name=="app")]` | Filter array by field value |
| `{range ...}{end}` | Loop construct for lists |
| `{"\t"}` `{"\n"}` | Literal tab / newline in output |

**Важно: JSONPath для списка и отдельного ресурса различается.** В команде `kubectl get pod myapp-abc123 -o jsonpath='{.status.podIP}'` корневой объект — сам Pod. В `kubectl get pods -o jsonpath='{...}'` корень — PodList, поэтому для перебора нужен `.items[*]`. Если забыть об этом, вывод будет пустым, но ошибки не появится.

**`-o json | jq` и `-o jsonpath`:** для простого извлечения данных быстрее JSONPath — дополнительный инструмент не нужен. Для сложной фильтрации, условий или форматирования вложенных структур передавайте JSON в `jq`. Оба способа подходят для production-скриптов; JSONPath предпочтительнее, когда нужно сократить внешние зависимости, например в минимальном CI-контейнере.

---

### Применение и редактирование ресурсов

Kubernetes предпочитает **декларативное** управление: вы описываете желаемое состояние в YAML, а управляющая плоскость приводит фактическое состояние к нему. Основной инструмент для этого — `kubectl apply`.

```bash
# Apply a single manifest (create if absent, patch if present)
kubectl apply -f deployment.yaml

# Apply all manifests in a directory (non-recursive by default)
kubectl apply -f ./manifests/

# Apply recursively through subdirectories
kubectl apply -f ./manifests/ -R

# Apply with Kustomize overlays
kubectl apply -k ./overlays/prod/

# Dry run — validate manifest without touching the cluster
kubectl apply -f deployment.yaml --dry-run=client    # parsed locally only
kubectl apply -f deployment.yaml --dry-run=server    # sent to API, validated by admission webhooks

# Edit a live resource in $EDITOR (fetches YAML, opens editor, re-applies on save)
kubectl edit deployment myapp

# Strategic merge patch — merge a partial JSON/YAML document into the resource
kubectl patch deployment myapp -p '{"spec":{"replicas":5}}'

# JSON Patch (RFC 6902) — precise operation-based patching
kubectl patch deployment myapp --type=json \
    -p='[{"op":"replace","path":"/spec/replicas","value":5}]'

# Scale shortcut (equivalent to patching spec.replicas)
kubectl scale deployment myapp --replicas=5

# Delete by manifest (respects resource names in file)
kubectl delete -f deployment.yaml

# Delete by name
kubectl delete deployment myapp
kubectl delete pod myapp-abc123 --grace-period=0   # skip graceful termination
```

**`--dry-run=client` и `--dry-run=server`:** клиентский пробный запуск проверяет только синтаксис YAML и базовую структуру. Серверный проходит через все admission-webhook (OPA Gatekeeper, Kyverno и другие) и проверяет манифест с учётом текущего состояния кластера. Это позволяет обнаружить нарушения политик до применения. Используйте серверную проверку в CI-конвейерах.

**Важно: `kubectl apply` и `kubectl create`:** `create` завершится ошибкой, если ресурс уже существует. `apply` идемпотентен и безопасен при повторном запуске. В конвейерах используйте `apply`; `create` подходит для однократной начальной настройки или когда при конфликте нужна явная ошибка.

| Command | Idempotent | Creates | Updates | Deletes removed fields |
|---------|-----------|---------|---------|----------------------|
| `kubectl create` | No | Yes | No | N/A |
| `kubectl apply` | Yes | Yes | Yes (merge) | No (use `--prune`) |
| `kubectl replace` | No | No | Yes (full replace) | Yes |
| `kubectl patch` | Yes | No | Yes (partial) | No |

**Управление развёртыванием:** после изменения Deployment используйте `kubectl rollout`, чтобы отслеживать и контролировать процесс обновления:

```bash
# Watch rollout progress (blocks until complete or fails)
kubectl rollout status deployment/myapp

# View rollout history (requires --record on apply, or use annotations)
kubectl rollout history deployment/myapp

# Rollback to the previous revision
kubectl rollout undo deployment/myapp

# Rollback to a specific revision
kubectl rollout undo deployment/myapp --to-revision=3

# Pause a rolling update mid-flight (canary pause)
kubectl rollout pause deployment/myapp

# Resume after inspection
kubectl rollout resume deployment/myapp
```

**Важно: `kubectl rollout undo` не заменяет GitOps.** Команда возвращает в Deployment шаблон предыдущего ReplicaSet, но в Git по-прежнему остаётся сломанная версия. После отката обязательно исправьте манифест и выполните `kubectl apply` из него, иначе следующий запуск конвейера снова развернёт неисправную версию.

---

### Debugging

Диагностика Kubernetes требует сопоставления четырёх источников: Events (что пыталась сделать управляющая плоскость), журналов (что вывело приложение), состояния ресурсов (что поля говорят о текущем состоянии) и сетевой доступности. `kubectl` даёт прямой доступ ко всем четырём.

```bash
# Logs — basic
kubectl logs myapp-abc123
kubectl logs myapp-abc123 -c sidecar        # specific container in multi-container pod
kubectl logs myapp-abc123 --previous        # logs from the last (crashed) container instance
kubectl logs -f myapp-abc123                # stream / follow
kubectl logs myapp-abc123 --tail=100        # last N lines
kubectl logs myapp-abc123 --since=1h        # logs from the last hour
kubectl logs -l app=myapp --all-containers  # aggregate across all matching pods

# Shell access
kubectl exec -it myapp-abc123 -- /bin/bash
kubectl exec -it myapp-abc123 -c sidecar -- /bin/sh
kubectl exec myapp-abc123 -- cat /etc/resolv.conf   # non-interactive single command

# Ephemeral debug container (K8s 1.23+) — attach a debug image to a running pod
# Useful when the main container has no shell (distroless, scratch images)
kubectl debug -it myapp-abc123 --image=busybox:1.37 --target=app

# Spawn a standalone debug pod on a specific node (bypasses pod scheduling constraints)
kubectl debug node/ip-10-0-1-5 -it --image=ubuntu:22.04

# Port-forward — proxy traffic directly to a pod/service/deployment, no Ingress needed
kubectl port-forward pod/myapp-abc123 8080:8080        # local:remote
kubectl port-forward service/myapp 8080:80
kubectl port-forward deployment/myapp 8080:8080        # forwards to one pod in the deployment

# File transfer
kubectl cp myapp-abc123:/var/log/app.log ./app.log                   # pod → local
kubectl cp ./config.json myapp-abc123:/etc/app/config.json           # local → pod
kubectl cp myapp-abc123:/var/log/app.log ./app.log -c sidecar        # specify container
```

**Важно: `kubectl logs --previous`:** команда работает, пока Pod существует и в нём хотя бы раз завершался предыдущий контейнер. Если Pod удалили и создали заново под другим именем, старые журналы исчезнут, если нет системы агрегации логов (Loki, Elasticsearch, CloudWatch и т. п.). В production не полагайтесь только на `kubectl logs` — всегда отправляйте журналы в агрегатор.

**Важно: `kubectl exec` в distroless-контейнеры:** во многих production-образах, собранных на основе `scratch` или `distroless`, нет оболочки. Помогает `kubectl debug` с эфемерным контейнером: он использует сетевое пространство имён и PID-пространство Pod, поэтому можно изучать `/proc`, запускать `curl` к `localhost` и просматривать файловую систему через `/proc/<pid>/root`.

**Важно: `kubectl cp` требует `tar` внутри контейнера.** Команда запускает `tar` в контейнере. Если в образе нет этой утилиты (например, distroless или минимальный Alpine), копирование завершится ошибкой или не сработает. Используйте `kubectl debug`, чтобы подключить контейнер с нужными инструментами, и скопируйте файлы оттуда.

---

### Сценарии диагностики

Знать отдельные команды недостаточно — для каждого типа отказа нужен систематический алгоритм диагностики.

**Pod завис в состоянии `Pending`:**
```bash
kubectl describe pod myapp-abc123 | grep -A 20 "Events:"
# Common causes in Events:
#   0/3 nodes are available: Insufficient memory
#   0/3 nodes are available: node(s) had untolerated taint
#   persistentvolumeclaim "my-pvc" not found

# Check available node capacity
kubectl get nodes -o custom-columns=\
NAME:.metadata.name,\
CPU:.status.allocatable.cpu,\
MEM:.status.allocatable.memory,\
STATUS:.status.conditions[-1:].type
```

**Pod in `CrashLoopBackOff`:**
```bash
kubectl logs myapp-abc123 --previous    # application crash output
kubectl describe pod myapp-abc123       # check exit code and reason

# Exit code meanings:
#   exit 0  — process exited cleanly (misconfigured liveness probe likely cause)
#   exit 1  — application error
#   exit 137 — OOMKilled (SIGKILL from kernel OOM, or Docker limit)
#   exit 143 — SIGTERM not handled (graceful shutdown failed)

# If OOMKilled: spec.containers[].resources.limits.memory is too low
# If liveness probe: check probe path, port, and initialDelaySeconds
```

**Pod in `ImagePullBackOff` or `ErrImagePull`:**
```bash
kubectl describe pod myapp-abc123 | grep -A5 "Events:"
# Causes:
#   image tag does not exist → typo or tag was deleted
#   repository is private → missing imagePullSecret
#   registry is unreachable → network policy or DNS issue on node

# Inspect the pull secret content
kubectl get secret regcred -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d
```

**Service не направляет трафик:**
```bash
# Step 1: check if endpoints exist — empty = selector matches no pods
kubectl get endpoints myapp-service

# Step 2: compare Service selector to pod labels
kubectl get svc myapp-service -o jsonpath='{.spec.selector}'
kubectl get pods -l app=myapp --show-labels

# Step 3: verify pod is Ready (not just Running)
kubectl get pods -l app=myapp -o custom-columns=\
NAME:.metadata.name,\
READY:.status.containerStatuses[0].ready,\
PHASE:.status.phase

# Step 4: test connectivity from inside the cluster
kubectl run curl-test --image=curlimages/curl:8.5.0 --rm -it --restart=Never \
  -- curl -v http://myapp-service.production.svc.cluster.local:80/healthz
```

**Узел NotReady:**
```bash
# Check node conditions
kubectl describe node ip-10-0-1-5 | grep -A5 "Conditions:"

# List pods currently scheduled on the troubled node
kubectl get pods -A --field-selector spec.nodeName=ip-10-0-1-5

# Cordon (prevent new scheduling) before investigating
kubectl cordon ip-10-0-1-5

# Drain (evict existing pods) before maintenance or replacement
kubectl drain ip-10-0-1-5 --ignore-daemonsets --delete-emptydir-data

# Uncordon after node is healthy
kubectl uncordon ip-10-0-1-5
```

**Важно: `kubectl drain` и PodDisruptionBudget.** Если PDB требует доступности хотя бы одного Pod, а у Deployment только одна реплика, `kubectl drain` может надолго заблокироваться. Появится сообщение `cannot evict pod as it would violate the pod's disruption budget`. Можно сначала увеличить число реплик или передать `--disable-eviction` (обходит PDB — в production используйте осторожно).

---

### Управление ресурсами и эффективность

Освоив несколько приёмов `kubectl`, вы сможете заметно быстрее выполнять повседневные задачи.

```bash
# Generate YAML scaffold without applying — great starting point for new manifests
kubectl create deployment myapp --image=nginx:1.25 --dry-run=client -o yaml > deployment.yaml
kubectl create service clusterip myapp --tcp=80:8080 --dry-run=client -o yaml >> deployment.yaml
kubectl create configmap app-config --from-file=./config/ --dry-run=client -o yaml

# Explain any field in any resource — no docs tab needed
kubectl explain pod.spec.containers.resources
kubectl explain deployment.spec.strategy.rollingUpdate
kubectl explain --recursive pod.spec   # full tree of all fields

# API resource discovery — know what CRDs and built-ins are available
kubectl api-resources                          # all resource types
kubectl api-resources --namespaced=false       # cluster-scoped only
kubectl api-resources --api-group=apps         # filter by API group
kubectl api-versions                           # all available API versions

# Check your own RBAC permissions — critical when debugging "Forbidden" errors
kubectl auth can-i create deployments -n production
kubectl auth can-i '*' '*'                     # am I cluster-admin?
kubectl auth can-i list secrets -n kube-system --as=system:serviceaccount:default:myapp

# Top — live resource consumption (requires metrics-server installed)
kubectl top nodes
kubectl top pods -n production
kubectl top pods -n production --sort-by=memory
kubectl top pods -n production --containers     # per-container breakdown
```

**`kubectl explain` на собеседовании:** интервьюеры часто спрашивают о конкретных полях YAML. `kubectl explain` даёт точный ответ без необходимости запоминать спецификацию. Если во время практического собеседования доступен терминал, используйте эту команду.

**Важно: `kubectl top` требует metrics-server.** В пустом кластере команда не работает: нужен агрегированный API `metrics-server`. Если получаете `error: Metrics API not available`, сервис не установлен или неисправен. Проверьте его командой `kubectl get apiservice v1beta1.metrics.k8s.io`.

---

## Примеры

### Пример 1. Полный цикл развёртывания, проверки и отката

Пример показывает полный жизненный цикл развёртывания в CI/CD-конвейере, завершающийся контролируемым откатом.

```bash
# 1. Write a deployment manifest
cat <<'EOF' > myapp-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: production
  labels:
    app: myapp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # allow one extra pod during update
      maxUnavailable: 0  # never reduce below desired count (zero-downtime)
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: app
        image: nginx:1.24   # intentionally older version; we'll upgrade
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 250m
            memory: 256Mi
        readinessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5
EOF

# 2. Server-side dry run — validates against admission webhooks
kubectl apply -f myapp-deployment.yaml --dry-run=server

# 3. Apply for real
kubectl apply -f myapp-deployment.yaml

# 4. Watch rollout converge
kubectl rollout status deployment/myapp -n production
# Output: Waiting for deployment "myapp" rollout to finish: 0 of 3 updated replicas are available...
# Output: deployment "myapp" successfully rolled out

# 5. Verify: all pods Running and Ready
kubectl get pods -n production -l app=myapp -o wide

# 6. Simulate an upgrade to a broken image
kubectl set image deployment/myapp app=nginx:broken-tag -n production

# 7. Watch the rollout fail
kubectl rollout status deployment/myapp -n production
# Output: error: deployment "myapp" exceeded its progress deadline

# 8. Confirm: some pods in ImagePullBackOff
kubectl get pods -n production -l app=myapp

# 9. Rollback to the last good revision
kubectl rollout undo deployment/myapp -n production

# 10. Verify recovery
kubectl rollout status deployment/myapp -n production
kubectl get pods -n production -l app=myapp
```

---

### Пример 2. Диагностика CrashLoopBackOff с нуля

Моделирует неправильно настроенное приложение и демонстрирует полный процесс диагностики.

```bash
# 1. Deploy a pod that immediately crashes (bad command)
kubectl run crasher \
  --image=busybox:1.37 \
  --restart=Always \
  -n default \
  -- /bin/sh -c "echo 'starting'; exit 1"

# 2. Check pod status after a few seconds
kubectl get pod crasher
# NAME      READY   STATUS             RESTARTS   AGE
# crasher   0/1     CrashLoopBackOff   3          45s

# 3. Read the crash output from the previous container instance
kubectl logs crasher --previous
# Output: starting

# 4. Describe to see exit code and restart count
kubectl describe pod crasher | grep -A 10 "Last State:"
# Last State: Terminated
#   Reason: Error
#   Exit Code: 1
#   ...

# 5. Fix: update the command to not exit with error
kubectl delete pod crasher
kubectl run crasher \
  --image=busybox:1.37 \
  --restart=Always \
  -n default \
  -- /bin/sh -c "echo 'running'; sleep 3600"

# 6. Verify
kubectl get pod crasher
# NAME      READY   STATUS    RESTARTS   AGE
# crasher   1/1     Running   0          10s

# Cleanup
kubectl delete pod crasher
```

---

### Пример 3. Диагностика сетевой доступности Service

Разбирает ситуацию, когда Service выглядит исправным, но не получает трафик.

```bash
# 1. Create a deployment and a deliberately misconfigured Service
kubectl create deployment web --image=nginx:1.25 --replicas=2 -n production

cat <<'EOF' | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: web-svc
  namespace: production
spec:
  selector:
    app: web-typo   # BUG: should be "app: web"
  ports:
  - port: 80
    targetPort: 80
EOF

# 2. Check endpoints — should be populated if selector matches
kubectl get endpoints web-svc -n production
# NAME      ENDPOINTS   AGE
# web-svc   <none>      5s    ← selector matches nothing

# 3. Compare selector to pod labels
kubectl get svc web-svc -n production -o jsonpath='{.spec.selector}'
# {"app":"web-typo"}

kubectl get pods -n production -l app=web --show-labels
# NAME             READY   STATUS    LABELS
# web-xxx   1/1   Running   app=web,pod-template-hash=...

# 4. Fix the selector
kubectl patch svc web-svc -n production \
  -p '{"spec":{"selector":{"app":"web"}}}'

# 5. Verify endpoints are now populated
kubectl get endpoints web-svc -n production
# NAME      ENDPOINTS                         AGE
# web-svc   10.0.0.5:80,10.0.0.6:80          10s

# 6. Confirm reachability from inside the cluster
kubectl run curl-test --image=curlimages/curl:8.5.0 --rm -it \
  --restart=Never -n production \
  -- curl -s -o /dev/null -w "%{http_code}" http://web-svc.production.svc.cluster.local/
# 200

# Cleanup
kubectl delete deployment web -n production
kubectl delete svc web-svc -n production
```

---

### Пример 4. Отчёт JSONPath по нескольким кластерам

Создаёт инвентаризацию образов в разных пространствах имён. Это полезно для проверки версий перед установкой исправления CVE.

```bash
# Report: namespace, deployment name, container name, image — across entire cluster
kubectl get deployments -A -o jsonpath=\
'{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{range .spec.template.spec.containers[*]}{.name}{"\t"}{.image}{"\n"}{end}{end}' \
| column -t \
| sort

# Sample output:
# kube-system   coredns          coredns    registry.k8s.io/coredns/coredns:v1.10.1
# production    myapp            app        nginx:1.25
# production    myapp            sidecar    envoyproxy/envoy:v1.28.0
# staging       myapp            app        nginx:1.26-beta   ← spot the drift

# Find all deployments NOT using a pinned tag (using :latest or no tag)
kubectl get deployments -A -o json \
| jq -r '.items[] | 
    .metadata.namespace + "\t" + .metadata.name + "\t" + 
    (.spec.template.spec.containers[].image) 
  | select(test(":latest$|^[^:]+$"))'
# Outputs anything with :latest or missing tag — a security/reproducibility risk
```

---

## Практические задания

### Задание 1. Безопасная работа с контекстом и пространством имён

**Цель:** понять, как пространство имён по умолчанию влияет на команды, и научиться безопасно работать с контекстами.

1. Выполните `kubectl config get-contexts` и запишите активный контекст и заданное пространство имён, если оно указано.
2. С помощью `kubectl config set-context` установите `kube-system` как пространство имён по умолчанию для текущего контекста.
3. Выполните `kubectl get pods` без флага `-n` и проверьте, из какого пространства имён получены результаты.
4. Верните пространство имён по умолчанию на `default`.
5. Напишите однострочную команду, которая выводит имя текущего контекста и настроенное пространство имён, используя только подкоманды `kubectl config`, без `grep` и `awk`.

**Задание со звёздочкой:** не переключая текущий контекст, выполните одну команду `kubectl get pods`, обращаясь к пространству имён `kube-system` в *другом* контексте. Подсказка: используйте флаг `--context`.

---

### Задание 2. Извлечение данных через JSONPath в условиях инцидента

**Цель:** отработать JSONPath до автоматизма, чтобы уверенно применять его во время инцидента.

В кластере работает несколько Pod. Ответьте на вопросы, используя только `kubectl get` с `-o jsonpath` или `-o custom-columns`, без `grep`, `jq` и `awk`:

1. Выведите только IP-адреса всех работающих Pod в пространстве имён `default`, по одному в строке.
2. Выведите имя и образ *первого* контейнера каждого Pod во всех пространствах имён в формате `namespace/pod-name: image`.
3. Найдите Pod, у которого `status.phase` не равен `Running`, и выведите его имя и фазу. Подсказка: фильтры JSONPath поддерживают `!=`.
4. Выведите имя узла `nodeName`, на котором запланирован каждый Pod в `default`, вместе с именем Pod.

**Проверка:** каждый ответ должен быть одной командой `kubectl`. Если требуется вторая команда, значит, вы пока недостаточно освоили JSONPath.

---

### Задание 3. Обновление Deployment и восстановление

**Цель:** самостоятельно отработать полный цикл «развернуть — сломать — диагностировать — восстановить».

1. Создайте Deployment `exercise-app` в пространстве имён `exercise` с образом `nginx:1.25`, тремя репликами и стратегией `rollingUpdate`: `maxUnavailable: 0`, `maxSurge: 1`.
2. Перед продолжением убедитесь, что все три Pod находятся в состоянии `Running` и `Ready`.
3. Измените образ на `nginx:does-not-exist` с помощью `kubectl set image`.
4. Самостоятельно найдите причину сбоя и затронутые Pod с помощью команд `kubectl describe` и `kubectl get`.
5. Откатитесь к предыдущей ревизии и убедитесь, что все три реплики восстановились.
6. Выведите историю развёртывания, в которой видны обе ревизии.

**Очистка:** по завершении удалите пространство имён `exercise`.

---

### Задание 4. Диагностика Service без подсказок

**Цель:** структурированно диагностировать неисправность сервиса — от симптомов до первопричины.

Примените к кластеру следующие манифесты:

```yaml
# Save as broken-scenario.yaml and apply with kubectl apply -f broken-scenario.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: app
        image: hashicorp/http-echo:1.0.0
        args: ["-text=hello"]
        ports:
        - containerPort: 5678
---
apiVersion: v1
kind: Service
metadata:
  name: backend-svc
  namespace: default
spec:
  selector:
    app: backend
    tier: api          # extra label that pods don't have
  ports:
  - port: 80
    targetPort: 5678
```

После применения не перечитывайте YAML выше:

1. Проверьте, есть ли у `backend-svc` конечные точки. Запишите использованную команду.
2. Сравните селектор Service с фактическими метками Pod и определите, почему у Service нет конечных точек. Запишите результат.
3. Исправьте Service с помощью `kubectl patch` — не применяйте YAML-файл повторно.
4. Проверьте соединение, запустив временный Pod с curl внутри кластера и обратившись к `backend-svc`.
5. В завершение одним предложением объясните, что произошло бы, если бы селектор Service содержал существующую у Pod метку, но с неправильным значением (например, `tier: frontend` вместо `tier: api`).

---

### Быстрая проверка

6. Посчитайте Pod в состоянии Running по списку статусов. Выполните: `printf 'web-1 Running\ndb-0 Pending\nweb-2 Running\ncache-0 Running\n' | awk '$2=="Running"{c++} END{print c}'`

```expected_output
3
```

Подсказка: `awk` может увеличивать счётчик при выполнении условия для определённого поля каждой строки.
Подсказка: используйте условие `'$2=="Running"{c++}'`, чтобы увеличивать счётчик, а затем выведите его в блоке `END`.

7. Извлеките поле статуса Pod с помощью имитации jsonpath. Выполните: `printf 'name: nginx\nstatus: Running\nready: 1/1\n' | awk '/^status:/{print $2}'`

```expected_output
Running
```

Подсказка: отфильтруйте текстовые строки по шаблону в начале строки.
Подсказка: используйте в `awk` регулярное выражение вроде `/^status:/`, чтобы найти строку статуса, и выведите второе поле с помощью `{print $2}`.
