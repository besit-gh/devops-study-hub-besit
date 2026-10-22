# AWS — краткая справка

## Настройка CLI

| Команда | Описание |
|---------|-------------|
| `aws configure` | Задать ключ доступа, секрет, регион и формат |
| `aws configure list` | Показать текущую конфигурацию |
| `aws configure list-profiles` | Показать именованные профили |
| `aws --profile name cmd` | Использовать именованный профиль |
| `AWS_PROFILE=name aws cmd` | Выбрать профиль через переменную окружения |
| `aws sts get-caller-identity` | Проверить текущую идентичность |

## EC2

| Команда | Описание |
|---------|-------------|
| `aws ec2 describe-instances` | Список всех экземпляров |
| `aws ec2 describe-instances --filters "Name=tag:Name,Values=myapp"` | Фильтр по тегу |
| `aws ec2 start-instances --instance-ids i-xxx` | Запустить экземпляр |
| `aws ec2 stop-instances --instance-ids i-xxx` | Остановить экземпляр |
| `aws ec2 describe-images --owners amazon --filters "Name=name,Values=amzn2*"` | Найти AMI |
| `aws ec2 describe-security-groups` | Список групп безопасности |
| `aws ec2 describe-key-pairs` | Список пар ключей |

## S3

| Команда | Описание |
|---------|-------------|
| `aws s3 ls` | Список бакетов |
| `aws s3 ls s3://bucket/` | Список объектов бакета |
| `aws s3 cp file s3://bucket/path` | Загрузить файл |
| `aws s3 cp s3://bucket/path file` | Скачать файл |
| `aws s3 sync dir/ s3://bucket/` | Синхронизировать каталог с бакетом |
| `aws s3 sync s3://bucket/ dir/` | Синхронизировать бакет с каталогом |
| `aws s3 rm s3://bucket/path` | Удалить объект |
| `aws s3 rb s3://bucket --force` | Удалить бакет и его содержимое |
| `aws s3 presign s3://bucket/key --expires-in 3600` | Создать предварительно подписанный URL |

## IAM

| Команда | Описание |
|---------|-------------|
| `aws iam list-users` | Список пользователей IAM |
| `aws iam list-roles` | Список ролей IAM |
| `aws iam list-policies --scope Local` | Список пользовательских политик |
| `aws iam get-role --role-name name` | Получить сведения о роли |
| `aws iam attach-role-policy --role-name r --policy-arn arn` | Присоединить политику |
| `aws iam create-user --user-name name` | Создать пользователя |
| `aws iam create-access-key --user-name name` | Создать ключ доступа |

## EKS

| Команда | Описание |
|---------|-------------|
| `aws eks list-clusters` | Список кластеров EKS |
| `aws eks describe-cluster --name name` | Сведения о кластере |
| `aws eks update-kubeconfig --name name --region r` | Добавить кластер в kubeconfig |

## CloudWatch Logs

| Команда | Описание |
|---------|-------------|
| `aws logs describe-log-groups` | Список групп журналов |
| `aws logs describe-log-streams --log-group-name name` | Список потоков журналов |
| `aws logs tail /aws/lambda/func --follow` | Следить за потоком журнала |
| `aws logs filter-log-events --log-group-name name --filter-pattern "ERROR"` | Фильтровать журналы |

## Common Flags

| Flag | Описание |
|------|-------------|
| `--region us-east-1` | Переопределить регион |
| `--output json` | Вывод в формате JSON |
| `--output text` | Текстовый вывод |
| `--output table` | Табличный вывод |
| `--query 'Items[*].Name'` | Фильтр JMESPath |
| `--no-paginate` | Отключить автоматическую пагинацию |
| `--dry-run` | Проверить без выполнения (EC2) |
