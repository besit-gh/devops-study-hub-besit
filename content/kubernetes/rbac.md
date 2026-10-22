---
title: RBAC — управление доступом
module: kubernetes
duration_min: 20
difficulty: advanced
tags: [kubernetes, rbac, roles, clusterrole, serviceaccount, permissions, security]
exercises: 4
---

## Обзор

Role-Based Access Control (RBAC) — механизм авторизации Kubernetes, который отвечает на вопрос: «Разрешено ли этой идентичности выполнить это действие над этим ресурсом?». Он действует после аутентификации, подтверждающей личность, и до выполнения запроса API-сервером. Без RBAC скомпрометированный Pod или неправильно настроенный CI-пайплайн может прочитать все Secret, удалить любой Deployment или извлечь данные кластера. RBAC помогает соблюдать принцип минимальных привилегий: каждая идентичность получает только необходимые права.

RBAC намеренно построен по разрешающей модели: правил явного запрета нет. Права суммируются по всем binding-объектам, применимым к субъекту. Поэтому RBAC не может отменить уже выданное разрешение отдельным deny-правилом — нужно просто не предоставлять лишние права. Модель включает четыре типа объектов в двух независимых слоях: слой *определения* (Role, ClusterRole) задаёт разрешённые операции, а слой *привязки* (RoleBinding, ClusterRoleBinding) назначает эти права идентичностям, называемым *subjects*. Благодаря этому роль можно определить один раз и использовать для разных команд, пространств имён и сервисных аккаунтов.

В DevOps RBAC находится на пересечении безопасности платформы и самостоятельной работы разработчиков. Платформенная команда задаёт роли для CI-пайплайнов, агентов мониторинга и операторов приложений. Разработчики используют их через service accounts, не работая напрямую с учётными данными kubeconfig. Аудит безопасности сводится к проверке binding-объектов, а не поиску прав в коде приложений. Понимание RBAC помогает диагностировать `Forbidden` — одну из самых частых ошибок доступа в production Kubernetes, — и проектировать многопользовательские кластеры.

---

## Основные понятия

### Четыре объекта RBAC

Любая конфигурация RBAC строится ровно на четырёх типах объектов. Понимание области их действия — ключ к правильной модели разрешений.

| Объект | Область действия | Назначение |
|---|---|---|
| `Role` | Одно пространство имён | Разрешения на ресурсы в пределах пространства имён |
| `ClusterRole` | Весь кластер | Ресурсы уровня кластера или повторно используемые правила для пространств имён |
| `RoleBinding` | Одно пространство имён | Назначает Role или ClusterRole в пределах одного пространства имён |
| `ClusterRoleBinding` | Весь кластер | Назначает ClusterRole во всех пространствах имён |

**Типы субъектов** — идентичности, которым можно назначать права:

| Тип | Пример имени | Примечания |
|---|---|---|
| `User` | `alice`, `alice@company.com` | В Kubernetes нет объекта User; имя должно точно совпадать с аутентифицированной идентичностью |
| `Group` | `backend-team`, `system:masters` | Внешняя группа, например группа OIDC или поле `O=` сертификата |
| `ServiceAccount` | `ci-deployer` | Реальный объект кластера; в binding обязательно указывать namespace |

**Критически важное правило области действия:** `RoleBinding` может ссылаться на `ClusterRole`, но фактические разрешения всё равно ограничены пространством имён RoleBinding. Так можно определить роль один раз и повторно использовать её в разных пространствах имён, не предоставляя доступ ко всему кластеру.

**Четыре сочетания ролей и binding:**

| Тип роли | Тип binding | Фактическая область действия |
|---|---|---|
| `Role` | `RoleBinding` | Только ресурсы пространства имён binding |
| `ClusterRole` | `RoleBinding` | Только ресурсы пространства имён binding (шаблон повторного использования) |
| `ClusterRole` | `ClusterRoleBinding` | Ресурсы во всех пространствах имён и ресурсы уровня кластера |
| `Role` | `ClusterRoleBinding` | **Недопустимо** — ClusterRoleBinding может ссылаться только на ClusterRole |

### Роли и язык правил

