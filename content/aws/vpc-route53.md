---
title: VPC и Route 53
module: aws
duration_min: 25
difficulty: intermediate
tags: [aws, vpc, subnets, route53, networking, nat-gateway, security-groups, dns]
exercises: 4
---

## Обзор
VPC предоставляет приватную изолированную сеть в AWS, а Route 53 — DNS-сервис AWS. Вместе они определяют, как трафик попадает в инфраструктуру, маршрутизируется между сервисами и как внешние клиенты находят ваши endpoint. Многие реальные проблемы инфраструктуры связаны с ошибками VPC: неверной таблицей маршрутизации, слишком широкими правилами security group или отсутствующим NAT Gateway.

## Основные понятия

### Структура VPC
```
VPC (10.0.0.0/16)
├── Public Subnet (10.0.1.0/24) — AZ us-east-1a
│   └── EC2 instances accessible from internet
│   └── Internet Gateway (IGW) route
├── Public Subnet (10.0.2.0/24) — AZ us-east-1b
├── Private Subnet (10.0.10.0/24) — AZ us-east-1a
│   └── RDS, internal services
│   └── NAT Gateway route (for outbound internet)
└── Private Subnet (10.0.11.0/24) — AZ us-east-1b
```

**Публичная подсеть** имеет маршрут к Internet Gateway (IGW).
**Приватная подсеть** не имеет маршрута к IGW; исходящий доступ в интернет обеспечивается через NAT Gateway.

### Создание VPC через CLI
```bash
# Создать VPC
VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --query 'Vpc.VpcId' --output text)
aws ec2 create-tags --resources $VPC_ID --tags Key=Name,Value=prod-vpc

# Включить DNS-имена узлов (требуется некоторым сервисам)
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames

# Создать подсети
aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.1.0/24 \
  --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=public-1a}]'

# Создать и подключить Internet Gateway
IGW_ID=$(aws ec2 create-internet-gateway --query 'InternetGateway.InternetGatewayId' --output text)
aws ec2 attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID

# Создать таблицу маршрутизации публичной подсети
RT_ID=$(aws ec2 create-route-table --vpc-id $VPC_ID --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id $RT_ID --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID
aws ec2 associate-route-table --route-table-id $RT_ID --subnet-id <public-subnet-id>
```

### NAT Gateway
Приватным подсетям нужен NAT Gateway для исходящего доступа в интернет (установка пакетов, API-запросы):

```bash
# Выделить Elastic IP для NAT Gateway
EIP=$(aws ec2 allocate-address --domain vpc --query 'AllocationId' --output text)

# Создать NAT Gateway в ПУБЛИЧНОЙ подсети
NAT_ID=$(aws ec2 create-nat-gateway \
  --subnet-id <public-subnet-id> \
  --allocation-id $EIP \
  --query 'NatGateway.NatGatewayId' --output text)

# Таблица маршрутизации приватной подсети: направить исходящий трафик через NAT
PRIVATE_RT=$(aws ec2 create-route-table --vpc-id $VPC_ID --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id $PRIVATE_RT --destination-cidr-block 0.0.0.0/0 --nat-gateway-id $NAT_ID
aws ec2 associate-route-table --route-table-id $PRIVATE_RT --subnet-id <private-subnet-id>
```

NAT Gateway стоит примерно $0,045 в час плюс $0,045 за каждый обработанный гигабайт. Для высокой доступности рекомендуется отдельный шлюз в каждой зоне доступности.

### Группы безопасности и NACL
```
Security Groups                 NACLs
─────────────────               ─────────────────
Stateful (track connections)    Stateless (explicit in+out rules needed)
Applied to instances/ENIs       Applied to subnets
Allow rules only                Allow AND deny rules
Evaluated all at once           Evaluated in rule number order
Default: deny all inbound       Default: allow all (VPC default NACL)
```

```bash
# Группа безопасности веб-серверов
SG_ID=$(aws ec2 create-security-group \
  --group-name web-sg \
  --description "Web server security group" \
  --vpc-id $VPC_ID \
  --query 'GroupId' --output text)

# Разрешить HTTPS из любых источников
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp --port 443 --cidr 0.0.0.0/0

# Разрешить SSH только с конкретного IP
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp --port 22 --cidr 203.0.113.0/32

# Разрешить трафик приложения из другой группы безопасности (не по CIDR)
aws ec2 authorize-security-group-ingress \
  --group-id $DB_SG_ID \
  --protocol tcp --port 5432 \
  --source-group $APP_SG_ID
```

### Конечные точки VPC
Доступ к сервисам AWS без выхода из сети AWS:

```bash
# Gateway endpoint для S3 (бесплатно — трафик остаётся в магистральной сети AWS)
aws ec2 create-vpc-endpoint \
  --vpc-id $VPC_ID \
  --service-name com.amazonaws.us-east-1.s3 \
  --route-table-ids $PRIVATE_RT

# Interface endpoint для Secrets Manager (создаёт ENI в вашей подсети)
aws ec2 create-vpc-endpoint \
  --vpc-id $VPC_ID \
  --vpc-endpoint-type Interface \
  --service-name com.amazonaws.us-east-1.secretsmanager \
  --subnet-ids <private-subnet-id> \
  --security-group-ids $SG_ID
```

