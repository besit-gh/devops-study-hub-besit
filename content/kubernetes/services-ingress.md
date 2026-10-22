---
title: Service и Ingress в Kubernetes
module: kubernetes
duration_min: 20
difficulty: intermediate
tags: [kubernetes, services, ingress, clusterip, nodeport, loadbalancer, networking]
exercises: 4
---

## Обзор
Pod эфемерны и при каждом пересоздании могут получать новые IP-адреса. Service предоставляет стабильную точку доступа и автоматически направляет запросы к здоровым Pod независимо от их текущих IP. Ingress маршрутизирует внешний HTTP/HTTPS-трафик к нужному Service по имени хоста или пути. Вместе они образуют сетевой слой, от которого зависит каждое приложение Kubernetes.

## Основные понятия

### Типы Service
| Тип | Откуда доступен | Применение |
|---|---|---|
| `ClusterIP` | Только внутри кластера | Внутреннее взаимодействие сервисов |
| `NodePort` | IP любого узла + порт | Простой внешний доступ, разработка и тестирование |
| `LoadBalancer` | Публичный IP (облачный балансировщик) | Внешний доступ в production |
| `ExternalName` | Внутри кластера | DNS-псевдоним внешнего имени хоста |

### ClusterIP (по умолчанию)
```yaml
apiVersion: v1
kind: Service
metadata:
  name: api-service
  namespace: production
spec:
  type: ClusterIP      # default — omit or explicit
  selector:
    app: api           # routes to Pods with this label
  ports:
    - port: 80         # port the Service listens on
      targetPort: 8080 # port the Pod container listens on
      protocol: TCP
```

Другие pod в кластере могут обращаться к сервису по следующим именам:
- `api-service` (то же пространство имён)
- `api-service.production` (короткая форма для другого пространства имён)
- `api-service.production.svc.cluster.local` (полное DNS-имя)

DNS Kubernetes автоматически разрешает имена — IP-адреса указывать не нужно.

### NodePort
```yaml
spec:
  type: NodePort
  selector:
    app: api
  ports:
    - port: 80
      targetPort: 8080
      nodePort: 30080   # optional — auto-assigned in 30000-32767 range if omitted
```

Доступен по адресу `<any-node-ip>:30080`. В production используется редко — обычно лучше выбрать LoadBalancer или Ingress.

### LoadBalancer
```yaml
spec:
  type: LoadBalancer
  selector:
    app: api
  ports:
    - port: 80
      targetPort: 8080
```

В облачных средах (EKS, GKE, AKS) создаётся настоящий облачный балансировщик и назначается публичный IP. Каждый Service типа LoadBalancer стоит денег: для каждого сервиса создаётся отдельный балансировщик. Для HTTP/HTTPS Ingress обычно экономичнее.

### Endpoints и выбор Pod
Service направляет трафик к pod с помощью селекторов меток. Контроллер Service поддерживает объект `Endpoints` — список IP-адресов готовых pod:

```bash
kubectl get endpoints api-service
# NAME          ENDPOINTS                         AGE
# api-service   10.0.1.5:8080,10.0.1.6:8080      5m
```

В Endpoints попадают только pod с подходящими метками, прошедшие readiness probe. Неработающие pod автоматически удаляются из списка.

### Ingress
Ingress маршрутизирует внешний HTTP/HTTPS-трафик по имени хоста или пути. В кластере должен быть установлен **Ingress Controller** (nginx-ingress, AWS ALB Controller, Traefik и т. п.).

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: myapp-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: letsencrypt-prod   # auto TLS
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.example.com
      secretName: api-tls-secret   # cert-manager populates this
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api-service
                port:
                  number: 80
    - host: app.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: api-service
                port:
                  number: 80
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend-service
                port:
                  number: 80
```

### Типы путей
| Тип | Поведение |
|---|---|
| `Exact` | Точное совпадение пути |
| `Prefix` | Совпадение с префиксом пути (самый распространённый вариант) |
| `ImplementationSpecific` | Поведение определяется контроллером |

### Разрешение DNS-имён внутри кластера
Каждый Service получает DNS-запись, которой управляет CoreDNS:
```
<service>.<namespace>.svc.cluster.local
```

```bash
# Test DNS from inside a pod
kubectl run -it --rm debug --image=alpine -- /bin/sh
# Inside pod:
nslookup api-service.production.svc.cluster.local
wget -qO- http://api-service.production/health
```

### Сетевые политики
Управляют трафиком между pod (требуется CNI-плагин с поддержкой NetworkPolicy, например Calico или Cilium):

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-netpol
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: frontend   # only frontend pods can reach api pods
      ports:
        - port: 8080
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: db
      ports:
        - port: 5432
```

## Примеры

### Полный стек: Deployment + Service + Ingress
```yaml
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: api
          image: myapi:v1.0.0
          ports:
            - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  selector:
    app: api
  ports:
    - port: 80
      targetPort: 8080
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
spec:
  ingressClassName: nginx
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 80
```

## Практические задания

1. Создайте Deployment и Service типа ClusterIP для pod с nginx. Изнутри кластера выполните `kubectl run -it --rm debug --image=busybox -- wget -qO- http://<service-name>` и проверьте, что имя сервиса разрешается корректно.
2. Измените тип Service на `NodePort`. Найдите назначенный порт узла командой `kubectl get svc` и обратитесь к сервису извне кластера по адресу `<node-ip>:<node-port>`.
3. Создайте ресурс Ingress, направляющий `api.local/v1` в один Service, а `api.local/v2` — в другой. Примените его и проверьте командой `curl -H "Host: api.local" http://<ingress-ip>/v1`.
4. Создайте NetworkPolicy, разрешающую pod с меткой `app: frontend` обращаться к pod с меткой `app: api` по порту 8080. Весь остальной входящий трафик запретите. Проверьте правило, создав оба типа pod и проверив соединение.


---

### Быстрая проверка

5. Извлеките `targetPort` из примера спецификации Service. Выполните: `printf 'ports:\n- port: 80\n  targetPort: 8080\n' | awk '/targetPort:/{print $2}'`

```expected_output
8080
```

Подсказка: найдите в YAML нужное поле и извлеките его значение.
Подсказка: используйте `awk` с шаблоном `/targetPort:/` и выведите второе поле через `{print $2}`.

6. Посчитайте правила host в примере Ingress. Выполните: `printf 'rules:\n- host: app.example.com\n- host: api.example.com\n- host: admin.example.com\n' | grep -c 'host:'`

```expected_output
3
```

Подсказка: отфильтруйте строки по шаблону и сразу получите число совпадений.
Подсказка: флаг `-c` команды `grep` считает совпавшие строки вместо их вывода. Используйте его с шаблоном `host:`.
