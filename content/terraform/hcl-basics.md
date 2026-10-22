---
title: Основы HCL
module: terraform
duration_min: 20
difficulty: beginner
tags: [terraform, hcl, providers, resources, variables, outputs, plan, apply]
exercises: 4
---

## Обзор
Terraform — один из основных инструментов Infrastructure as Code (IaC). Вы описываете желаемую инфраструктуру на HCL (HashiCorp Configuration Language), а Terraform определяет, как привести реальные ресурсы к этому состоянию. Для большинства крупных облачных провайдеров, DNS-регистраторов, баз данных и платформ мониторинга существуют Terraform-провайдеры. В уроке разбираются синтаксис HCL, основной рабочий процесс и строительные блоки конфигурации Terraform.

## Основные понятия

### Основной рабочий процесс
```bash
terraform init     # загрузить провайдеры и модули
terraform plan     # показать, что будет создано, изменено или удалено
terraform apply    # применить план (потребуется подтверждение)
terraform destroy  # удалить все управляемые ресурсы (потребуется подтверждение)
```

Всегда проверяйте вывод `plan` перед запуском `apply`. Terraform показывает добавления (+), изменения (~) и удаления (-).

### Провайдеры
Провайдеры — это плагины, которые взаимодействуют с определённым API (AWS, GCP, Azure, Kubernetes, GitHub и другими):

```hcl
terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"   # любая версия 5.x
    }
  }
}

provider "aws" {
  region = "us-east-1"
  # Учётные данные: переменные AWS_ACCESS_KEY_ID и AWS_SECRET_ACCESS_KEY либо файл ~/.aws/credentials
}
```

### Ресурсы
Ресурсы — это объекты инфраструктуры, которыми управляет Terraform:

```hcl
# Формат объявления ресурса: `resource "<provider>_<type>" "<local_name>" { ... }`

resource "aws_s3_bucket" "app_assets" {
  bucket = "mycompany-app-assets-prod"

  tags = {
    Environment = "production"
    Team        = "platform"
  }
}

resource "aws_s3_bucket_versioning" "app_assets_versioning" {
  bucket = aws_s3_bucket.app_assets.id   # ссылка на другой ресурс

  versioning_configuration {
    status = "Enabled"
  }
}
```

Формат ссылки: `<resource_type>.<local_name>.<attribute>`

### Переменные
```hcl
# variables.tf
variable "region" {
  description = "Регион AWS для развёртывания"
  type        = string
  default     = "us-east-1"
}

variable "instance_count" {
  type    = number
  default = 2
}

variable "db_password" {
  type      = string
  sensitive = true    # скрывается в выводе plan и журналах
}

variable "tags" {
  type = map(string)
  default = {
    Project = "myapp"
  }
}

variable "allowed_cidrs" {
  type    = list(string)
  default = ["10.0.0.0/8"]
}
```

Передать значения переменных можно так:
```bash
terraform apply -var="region=eu-west-1"
terraform apply -var-file="prod.tfvars"
```

```hcl
# Файл prod.tfvars
region         = "eu-west-1"
instance_count = 3
db_password    = "supersecret"
```

Или через переменную окружения: `TF_VAR_region=eu-west-1 terraform apply`

### Выходные значения
```hcl
# outputs.tf
output "bucket_name" {
  description = "Имя бакета S3"
  value       = aws_s3_bucket.app_assets.bucket
}

output "bucket_arn" {
  value = aws_s3_bucket.app_assets.arn
}

output "db_endpoint" {
  value     = aws_db_instance.main.endpoint
  sensitive = true
}
```

```bash
terraform output bucket_name
terraform output -json   # все выходные значения в формате JSON
```

### Локальные значения
```hcl
locals {
  common_tags = merge(var.tags, {
    ManagedBy   = "terraform"
    Environment = var.environment
  })
  
  name_prefix = "${var.project}-${var.environment}"
}

resource "aws_instance" "web" {
  ami  = "ami-0c55b159cbfafe1f0"
  tags = local.common_tags
}
```

### Источники данных
Источники данных считывают сведения об уже существующей инфраструктуре, которой эта конфигурация не управляет:

```hcl
# Найти актуальный образ AMI Amazon Linux
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_instance" "web" {
  ami           = data.aws_ami.amazon_linux.id
  instance_type = "t3.micro"
}

# Найти существующую VPC по тегу
data "aws_vpc" "main" {
  tags = {
    Name = "production-vpc"
  }
}
```

### Выражения и функции
```hcl
# Подстановка значений в строки
name = "myapp-${var.environment}"

# Условное выражение
instance_type = var.environment == "prod" ? "t3.medium" : "t3.micro"

# Выражения с циклом for
security_group_ids = [for sg in var.security_groups : sg.id]

# Функции
cidr_block   = cidrsubnet("10.0.0.0/16", 8, 1)   # 10.0.1.0/24
name         = lower(replace(var.name, " ", "-"))
merged_tags  = merge(var.tags, local.extra_tags)
```

## Примеры

### Экземпляр EC2 с группой безопасности
```hcl
# Файл main.tf

provider "aws" {
  region = var.region
}

resource "aws_security_group" "web" {
  name_prefix = "${var.name_prefix}-web-"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_instance" "web" {
  count         = var.instance_count
  ami           = data.aws_ami.amazon_linux.id
  instance_type = var.instance_type

  vpc_security_group_ids = [aws_security_group.web.id]
  subnet_id              = var.subnet_ids[count.index % length(var.subnet_ids)]

  tags = merge(local.common_tags, {
    Name = "${var.name_prefix}-web-${count.index + 1}"
  })
}

output "instance_ips" {
  value = aws_instance.web[*].private_ip
}
```

## Практические задания

1. Напишите конфигурацию Terraform, которая создаёт бакет S3 с включённым версионированием. Выполните `terraform init`, `terraform plan` и `terraform apply`. Затем изучите состояние командой `terraform show`.
2. Добавьте переменную `environment` (тип `string`, без значения по умолчанию) и используйте её в имени бакета и тегах. Выполните применение с `-var="environment=dev"`, а затем со значением `staging` — сравните планы.
3. Добавьте выходные значения для ARN бакета и его веб-эндпоинта. После применения выполните `terraform output`, чтобы посмотреть значения.
4. Используйте источник данных для получения сведений о существующем ресурсе (например, `data "aws_caller_identity"`, чтобы узнать ID аккаунта AWS). Примените результат в локальной переменной, чтобы сформировать глобально уникальное имя бакета.


---

### Быстрая проверка

5. Посчитайте блоки `resource` в примере HCL. Выполните: `printf 'resource "aws_instance" "web" {}\nresource "aws_s3_bucket" "logs" {}\n' | grep -c '^resource'`

```expected_output
2
```

Подсказка: подумайте, как отфильтровать строки, начинающиеся с заданного ключевого слова, и сразу посчитать совпадения.
Подсказка: используйте `grep` с флагом `-c` и якорем `^`, чтобы учитывать только строки, начинающиеся с `resource`.

6. Извлеките значение `default` переменной из HCL. Выполните: `printf 'variable "instance_type" {\n  default = "t3.micro"\n}\n' | awk '/default =/{gsub(/"/, "", $3); print $3}'`

```expected_output
t3.micro
```

Подсказка: используйте инструмент обработки текста, чтобы найти нужную строку HCL и извлечь из неё определённое поле.
Подсказка: используйте `awk` для поиска строк с `default =`, затем вызовите `gsub()`, чтобы убрать двойные кавычки из третьего поля (`$3`) перед выводом.
