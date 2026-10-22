# Helm — краткая справка

## Основные команды

| Команда | Описание |
|---------|-------------|
| `helm install name chart` | Установить релиз |
| `helm install name chart -f values.yaml` | Установить с пользовательскими values |
| `helm install name chart --set key=val` | Установить с параметром через --set |
| `helm upgrade name chart` | Обновить релиз |
| `helm upgrade --install name chart` | Установить или обновить релиз |
| `helm uninstall name` | Удалить релиз |
| `helm list` | Список релизов в текущем пространстве имён |
| `helm list -A` | Список всех релизов |
| `helm status name` | Показать состояние релиза |
| `helm history name` | Показать историю релиза |

## Values и шаблоны

| Команда | Описание |
|---------|-------------|
| `helm show values chart` | Показать значения по умолчанию |
| `helm show chart chart` | Показать метаданные chart |
| `helm get values name` | Показать применённые values |
| `helm get manifest name` | Показать сформированные манифесты |
| `helm template name chart` | Сформировать шаблоны локально |
| `helm template name chart -f values.yaml` | Сформировать шаблоны с пользовательскими values |
| `helm lint chart/` | Проверить синтаксис chart |
| `helm diff upgrade name chart` | Предварительно просмотреть изменения (нужен плагин) |

## Откат и отладка

| Команда | Описание |
|---------|-------------|
| `helm rollback name 1` | Откатиться к ревизии 1 |
| `helm rollback name 0` | Откатиться к предыдущей ревизии |
| `helm test name` | Запустить тесты chart |
| `helm get notes name` | Показать заметки после установки |
| `helm upgrade name chart --debug --dry-run` | Dry run with debug output |
| `helm upgrade name chart --atomic` | Roll back automatically on failure |
| `helm upgrade name chart --timeout 5m0s` | Set timeout |

## Repositories

| Команда | Описание |
|---------|-------------|
| `helm repo add name url` | Add repository |
| `helm repo list` | List repos |
| `helm repo update` | Fetch latest charts |
| `helm repo remove name` | Remove repo |
| `helm search repo term` | Search in repos |
| `helm search hub term` | Search Artifact Hub |
| `helm pull repo/chart` | Download chart tarball |
| `helm pull repo/chart --untar` | Download and extract |

## Chart Development

| Команда | Описание |
|---------|-------------|
| `helm create name` | Scaffold new chart |
| `helm package chart/` | Упаковать чарт to tarball |
| `helm dependency update chart/` | Download chart dependencies |
| `helm dependency list chart/` | List dependencies |

## Common Flags

| Flag | Описание |
|------|-------------|
| `-n namespace` | Target namespace |
| `--create-namespace` | Create namespace if missing |
| `--wait` | Wait until all resources are ready |
| `--timeout 5m0s` | Override default timeout |
| `--dry-run` | Simulate without applying |
| `--debug` | Enable verbose output |
| `--set key=val` | Override single value |
| `-f values.yaml` | Переопределить values file |