---

### Route 53

#### Хостинговые зоны и записи
```bash
# Создать hosted zone (публичную — для DNS, доступного из интернета)
aws route53 create-hosted-zone \
  --name myapp.com \
  --caller-reference $(date +%s)

# Получить ID hosted zone
HZ_ID=$(aws route53 list-hosted-zones-by-name \
  --dns-name myapp.com \
  --query 'HostedZones[0].Id' --output text | cut -d/ -f3)

# Создать или обновить запись A
aws route53 change-resource-record-sets \
  --hosted-zone-id $HZ_ID \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "api.myapp.com",
        "Type": "A",
        "TTL": 300,
        "ResourceRecords": [{"Value": "203.0.113.10"}]
      }
    }]
  }'

# Alias-запись (для ALB/CloudFront — TTL не требуется)
aws route53 change-resource-record-sets \
  --hosted-zone-id $HZ_ID \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "myapp.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "Z35SXDOTRQ7X7K",
          "DNSName": "my-alb-1234567890.us-east-1.elb.amazonaws.com",
          "EvaluateTargetHealth": true
        }
      }
    }]
  }'
```

#### Политики маршрутизации
```
Simple           — single record, single value (default)
Weighted         — distribute traffic by weight (A/B testing, gradual rollout)
Latency          — route to region with lowest latency for the user
Failover         — primary/secondary, switch on health check failure
Geolocation      — route by user's country or continent
Geoproximity     — route by proximity, with configurable bias
```

```bash
# Взвешенная маршрутизация — 10% трафика на canary
aws route53 change-resource-record-sets --hosted-zone-id $HZ_ID \
  --change-batch '{
    "Changes": [
      {
        "Action": "UPSERT",
        "ResourceRecordSet": {
          "Name": "api.myapp.com", "Type": "A",
          "SetIdentifier": "primary", "Weight": 90,
          "TTL": 60, "ResourceRecords": [{"Value": "203.0.113.10"}]
        }
      },
      {
        "Action": "UPSERT",
        "ResourceRecordSet": {
          "Name": "api.myapp.com", "Type": "A",
          "SetIdentifier": "canary", "Weight": 10,
          "TTL": 60, "ResourceRecords": [{"Value": "203.0.113.20"}]
        }
      }
    ]
  }'
```

#### Проверки состояния
```bash
# Создать проверку состояния endpoint
HC_ID=$(aws route53 create-health-check \
  --caller-reference $(date +%s) \
  --health-check-config '{
    "IPAddress": "203.0.113.10",
    "Port": 443,
    "Type": "HTTPS",
    "ResourcePath": "/health",
    "FailureThreshold": 3,
    "RequestInterval": 30
  }' \
  --query 'HealthCheck.Id' --output text)
```

Свяжите проверку состояния с DNS-записью: при политиках failover и latency Route 53 перестанет направлять трафик на неработающие конечные точки.

## Примеры

### Стандартная трёхуровневая VPC (Terraform)
```hcl
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "prod-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["us-east-1a", "us-east-1b", "us-east-1c"]
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  private_subnets = ["10.0.10.0/24", "10.0.11.0/24", "10.0.12.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = false   # one per AZ for HA
}
```

## Практические задания

1. Создайте VPC с двумя публичными и двумя приватными подсетями в двух зонах доступности. Добавьте Internet Gateway для публичных подсетей и NAT Gateway (в одной публичной подсети) для приватных. Убедитесь, что экземпляр в приватной подсети выходит в интернет через NAT Gateway, выполнив `curl https://example.com`.
2. Создайте две группы безопасности: `web-sg` (разрешает порт 443 с `0.0.0.0/0`) и `app-sg` (разрешает порт 8080 только от `web-sg`). Покажите, что ограничение источника для `app-sg` группой `web-sg` блокирует прямой доступ из интернета.
3. Настройте Route 53 с публичной hosted zone. Создайте запись A и проверьте DNS-разрешение командой `dig`. Затем настройте взвешенную маршрутизацию — 80% запросов на один IP и 20% на другой — и проверьте её повторными запросами `dig`.
4. Настройте в Route 53 политику failover: основную запись на активный сервер с проверкой состояния и резервную — на standby. Имитируйте сбой, добившись неуспешной проверки, и убедитесь, что Route 53 переключается на резервную запись.


---

### Быстрая проверка

5. Рассчитайте количество доступных адресов узлов в подсети /24. Выполните: `python3 -c "print(2**(32-24) - 2)"`

```expected_output
254
```

Подсказка: общее число адресов минус зарезервированные адреса даёт количество адресов, доступных узлам.
Подсказка: используйте возведение в степень в Python: `2**(32-префикс)`, затем вычтите адрес сети и широковещательный адрес.

6. Посчитайте количество октетов в IPv4-адресе. Выполните: `echo "192.168.10.5" | tr '.' '\n' | wc -l`

```expected_output
4
```

Подсказка: разбейте IP-адрес на отдельные строки, а затем посчитайте их стандартными инструментами Unix.
Подсказка: используйте `tr`, чтобы заменить точки символами новой строки, а результат передайте в `wc -l` для подсчёта строк.
