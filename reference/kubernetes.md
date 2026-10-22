# Kubernetes — краткая справка

## Основы kubectl

| Command | Description |
|---------|-------------|
| `kubectl get pods` | Список pod в текущем пространстве имён |
| `kubectl get pods -A` | Список pod во всех пространствах имён |
| `kubectl get all` | Список всех ресурсов |
| `kubectl get pods -o wide` | Показать узел и IP-адрес |
| `kubectl get pod NAME -o yaml` | Вывести полную спецификацию YAML |
| `kubectl describe pod NAME` | Подробные сведения о pod и событиях |
| `kubectl apply -f file.yaml` | Применить манифест |
| `kubectl delete -f file.yaml` | Удалить ресурсы, описанные в манифесте |
| `kubectl delete pod NAME` | Удалить конкретный pod |

## Пространства имён и контекст

| Command | Description |
|---------|-------------|
| `kubectl config get-contexts` | Список контекстов |
| `kubectl config use-context ctx` | Переключить контекст |
| `kubectl config current-context` | Показать активный контекст |
| `kubectl get ns` | Список пространств имён |
| `kubectl create ns name` | Создать пространство имён |
| `kubectl -n ns get pods` | Pod в указанном пространстве имён |
| `kubectl config set-context --current --namespace=ns` | Задать пространство имён по умолчанию |

## Рабочие нагрузки

| Command | Description |
|---------|-------------|
| `kubectl create deployment name --image=img` | Создать Deployment |
| `kubectl scale deploy name --replicas=3` | Изменить число реплик Deployment |
| `kubectl rollout status deploy name` | Следить за обновлением Deployment |
| `kubectl rollout undo deploy name` | Откатить Deployment |
| `kubectl rollout history deploy name` | История обновлений |
| `kubectl set image deploy name app=img:tag` | Обновить образ |
| `kubectl get deploy` | Список Deployment |
| `kubectl get rs` | Список ReplicaSet |

## Сервисы и сеть

| Command | Description |
|---------|-------------|
| `kubectl get svc` | Список Service |
| `kubectl expose deploy name --port=80 --type=ClusterIP` | Опубликовать Deployment как Service |
| `kubectl port-forward pod NAME 8080:80` | Переадресовать локальный порт в pod |
| `kubectl port-forward svc NAME 8080:80` | Переадресовать порт в Service |
| `kubectl get ingress` | Список Ingress |
| `kubectl get endpoints` | Показать конечные точки Service |

## Отладка

| Command | Description |
|---------|-------------|
| `kubectl logs pod NAME` | Журналы pod |
| `kubectl logs -f pod NAME` | Следить за журналом |
| `kubectl logs pod NAME -c container` | Указать конкретный контейнер |
| `kubectl logs pod NAME --previous` | Предыдущий контейнер (завершившийся с ошибкой) |
| `kubectl exec -it pod NAME -- bash` | Открыть shell в pod |
| `kubectl exec -it pod NAME -c ctr -- sh` | Указать конкретный контейнер |
| `kubectl top pods` | Использование CPU и памяти |
| `kubectl top nodes` | Использование ресурсов узла |
| `kubectl events --sort-by=.lastTimestamp` | Sorted events |

## Config & Secrets

| Command | Description |
|---------|-------------|
| `kubectl get configmap` | List ConfigMaps |
| `kubectl describe configmap NAME` | Show ConfigMap data |
| `kubectl create configmap NAME --from-file=file` | Create from file |
| `kubectl get secret` | List secrets |
| `kubectl get secret NAME -o jsonpath='{.data.key}' \| base64 -d` | Decode secret |
| `kubectl create secret generic NAME --from-literal=k=v` | Create secret |

## Resource Management

| Command | Description |
|---------|-------------|
| `kubectl get nodes` | List cluster nodes |
| `kubectl describe node NAME` | Node details + capacity |
| `kubectl cordon node NAME` | Mark node unschedulable |
| `kubectl drain node NAME` | Evict pods from node |
| `kubectl uncordon node NAME` | Re-enable scheduling |
| `kubectl label pod NAME key=val` | Add label |
| `kubectl annotate pod NAME key=val` | Add annotation |
| `kubectl taint node NAME key=val:NoSchedule` | Add taint |
