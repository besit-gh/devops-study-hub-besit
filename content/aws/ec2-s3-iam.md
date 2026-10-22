---
title: EC2, S3 и IAM
module: aws
duration_min: 35
difficulty: intermediate
tags: [aws, ec2, s3, iam, instances, buckets, policies, roles, permissions]
exercises: 4
---

## Обзор
EC2, S3 и IAM — основа большинства развёртываний в AWS. EC2 предоставляет виртуальные машины, S3 — объектное хранилище, а IAM управляет тем, кто и к каким ресурсам может обращаться. Понимание взаимодействия этих компонентов, особенно модели пользователей, ролей и политик IAM, необходимо для работы с другими сервисами AWS.

## Основные понятия

### EC2 — Elastic Compute Cloud

#### Типы экземпляров
```
t3.micro      — burstable, 2 vCPU, 1 GB RAM     (dev/test, free tier)
t3.medium     — burstable, 2 vCPU, 4 GB RAM
m6i.large     — general purpose, 2 vCPU, 8 GB RAM
c6i.xlarge    — compute optimized, 4 vCPU, 8 GB RAM
r6i.large     — memory optimized, 2 vCPU, 16 GB RAM
g4dn.xlarge   — GPU instance (ML inference, graphics)
```

Шаблон имени: `<family><generation><attributes>.<size>` — `m6i.xlarge` означает семейство M, поколение 6, Intel, размер extra large.

#### Запуск экземпляра
```bash
# Запуск через CLI
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.micro \
  --key-name my-keypair \
  --security-group-ids sg-12345678 \
  --subnet-id subnet-12345678 \
  --iam-instance-profile Name=MyEC2Role \
  --user-data file://startup.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=myapp}]'

# Показать запущенные экземпляры
aws ec2 describe-instances \
  --filters Name=instance-state-name,Values=running \
  --query 'Reservations[*].Instances[*].[InstanceId,PublicIpAddress,Tags[?Key==`Name`].Value|[0]]' \
  --output table

# Подключиться по SSH
ssh -i ~/.ssh/my-keypair.pem ec2-user@<public-ip>

# Остановить / завершить
aws ec2 stop-instances --instance-ids i-1234567890abcdef0
aws ec2 terminate-instances --instance-ids i-1234567890abcdef0
```

#### User Data (скрипт запуска)
```bash
#!/bin/bash
set -euo pipefail
yum update -y
yum install -y docker
systemctl enable --now docker
usermod -aG docker ec2-user
```

Выполняется один раз при первой загрузке от имени root. Используйте его для установки пакетов, получения конфигураций и запуска служб.

#### Профили экземпляров
Профиль экземпляра — механизм назначения роли IAM экземпляру EC2. Когда код на EC2 вызывает `boto3.client('s3')`, он автоматически получает временные учётные данные через сервис метаданных экземпляра по адресу `169.254.169.254`.

```bash
# Проверить, какую роль использует экземпляр
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

---

### S3 — Simple Storage Service

#### Основные операции
```bash
# Создать бакет
aws s3 mb s3://my-unique-bucket-name --region us-east-1

# Загрузить или скачать
aws s3 cp ./file.txt s3://my-bucket/folder/file.txt
aws s3 cp s3://my-bucket/folder/file.txt ./file.txt

# Синхронизировать каталог
aws s3 sync ./dist s3://my-bucket/dist --delete

# Показать список
aws s3 ls s3://my-bucket/
aws s3 ls s3://my-bucket/ --recursive --human-readable

# Удалить
aws s3 rm s3://my-bucket/file.txt
aws s3 rm s3://my-bucket/folder/ --recursive
```

#### Политика бакета
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCIAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789:role/github-actions-role"
      },
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::my-bucket/*"
    }
  ]
}
```

#### Версионирование и жизненный цикл
```bash
# Включить версионирование
aws s3api put-bucket-versioning \
  --bucket my-bucket \
  --versioning-configuration Status=Enabled

# Правило жизненного цикла (перенести в Glacier через 90 дней, удалить через 365)
aws s3api put-bucket-lifecycle-configuration \
  --bucket my-bucket \
  --lifecycle-configuration file://lifecycle.json
```

#### Предварительно подписанные URL (доступ на ограниченное время)
```python
import boto3

s3 = boto3.client('s3')
url = s3.generate_presigned_url(
    'get_object',
    Params={'Bucket': 'my-bucket', 'Key': 'reports/q4.pdf'},
    ExpiresIn=3600   # 1 hour
)
# Любой обладатель этого URL может скачать файл в течение часа без аутентификации
```

---

### IAM — управление идентификацией и доступом

