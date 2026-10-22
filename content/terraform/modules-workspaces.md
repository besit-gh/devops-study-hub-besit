---
title: Модули и рабочие пространства Terraform
module: terraform
duration_min: 20
difficulty: intermediate
tags: [terraform, modules, workspaces, reusability, for-each, count]
exercises: 4
---

## Обзор
Модули упаковывают повторно используемые конфигурации Terraform. Вместо копирования одного и того же описания VPC или кластера EKS между командами вы создаёте модуль один раз и вызываете его с разными входными параметрами. Workspaces позволяют одной конфигурации управлять несколькими файлами состояния для разных окружений. Вместе они составляют основу масштабируемой архитектуры Terraform.

## Основные понятия

### Модули
Модуль — это каталог с файлами `.tf`. До сих пор вы работали с корневым модулем; дочерние модули подключаются из него:

```hcl
# Подключить локальный модуль
module "vpc" {
  source = "./modules/vpc"      # локальный путь

  cidr_block         = "10.0.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b"]
  environment        = var.environment
}

# Подключить модуль из Terraform Registry
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "my-cluster"
  cluster_version = "1.29"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets
}

# Подключить модуль из Git-репозитория
module "db" {
  source = "git::https://github.com/myorg/terraform-modules.git//rds?ref=v1.2.0"

  instance_class = "db.t3.medium"
  db_name        = "myapp"
}
```

После добавления модуля или изменения его источника повторно выполните `terraform init`.

### Структура модуля
```
modules/
  vpc/
    main.tf        # ресурсы
    variables.tf   # входные переменные (интерфейс модуля)
    outputs.tf     # выходные значения, на которые могут ссылаться вызывающие конфигурации
    versions.tf    # required_providers и required_version
```

```hcl
# modules/vpc/variables.tf
variable "cidr_block" {
  type        = string
  description = "CIDR-блок VPC"
}

variable "environment" {
  type        = string
  description = "Окружение развёртывания (dev, staging, prod)"
}

variable "tags" {
  type    = map(string)
  default = {}
}
```

```hcl
# modules/vpc/outputs.tf
output "vpc_id" {
  value = aws_vpc.main.id
}

output "private_subnets" {
  value = aws_subnet.private[*].id
}

output "public_subnets" {
  value = aws_subnet.public[*].id
}
```

Ссылки на выходные значения модуля: `module.vpc.vpc_id`, `module.vpc.private_subnets`

### for_each and count — Multiple Resource Instances
```hcl
# count — повторение заданное числом
resource "aws_instance" "web" {
  count         = var.instance_count
  ami           = data.aws_ami.linux.id
  instance_type = "t3.micro"

  tags = {
    Name = "web-${count.index}"
  }
}

# Примеры ссылок: aws_instance.web[0].id, aws_instance.web[*].id

# for_each — перебор map или set (предпочтительнее count для именованных ресурсов)
resource "aws_s3_bucket" "assets" {
  for_each = toset(["images", "videos", "documents"])

  bucket = "mycompany-${each.key}"
  tags = {
    AssetType = each.key
  }
}

# Пример ссылки: aws_s3_bucket.assets["images"].id

# for_each с map
variable "subnets" {
  default = {
    "us-east-1a" = "10.0.1.0/24"
    "us-east-1b" = "10.0.2.0/24"
  }
}

resource "aws_subnet" "private" {
  for_each = var.subnets

  vpc_id            = aws_vpc.main.id
  availability_zone = each.key
  cidr_block        = each.value
}
```

Для именованных ресурсов предпочитайте `for_each` вместо `count`: удаление элемента из списка `count` сдвигает индексы, из-за чего Terraform может удалить и пересоздать все ресурсы после образовавшегося разрыва.

### Рабочие пространства
Workspaces позволяют использовать одну конфигурацию с отдельным файлом состояния для каждого рабочего пространства:

```bash
# Показать рабочие пространства
terraform workspace list
# * default
#   staging
#   production

# Создать рабочее пространство и переключиться на него
terraform workspace new staging
terraform workspace select production
terraform workspace show    # current workspace name
```

