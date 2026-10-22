# AWS — краткая справка

## Настройка CLI

| Command | Description |
|---------|-------------|
| `aws configure` | Задать ключ доступа, секрет, регион и формат |
| `aws configure list` | Показать текущую конфигурацию |
| `aws configure list-profiles` | Показать именованные профили |
| `aws --profile name cmd` | Использовать именованный профиль |
| `AWS_PROFILE=name aws cmd` | Выбрать профиль через переменную окружения |
| `aws sts get-caller-identity` | Проверить текущую идентичность |

## EC2

| Command | Description |
|---------|-------------|
| `aws ec2 describe-instances` | Список всех экземпляров |
| `aws ec2 describe-instances --filters "Name=tag:Name,Values=myapp"` | Фильтр по тегу |
| `aws ec2 start-instances --instance-ids i-xxx` | Запустить экземпляр |
| `aws ec2 stop-instances --instance-ids i-xxx` | Остановить экземпляр |
| `aws ec2 describe-images --owners amazon --filters "Name=name,Values=amzn2*"` | Найти AMI |
| `aws ec2 describe-security-groups` | Список групп безопасности |
| `aws ec2 describe-key-pairs` | Список пар ключей |

## S3

| Command | Description |
|---------|-------------|
| `aws s3 ls` | Список бакетов |
| `aws s3 ls s3://bucket/` | Список объектов бакета |
| `aws s3 cp file s3://bucket/path` | Загрузить файл |
| `aws s3 cp s3://bucket/path file` | Скачать файл |
| `aws s3 sync dir/ s3://bucket/` | Синхронизировать каталог с бакетом |
| `aws s3 sync s3://bucket/ dir/` | Синхронизировать бакет с каталогом |
| `aws s3 rm s3://bucket/path` | Удалить объект |
| `aws s3 rb s3://bucket --force` | Удалить бакет и его содержимое |
| `aws s3 presign s3://bucket/key --expires-in 3600` | Generate presigned URL |

## IAM

| Command | Description |
|---------|-------------|
| `aws iam list-users` | List IAM users |
| `aws iam list-roles` | List IAM roles |
| `aws iam list-policies --scope Local` | List custom policies |
| `aws iam get-role --role-name name` | Get role details |
| `aws iam attach-role-policy --role-name r --policy-arn arn` | Attach policy |
| `aws iam create-user --user-name name` | Создать пользователя |
| `aws iam create-access-key --user-name name` | Create access key |

## EKS

| Command | Description |
|---------|-------------|
| `aws eks list-clusters` | List EKS clusters |
| `aws eks describe-cluster --name name` | Cluster details |
| `aws eks update-kubeconfig --name name --region r` | Add cluster to kubeconfig |

## CloudWatch Logs

| Command | Description |
|---------|-------------|
| `aws logs describe-log-groups` | List log groups |
| `aws logs describe-log-streams --log-group-name name` | List streams |
| `aws logs tail /aws/lambda/func --follow` | Follow log stream |
| `aws logs filter-log-events --log-group-name name --filter-pattern "ERROR"` | Filter logs |

## Common Flags

| Flag | Description |
|------|-------------|
| `--region us-east-1` | Override region |
| `--output json` | JSON output |
| `--output text` | Plain text output |
| `--output table` | Tabular output |
| `--query 'Items[*].Name'` | JMESPath filter |
| `--no-paginate` | Disable auto-pagination |
| `--dry-run` | Validate without executing (EC2) |