`Role` содержит одно или несколько правил. Каждое правило задаёт комбинацию API-групп, ресурсов и действий (verbs). Все три поля обязательны.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: production
rules:
  - apiGroups: [""]              # "" = core API group (pods, services, secrets, etc.)
    resources: ["pods", "pods/log", "pods/exec"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["app-config"]  # restrict to one specific named resource
    verbs: ["get"]
```

**Распространённые verbs и соответствующие HTTP-методы:**

| Verb | HTTP-метод | Примечания |
|---|---|---|
| `get` | GET (один объект) | Получить ресурс с заданным именем |
| `list` | GET (коллекция) | Получить список ресурсов определённого типа |
| `watch` | GET + `?watch=true` | Получать поток событий об изменениях; требуется контроллерам |
| `create` | POST | Создать ресурс |
| `update` | PUT | Полностью заменить ресурс |
| `patch` | PATCH | Частично изменить ресурс |
| `delete` | DELETE (один объект) | Удалить ресурс с заданным именем |
| `deletecollection` | DELETE (коллекция) | Массовое удаление; о нём часто забывают при аудите |

**Распространённые API-группы:**

| Группа | Ресурсы |
|---|---|
| `""` (core) | pods, services, configmaps, secrets, nodes, namespaces, persistentvolumeclaims, serviceaccounts |
| `apps` | deployments, replicasets, statefulsets, daemonsets |
| `batch` | jobs, cronjobs |
| `networking.k8s.io` | ingresses, networkpolicies |
| `rbac.authorization.k8s.io` | roles, rolebindings, clusterroles, clusterrolebindings |
| `autoscaling` | horizontalpodautoscalers |
| `policy` | poddisruptionbudgets |

**Особенность `resourceNames`:** ограничивает правило конкретными именованными объектами. Его **нельзя** использовать с `list`, `watch`, `create` и `deletecollection`, поскольку эти действия не относятся к одному именованному ресурсу. Такое сочетание тихо создаёт правило, которое никогда не сработает.

**Доступ к подресурсам:** `pods/log`, `pods/exec` и `pods/portforward` нужно указывать явно. Разрешение на `pods` не даёт доступ к `pods/exec`. Это частый пробел в модели минимальных привилегий: команде разрешают `get pods`, забывая, что `exec` — отдельное и гораздо более чувствительное право.

**Разрешения с подстановочным символом:** `resources: ["*"]` и `verbs: ["*"]` допустимы в YAML, но должны применяться только в административных ролях. Они автоматически охватывают новые типы ресурсов из будущих версий API и установленных операторов, поэтому по мере развития кластера становятся скрытым риском.

### ClusterRole

`ClusterRole` синтаксически похож на `Role`, но не содержит поля `namespace`. Используйте ClusterRole, когда нужно:

1. Предоставить доступ к ресурсам уровня кластера (nodes, namespaces, persistentvolumes, storageclasses)
2. Предоставить доступ к ресурсам во всех пространствах имён через `ClusterRoleBinding`
3. Определить повторно используемый шаблон, назначаемый разным пространствам имён отдельными `RoleBinding`

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: monitoring-reader
rules:
  - apiGroups: [""]
    resources: ["nodes", "nodes/metrics", "pods", "services", "endpoints"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["namespaces"]           # cluster-scoped; only grantable via ClusterRole
    verbs: ["get", "list"]
  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets", "daemonsets"]
    verbs: ["get", "list", "watch"]
  - nonResourceURLs: ["/metrics", "/healthz"]   # HTTP paths not backed by K8s objects
    verbs: ["get"]
```

**`nonResourceURLs`** — HTTP-пути API-сервера, не соответствующие объектам Kubernetes, например `/metrics`, `/healthz`, `/version`. Их можно указывать только в ClusterRole и только с verb `get`. Сборщикам Prometheus часто нужен `/metrics` самого API-сервера.

**Агрегация ClusterRole:** ClusterRole может автоматически объединять разрешения других ClusterRole с помощью селекторов меток. Некоторые операторы устанавливают ClusterRole, участвующие в такой агрегации. Учитывайте, что установка нового оператора может незаметно расширить права существующей агрегированной роли, если совпадают метки.

```yaml
# This ClusterRole's rules are auto-populated from any ClusterRole with the matching label
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: monitoring-aggregate
aggregationRule:
  clusterRoleSelectors:
    - matchLabels:
        rbac.example.com/aggregate-to-monitoring: "true"
rules: []   # populated automatically; do not add rules here manually
---
# An operator installs this, and monitoring-aggregate silently gains these rules
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: myoperator-metrics
  labels:
    rbac.example.com/aggregate-to-monitoring: "true"
rules:
  - apiGroups: ["myoperator.io"]
    resources: ["widgetmetrics"]
    verbs: ["get", "list"]
```

### Встроенные ClusterRole

В Kubernetes есть несколько ClusterRole для распространённых сценариев доступа:

| ClusterRole | Фактические права | Типичное применение |
|---|---|---|
| `cluster-admin` | Полные права `*` на всё | Только для аварийного доступа; не использовать в автоматизации |
| `admin` | Полный доступ в пространстве имён, включая управление RBAC | Владелец пространства имён |
| `edit` | Чтение и запись большинства ресурсов; в некоторых конфигурациях нельзя управлять RBAC и читать Secrets | Доступ разработчика |
| `view` | Чтение большинства несекретных ресурсов; без доступа к Secrets | Аудитор, дашборд только для чтения |
| `system:node` | Node-specific access | Kubelets |
| `system:kube-scheduler` | Scheduler-specific access | Scheduler component |

**Предупреждение о `cluster-admin`:** назначение этой роли сервисному аккаунту или CI-конвейеру — критическая ошибка безопасности. Скомпрометированный токен даёт полный контроль над кластером, включая чтение всех Secret, изменение RBAC и удаление рабочих нагрузок. Вместо этого используйте `admin` или специально созданный ClusterRole.

**`edit` и `admin`:** `admin` разрешает управлять Role и RoleBinding в пространстве имён, а `edit` — нет. Выдавайте разработчикам `edit`, если им явно не нужно управлять RBAC на уровне пространства имён. Не назначайте разработчикам `admin` на весь кластер.

### Сервисные аккаунты

ServiceAccount (SA) — объект Kubernetes в пространстве имён, предоставляющий идентичность процессам внутри pod. Каждый pod работает ровно с одним SA. Если его не указать, используется `default` SA пространства имён pod; в защищённом кластере у него не должно быть дополнительных разрешений.

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ci-deployer
  namespace: production
  annotations:
    # Optional: link to a cloud IAM role for pod-level cloud access
    # AWS IRSA — the pod's K8s token is exchanged for an AWS role credential
    eks.amazonaws.com/role-arn: "arn:aws:iam::123456789012:role/ci-deployer"
```

```yaml
# Reference the SA in a Deployment's pod spec
spec:
  serviceAccountName: ci-deployer
  automountServiceAccountToken: false   # set false when the pod never calls the K8s API
  containers:
    - name: app
      image: myapp:v1.0.0
```

Если `automountServiceAccountToken` включён (по умолчанию), Kubernetes монтирует токен по пути `/var/run/secrets/kubernetes.io/serviceaccount/token`. Начиная с Kubernetes 1.24 это ограниченные по времени **bound service account tokens**, а не постоянные JWT. Они истекают, ограничены по audience и автоматически обновляются.

**Базовое усиление безопасности automount:** в большинстве пространств имён у `default` SA задано `automountServiceAccountToken: true`. Каждый pod без явно указанного SA получает смонтированный токен, даже если он никогда его не использует. В качестве базовой меры отключите automount для `default` SA:

```bash
kubectl patch serviceaccount default -n production \
  -p '{"automountServiceAccountToken": false}'
```

**Повышение привилегий через ServiceAccount:** pod, которому разрешено создавать или изменять pod в пространстве имён, фактически может назначить себе любой SA в этом пространстве. Поэтому `create pods`, `patch deployments` и `create cronjobs` — чувствительные разрешения: они позволяют рабочей нагрузке получить более привилегированный SA без явного изменения RBAC.

### Проверка и отладка RBAC

Команда `kubectl auth can-i` — основной инструмент диагностики разрешений. Она напрямую вызывает API SubjectAccessReview — тот же механизм, который API-сервер использует для проверки запросов.

```bash
# Check your own permissions
kubectl auth can-i get pods -n production
kubectl auth can-i --list -n production          # dump all permissions for current identity

# Impersonate a user or ServiceAccount (server-side simulation — safe, requires no credentials)
kubectl auth can-i delete deployments -n production --as=alice
kubectl auth can-i create secrets -n production \
  --as=system:serviceaccount:production:ci-deployer

# Impersonate a user that belongs to a group
kubectl auth can-i list nodes \
  --as=alice --as-group=backend-team

# Find all RoleBindings and ClusterRoleBindings in a namespace
kubectl get rolebindings,clusterrolebindings -n production -o wide

# Find every ClusterRoleBinding that grants cluster-admin
kubectl get clusterrolebindings -o json | \
  jq '.items[] | select(.roleRef.name=="cluster-admin") | {name: .metadata.name, subjects: .subjects}'

# Find every binding that references a specific ServiceAccount
kubectl get rolebindings,clusterrolebindings -A -o json | \
  jq '.items[] | select(.subjects[]? | .kind=="ServiceAccount" and .name=="ci-deployer")'

# Describe a binding to see its full subject list and role reference
kubectl describe rolebinding ci-deployer-binding -n production

# Quick imperative creation for testing (do not use in production manifests)
kubectl create role test-role --verb=get,list --resource=pods -n staging
kubectl create rolebinding test-binding \
  --role=test-role --user=testuser -n staging
```

**Структура ошибки Forbidden:** при отказе в запросе API-сервер возвращает HTTP 403 со структурированным сообщением:

```
User "system:serviceaccount:production:ci-deployer" cannot update resource
"deployments" in API group "apps" in the namespace "production"
```

В сообщении есть все три элемента, необходимые для исправления: **субъект** (`system:serviceaccount:production:ci-deployer`), **действие и ресурс** (`update deployments` в `apps`) и **пространство имён** (`production`). Сопоставьте каждое поле с правилом, которое нужно добавить.

**Неизменяемость `roleRef`:** поле `roleRef` в `RoleBinding` и `ClusterRoleBinding` нельзя изменить после создания. Если нужно привязать другую роль, удалите и создайте привязку заново. Список субъектов при этом можно менять.

**`--as` — не полноценная имперсонация:** `kubectl auth can-i --as=X` спрашивает API-сервер, разрешено ли действие пользователю X, но не создаёт kubeconfig, работающий от имени X. Для реальной имперсонации требуется разрешение `impersonate` на ресурсах `users`, `groups` или `serviceaccounts`. Это мощное разрешение, которое следует ограничить администраторами платформы.

---

## Примеры

### Пример 1. CI/CD-конвейер с ограниченными правами на развёртывание

CI-конвейеру нужно обновлять Deployment и читать ConfigMap и Secret только в пространстве имён `production`. Другие ресурсы и пространства имён ему не нужны.

```yaml
# ci-deployer-rbac.yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ci-deployer
  namespace: production
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: ci-deployer-role
  namespace: production
rules:
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "patch", "update"]
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["secrets"]        # pipeline reads image pull credentials
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["pods"]           # needed to poll rollout status
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["replicasets"]    # kubectl rollout status reads replicasets
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ci-deployer-binding
  namespace: production