#### Основные понятия
```
Users       — human identities (use roles instead wherever possible)
Groups      — collections of users sharing the same policies
Roles       — assumed by services, EC2 instances, Lambda, CI pipelines
Policies    — JSON documents that define permissions
```

**Главное правило: предоставляйте минимально необходимые привилегии.** Начните без разрешений и добавляйте только те, которые действительно нужны.

#### Типы политик
```
Identity-based policies  — attached to IAM users, groups, or roles
Resource-based policies  — attached to the resource itself (S3 bucket policy, SQS queue policy)
Service control policies — applied at AWS Organizations level (affect entire accounts)
```

#### Написание политики
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::my-app-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::my-app-bucket"
    }
  ]
}
```

#### Роль IAM для сервиса
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Эта политика доверия разрешает экземплярам EC2 принимать данную роль. Укажите её при создании роли, а политики разрешений используйте для определения доступных роли действий.

#### Операции через CLI
```bash
# Создать роль с политикой доверия
aws iam create-role \
  --role-name MyAppRole \
  --assume-role-policy-document file://trust-policy.json

# Присоединить управляемую политику к роли
aws iam attach-role-policy \
  --role-name MyAppRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Присоединить встроенную политику
aws iam put-role-policy \
  --role-name MyAppRole \
  --policy-name S3WriteAccess \
  --policy-document file://s3-write-policy.json

# Кто я?
aws sts get-caller-identity

# Смоделировать политику и проверить разрешённые действия
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789:role/MyAppRole \
  --action-names s3:PutObject \
  --resource-arns arn:aws:s3:::my-bucket/*
```

#### Лучшие практики IAM
```
✓ Use roles for everything — EC2, Lambda, EKS pods (never hardcode keys)
✓ Enable MFA on root and human IAM users
✓ Enable CloudTrail to log all API calls
✓ Use IAM Access Analyzer to find over-permissive policies
✓ Rotate access keys regularly (or eliminate them with OIDC)
✗ Never use root account for day-to-day operations
✗ Never embed access keys in code or Docker images
```

## Примеры

### Настройка роли для развёртывания
```bash
# 1. Создать политику доверия (разрешает GitHub Actions принимать роль)
cat > trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::123456789:oidc-provider/token.actions.githubusercontent.com" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:myorg/myrepo:*"
      }
    }
  }]
}
EOF

# 2. Создать роль
aws iam create-role --role-name github-actions-deploy --assume-role-policy-document file://trust-policy.json

# 3. Назначить разрешения для развёртывания
aws iam put-role-policy \
  --role-name github-actions-deploy \
  --policy-name deploy-permissions \
  --policy-document file://deploy-policy.json
```

## Практические задания

1. Запустите экземпляр EC2 типа `t3.micro` со скриптом user data, который устанавливает и запускает nginx. Подключитесь по SSH и проверьте, что nginx работает. Затем получите сведения об экземпляре через AWS CLI и извлеките публичный IP с помощью `--query`.
2. Создайте бакет S3 с включённым версионированием. Загрузите три версии одного файла. Просмотрите их командой `aws s3api list-object-versions`. Удалите последнюю версию и убедитесь, что предыдущая по-прежнему доступна.
3. Создайте роль IAM для EC2 с политикой, разрешающей только чтение из конкретного бакета S3. Назначьте роль экземпляру EC2. Подключитесь по SSH и проверьте, что `aws s3 ls s3://your-bucket` работает без ручной настройки учётных данных.
4. Напишите политику IAM с минимальными привилегиями, разрешающую только `s3:PutObject` для пути `s3:::my-bucket/uploads/*`. Проверьте её командой `aws iam simulate-principal-policy`, затем добавьте `s3:DeleteObject` и повторите проверку.


---

### Быстрая проверка

5. Извлеките имя бакета S3 из ARN. Выполните: `echo "arn:aws:s3:::my-app-bucket-prod" | cut -d: -f6`

```expected_output
my-app-bucket-prod
```

Подсказка: разделите строку по двоеточиям и выберите нужное поле.
Подсказка: задайте двоеточие как разделитель в `cut` с помощью `-d:`, затем выберите шестое поле ARN флагом `-f6`.

6. Извлеките ID аккаунта из ARN IAM. Выполните: `echo "arn:aws:iam::123456789012:role/MyRole" | cut -d: -f5`

```expected_output
123456789012
```

Подсказка: разделите строку по разделителю и выберите нужное поле.
Подсказка: задайте двоеточие как разделитель в `cut` с помощью `-d:`, затем выберите пятое поле переданного ввода флагом `-f5`.
