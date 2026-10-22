# Terraform — краткая справка

## Основной рабочий процесс

| Command | Description |
|---------|-------------|
| `terraform init` | Инициализировать провайдеры и модули |
| `terraform fmt` | Форматировать файлы HCL |
| `terraform validate` | Проверить конфигурацию |
| `terraform plan` | Предварительно показать изменения |
| `terraform plan -out=plan.tfplan` | Сохранить план в файл |
| `terraform apply` | Применить изменения с подтверждением |
| `terraform apply -auto-approve` | Применить без запроса подтверждения |
| `terraform apply plan.tfplan` | Применить сохранённый план |
| `terraform destroy` | Удалить все управляемые ресурсы |
| `terraform destroy -auto-approve` | Удалить ресурсы без подтверждения |

## Управление состоянием

| Command | Description |
|---------|-------------|
| `terraform show` | Вывести текущее состояние |
| `terraform state list` | Список всех ресурсов в состоянии |
| `terraform state show res.name` | Показать конкретный ресурс |
| `terraform state mv src dst` | Переименовать ресурс в состоянии |
| `terraform state rm res.name` | Удалить из состояния, не затрагивая инфраструктуру |
| `terraform state pull` | Вывести состояние в формате JSON |
| `terraform import res.name id` | Импортировать существующий ресурс |
| `terraform refresh` | Синхронизировать состояние с реальной инфраструктурой |

## Рабочие пространства

| Command | Description |
|---------|-------------|
| `terraform workspace list` | Список рабочих пространств |
| `terraform workspace new name` | Создать рабочее пространство |
| `terraform workspace select name` | Переключить рабочее пространство |
| `terraform workspace show` | Текущее рабочее пространство |
| `terraform workspace delete name` | Удалить рабочее пространство |

## Выбор ресурсов и просмотр

| Command | Description |
|---------|-------------|
| `terraform plan -target=res.name` | Построить план для конкретного ресурса |
| `terraform apply -target=res.name` | Применить изменения для конкретного ресурса |
| `terraform output` | Показать выходные значения |
| `terraform output name` | Показать конкретное выходное значение |
| `terraform graph \| dot -Tpng > graph.png` | Визуализировать граф зависимостей |
| `terraform providers` | Показать необходимые провайдеры |
| `terraform version` | Показать версию Terraform |

## Шаблоны HCL

| Pattern | Description |
|---------|-------------|
| `variable "name" { default = "val" }` | Входная переменная |
| `var.name` | Ссылка на переменную |
| `output "name" { value = res.attr }` | Выходное значение |
| `locals { key = value }` | Локальное значение |
| `local.key` | Ссылка на локальное значение |
| `data "aws_ami" "latest" { ... }` | Источник данных |
| `module "name" { source = "./modules/x" }` | Вызов модуля |
| `count = var.enabled ? 1 : 0` | Условное создание ресурса |
| `for_each = toset(var.list)` | Создать ресурс для каждого элемента списка |
| `depends_on = [res.other]` | Explicit dependency |
| `lifecycle { prevent_destroy = true }` | Protect from destroy |