Use `terraform.workspace` in your config:
```hcl
locals {
  env_config = {
    default    = { instance_type = "t3.micro",  count = 1 }
    staging    = { instance_type = "t3.small",  count = 2 }
    production = { instance_type = "t3.medium", count = 4 }
  }
  config = local.env_config[terraform.workspace]
}

resource "aws_instance" "app" {
  count         = local.config.count
  instance_type = local.config.instance_type
}
```

**Ограничения рабочих пространств:**
- Файлы состояния используют один backend — нельзя выбрать отдельный аккаунт AWS для каждого workspace
- Легко забыть, какой workspace активен, и случайно изменить production
- Для полноценной изоляции окружений (разные аккаунты и права) используйте отдельные корневые конфигурации с разными backend

### Terraform Registry and Module Versioning
```hcl
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"   # ~> 20.0 = >= 20.0, < 21.0
}

# Ограничения версий:
# = 20.5.0   — exact
# ~> 20.5    — >= 20.5, < 20.6 (patch only)
# ~> 20.0    — >= 20.0, < 21.0 (minor+patch)
# >= 20.0, < 21.0   — explicit range
```

В production всегда фиксируйте версии модулей: использование `source = "...//module"` без `version` может привести к неожиданным изменениям.

## Примеры

### Несколько окружений с помощью модулей
```hcl
# environments/prod/main.tf
module "network" {
  source      = "../../modules/network"
  environment = "prod"
  cidr_block  = "10.0.0.0/16"
  az_count    = 3
}

module "app" {
  source         = "../../modules/app"
  environment    = "prod"
  vpc_id         = module.network.vpc_id
  subnet_ids     = module.network.private_subnets
  instance_count = 4
  instance_type  = "t3.medium"
}
```

```
infrastructure/
  modules/
    network/    # повторно используемая VPC, подсети, IGW и NAT
    app/        # повторно используемое развёртывание приложения в ECS/EC2
    rds/        # повторно используемый кластер RDS
  environments/
    dev/main.tf
    staging/main.tf
    prod/main.tf
```

### Подключение публичного модуля
```hcl
# Используйте готовый модуль EKS вместо написания 500 строк конфигурации
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "mycompany-prod"
  cluster_version = "1.29"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    general = {
      instance_types = ["t3.medium"]
      min_size       = 2
      max_size       = 10
      desired_size   = 3
    }
  }
}
```

## Практические задания

1. Вынесите повторяющийся блок ресурсов (например, несколько бакетов S3 или экземпляров EC2) в модуль. Вызывайте его из корневого модуля с разными входными параметрами. Убедитесь, что `terraform plan` показывает тот же результат, что и до изменений.
2. Используйте `for_each`, чтобы создать три бакета S3 из набора имён `toset`. Затем удалите одно имя и сравните план с поведением варианта на `count`.
3. Создайте два workspace (`dev` и `prod`). Используйте `terraform.workspace`, чтобы задавать разные типы экземпляров в каждом. Примените конфигурацию в обоих workspace и проверьте созданные экземпляры командой `terraform state list`.
4. Используйте модуль `terraform-aws-modules/s3-bucket/aws` из Terraform Registry, чтобы создать бакет S3 с версионированием и шифрованием. Сравните объём HCL с вариантом, где ресурсы описаны напрямую.


---

### Быстрая проверка

5. Посчитайте блоки `module` в примере конфигурации HCL. Выполните: `printf 'module "vpc" {\n  source = "./modules/vpc"\n}\nmodule "eks" {\n  source = "./modules/eks"\n}\n' | grep -c '^module'`

```expected_output
2
```

Подсказка: отфильтруйте строки, начинающиеся с заданного ключевого слова, и посчитайте их одной командой.
Подсказка: используйте `grep -c` с шаблоном `^module`, чтобы считать только строки, которые начинаются со слова `module`.

6. Извлеките тип ресурса из адреса ресурса Terraform. Выполните: `echo "aws_instance.web_server" | cut -d. -f1`

```expected_output
aws_instance
```

Подсказка: разделите строку по разделителю и выберите первый фрагмент.
Подсказка: используйте `cut` с флагом `-d`, указав `.` как разделитель, и `-f1`, чтобы получить первое поле.