subjects:
  - kind: ServiceAccount
    name: ci-deployer
    namespace: production
roleRef:
  kind: Role
  name: ci-deployer-role
  apiGroup: rbac.authorization.k8s.io
```

**Apply and verify:**

```bash
kubectl apply -f ci-deployer-rbac.yaml

# Confirm the SA can patch deployments
kubectl auth can-i patch deployments -n production \
  --as=system:serviceaccount:production:ci-deployer

# Confirm it cannot delete anything
kubectl auth can-i delete deployments -n production \
  --as=system:serviceaccount:production:ci-deployer
# Expected: no

# Confirm it has no access outside production
kubectl auth can-i get pods -n staging \
  --as=system:serviceaccount:production:ci-deployer
# Expected: no
```

### Пример 2. Агент мониторинга с правом чтения во всём кластере

Prometheus требуется доступ на чтение Pod, Service и Endpoint во всех пространствах имён, а также метрик узлов и URL, не являющихся ресурсами Kubernetes. Это подходящий случай для ClusterRoleBinding, поскольку мониторинг охватывает весь кластер.

```yaml
# prometheus-rbac.yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: prometheus
  namespace: monitoring
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prometheus-reader
rules:
  - apiGroups: [""]
    resources: ["nodes", "nodes/proxy", "nodes/metrics", "services",
                "endpoints", "pods", "configmaps"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["networking.k8s.io"]
    resources: ["ingresses"]
    verbs: ["get", "list", "watch"]
  - nonResourceURLs: ["/metrics", "/metrics/cadvisor", "/healthz", "/version"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: prometheus-reader-binding
subjects:
  - kind: ServiceAccount
    name: prometheus
    namespace: monitoring          # namespace is required even in ClusterRoleBinding
roleRef:
  kind: ClusterRole
  name: prometheus-reader
  apiGroup: rbac.authorization.k8s.io
```

```bash
kubectl apply -f prometheus-rbac.yaml

# Verify cluster-wide pod read access
kubectl auth can-i list pods --all-namespaces \
  --as=system:serviceaccount:monitoring:prometheus
# Expected: yes

# Verify it cannot create or delete anything
kubectl auth can-i create pods -n default \
  --as=system:serviceaccount:monitoring:prometheus
# Expected: no

# Verify non-resource URL access
kubectl auth can-i get /metrics \
  --as=system:serviceaccount:monitoring:prometheus
# Expected: yes
```

### Пример 3. Доступ разработчика к пространству имён с повторным использованием ClusterRole

A platform team wants all developers to have `edit` access within their team's namespace, but not outside it. Rather than creating identical Roles in each namespace, they bind the built-in `edit` ClusterRole via a namespace-scoped `RoleBinding`.

```bash
# Create the namespace for the team
kubectl create namespace team-alpha

# Bind the built-in edit ClusterRole — scoped to team-alpha only
# This is the ClusterRole-via-RoleBinding reuse pattern
kubectl create rolebinding team-alpha-edit \
  --clusterrole=edit \
  --group=team-alpha-developers \   # maps to OIDC group or cert O= field
  --namespace=team-alpha

# Verify a developer can create deployments in their namespace
kubectl auth can-i create deployments -n team-alpha \
  --as=alice --as-group=team-alpha-developers
# Expected: yes

# Verify they cannot touch other namespaces
kubectl auth can-i create deployments -n production \
  --as=alice --as-group=team-alpha-developers
# Expected: no

# Verify they cannot manage RBAC (edit role does not include this)
kubectl auth can-i create rolebindings -n team-alpha \
  --as=alice --as-group=team-alpha-developers
# Expected: no
```

### Example 4: Audit Who Has cluster-admin

Before a security review, you need to enumerate every subject that has been granted `cluster-admin`, either directly via ClusterRoleBinding or indirectly via RoleBinding in any namespace.

```bash
# Find all ClusterRoleBindings to cluster-admin
echo "=== ClusterRoleBindings to cluster-admin ==="
kubectl get clusterrolebindings -o json | jq -r '
  .items[]
  | select(.roleRef.name == "cluster-admin")
  | "Binding: \(.metadata.name) | Subjects: \(.subjects // [] | map("\(.kind)/\(.name)") | join(", "))"
'

# Find all RoleBindings to cluster-admin across all namespaces
# (less common, but valid — grants cluster-admin within the binding's namespace)
echo "=== RoleBindings to cluster-admin ==="
kubectl get rolebindings -A -o json | jq -r '
  .items[]
  | select(.roleRef.name == "cluster-admin")
  | "Namespace: \(.metadata.namespace) | Binding: \(.metadata.name) | Subjects: \(.subjects // [] | map("\(.kind)/\(.name)") | join(", "))"
'

# Export all bindings for offline audit
kubectl get clusterrolebindings,rolebindings -A -o yaml > rbac-audit-$(date +%Y%m%d).yaml
```

---

## Практические задания

### Exercise 1: Build a Read-Only Namespace Role

**Goal:** Practice translating a permission requirement into a correct Role and RoleBinding.

Create a namespace called `sandbox`. In that namespace, create a ServiceAccount named `auditor`. Write a Role that allows the `auditor` SA to list and get Pods, Deployments, Services, and ConfigMaps — but explicitly does **not** grant access to Secrets or the ability to exec into pods. Bind the role to the SA.

Verify your work:
- `kubectl auth can-i list pods -n sandbox --as=system:serviceaccount:sandbox:auditor` → `yes`
- `kubectl auth can-i get secrets -n sandbox --as=system:serviceaccount:sandbox:auditor` → `no`
- `kubectl auth can-i create pods/exec -n sandbox --as=system:serviceaccount:sandbox:auditor` → `no`

**Hint:** You do not need to explicitly deny Secrets. Think about what "additive only" means for what you omit.

---

### Exercise 2: Diagnose and Fix a Forbidden Error

**Goal:** Practice reading 403 errors and tracing them back to missing rules.

Apply the following ServiceAccount and RoleBinding to a `test` namespace:

```yaml
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: job-runner
  namespace: test
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: job-runner-role
  namespace: test
rules:
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["create", "get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: job-runner-binding
  namespace: test
subjects:
  - kind: ServiceAccount
    name: job-runner
    namespace: test
roleRef:
  kind: Role
  name: job-runner-role
  apiGroup: rbac.authorization.k8s.io
```

Now run this check and observe it fails:

```bash
kubectl auth can-i delete jobs -n test \
  --as=system:serviceaccount:test:job-runner
```

Without re-creating the RoleBinding, modify the Role so the `job-runner` SA can also delete Jobs. Verify the fix works, then check that it still cannot delete Pods — confirming you only added what was needed.

---

### Exercise 3: ClusterRole Reuse vs ClusterRoleBinding

**Goal:** Understand the difference between namespace-scoped and cluster-wide grants by observing both in practice.

1. Create a ClusterRole called `secret-reader` that grants `get` and `list` on Secrets.
2. Create two namespaces: `ns-a` and `ns-b`.
3. Create a ServiceAccount `secret-sa` in `ns-a`.
4. Bind `secret-reader` to `secret-sa` using a **RoleBinding** in `ns-a` only.
5. Verify:
   - The SA can list Secrets in `ns-a` → `yes`
   - The SA cannot list Secrets in `ns-b` → `no`
6. Now create a **ClusterRoleBinding** for the same SA to the same ClusterRole.
7. Re-run the check against `ns-b` — it should now return `yes`.
8. **Cleanup:** Delete the ClusterRoleBinding to restore least-privilege.

Explain in your own words why step 4 does not grant cluster-wide access despite using a ClusterRole.

---

### Exercise 4: Harden the Default ServiceAccount

**Goal:** Apply the automount hardening baseline to a realistic namespace setup.

1. Create a namespace called `hardened`.
2. Deploy a simple Pod that does not need Kubernetes API access:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: no-api-access
  namespace: hardened
spec:
  containers:
    - name: app
      image: busybox
      command: ["sleep", "3600"]
```

3. Exec into the pod and check whether a service account token is mounted:

```bash
kubectl exec -n hardened no-api-access -- \
  ls /var/run/secrets/kubernetes.io/serviceaccount/
```

4. Patch the `default` ServiceAccount in the `hardened` namespace to disable automounting:

```bash
kubectl patch serviceaccount default -n hardened \
  -p '{"automountServiceAccountToken": false}'
```

5. Delete and recreate the Pod. Exec in again and verify the token directory is no longer present.

6. As a follow-up: what happens if you set `automountServiceAccountToken: false` on the ServiceAccount but `automountServiceAccountToken: true` on the Pod spec? Check the Kubernetes documentation to confirm which takes precedence, then verify your answer by testing it.

---

### Быстрая проверка

7. Count verbs in an RBAC rule. Run: `printf 'verbs: ["get", "list", "watch"]\n' | tr ',' '\n' | grep -c '"'`

```expected_output
3
```

hint: Think about how you can split a comma-separated string into separate lines and then count occurrences of a specific character pattern.
hint: Use `tr ',' '\n'` to split on commas, then pipe to `grep -c` with a quote character as the pattern to count matching lines.

8. Extract the subject kind from a RoleBinding stub. Run: `printf 'subjects:\n- kind: ServiceAccount\n  name: myapp\n' | awk '/kind:/{print $2; exit}'`

```expected_output
ServiceAccount
```

hint: Consider using a stream processing tool that can match lines by pattern and extract specific fields from the matched line.
hint: Use awk with a pattern like /kind:/ to match the relevant line, then print the second field with $2 and use exit to stop after the first match.
