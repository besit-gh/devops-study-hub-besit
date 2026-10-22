---
title: Ansible и Terraform: сравнение и выбор инструмента
module: ansible
duration_min: 15
difficulty: intermediate
tags: [ansible, terraform, iac, configuration-management, comparison, when-to-use]
exercises: 4
---

## Обзор

Ansible и Terraform относятся к Infrastructure as Code, но решают разные задачи. Terraform создаёт и управляет жизненным циклом ресурсов инфраструктуры — VPC, экземпляров EC2, баз данных RDS и DNS-записей — через облачные API и фиксирует созданные объекты в state-файле. Ansible настраивает уже существующие серверы: устанавливает ПО, записывает конфигурации, перезапускает службы и выполняет шаги развёртывания. Простая модель: Terraform строит сцену, а Ansible расставляет декорации и управляет действием.

Главное архитектурное различие — работа с состоянием. Terraform хранит файл `.tfstate`, описывающий последнее известное состояние инфраструктуры. При `terraform apply` он сравнивает конфигурацию с state и реальными ресурсами, затем выполняет только необходимые API-вызовы. У Ansible такого файла нет: при каждом запуске playbook он проверяет текущее состояние систем и выполняет действия, если нужное состояние ещё не достигнуто. Это помогает устранять configuration drift, но Ansible не хранит историю облачных ресурсов, созданных ранее.

В общей цепочке DevOps эти инструменты находятся на соседних, но разных уровнях. Terraform работает на уровне инфраструктуры: его часто запускают в CI-пайплайнах при создании окружений или используют инженеры платформы для управления общей инфраструктурой. Ansible отвечает за настройку и развёртывание: его запускают при выпуске приложений, усилении защиты ОС и выполнении операционных задач. В командах, активно использующих Kubernetes, Helm частично заменяет Ansible при доставке приложений, однако Ansible остаётся важен для всего, что не является контейнером: CI-исполнителей, bastion-хостов, физических серверов и устаревших приложений. Умение выбрать подходящий инструмент и распознать его неправильное применение — один из самых практичных навыков на собеседовании DevOps.

## Основные понятия

### Ключевое различие

| Attribute | Terraform | Ansible |
|---|---|---|
| **Primary purpose** | Provision and manage infrastructure resources | Configure software and systems on existing servers |
| **Execution model** | Declarative: describe desired end state | Declarative in intent, procedural in execution order |
| **State tracking** | `.tfstate` file tracks every managed resource | Stateless — checks live system on every run |
| **Idempotency** | Built into the resource graph | Per-module; mostly built-in, but not guaranteed for `command`/`shell` |
| **Primary targets** | Cloud APIs, DNS providers, databases, Kubernetes objects | Running hosts reachable via SSH or WinRM |
| **Agent required** | No — uses cloud provider APIs | No — uses SSH (or WinRM for Windows) |
| **Language** | HCL (HashiCorp Configuration Language) | YAML + Jinja2 templating |
| **Secrets handling** | Terraform Vault provider, environment variables | Ansible Vault, `no_log: true` |
| **Parallelism** | Native resource graph enables parallel API calls | `forks` setting controls parallel SSH connections |
| **Destroy / rollback** | `terraform destroy` cleanly removes in reverse order | No destroy equivalent for cloud resources |

Самая важная строка таблицы — **отслеживание состояния**. Файл состояния Terraform позволяет определить, что `aws_instance.web` уже существует и его не нужно создавать повторно при следующем запуске. Без state каждая команда `apply` пыталась бы создавать дубликаты ресурсов. Ansible вместо этого проверяет текущую систему. Это отлично подходит для настройки: идемпотентные модули проверяют содержимое файлов, версии пакетов и состояние служб. Но для создания облачной инфраструктуры этого недостаточно: вопрос о существовании VPC требует отдельного API-запроса, а единого стандарта такого поведения у провайдеров нет.

### Terraform's Strengths

Terraform особенно хорош для задач, в которых нужно создать ресурс, зафиксировать факт его существования, учитывать зависимости между ресурсами и при необходимости корректно удалить всё созданное.

```hcl
# terraform/main.tf
# Terraform учитывает, что подсеть зависит от VPC,
# а экземпляр EC2 зависит от обоих ресурсов — Terraform автоматически строит
# граф зависимостей и создаёт ресурсы в правильном порядке.

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
  tags        = { Name = "main" }
}

resource "aws_subnet" "public" {
  vpc_id            = aws_vpc.main.id   # неявная зависимость через ссылку
  cidr_block        = "10.0.1.0/24"
  availability_zone = "us-east-1a"
}

resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.public.id  # ожидать создания подсети
}

resource "aws_route53_record" "web" {
  zone_id = var.zone_id
  name    = "api.example.com"
  type    = "A"
  ttl     = 300
  records = [aws_instance.web.public_ip]  # ожидать создания EC2 и получить его публичный IP-адрес
}

# Выходные значения для последующего использования в Ansible
output "web_public_ip" {
  value = aws_instance.web.public_ip
}

output "web_private_ip" {
  value = aws_instance.web.private_ip
}
```

Наиболее подходящие задачи для Terraform:
- Creating VPCs, subnets, route tables, security groups
- Provisioning cloud databases (RDS, CloudSQL, Aurora)
- Managing DNS records (Route53, Cloudflare)
- Kubernetes cluster creation (EKS, GKE, AKS) and node group management
- IAM roles, policies, and cross-account trust relationships
- Load balancers, target groups, listener rules
- S3 buckets with policies and lifecycle rules
- **Any resource where creation order or circular dependencies matter**

**Главная мысль:** `terraform destroy` корректно удаляет все созданные ресурсы в обратном порядке зависимостей. У Ansible нет полноценного аналога: он не может надёжно отменить выполнение плейбука для облачных ресурсов, поскольку не хранит сведения о том, что именно и в каком порядке было создано. Уже этого различия достаточно, чтобы поручать создание инфраструктуры Terraform.

### Ansible's Strengths

Ansible особенно хорошо подходит для действий *на уже существующем* сервере: установки ПО, записи файлов, запуска служб, последовательного выполнения команд и развёртывания кода.

```yaml
# ansible/deploy.yml
---
- name: Configure web servers
  hosts: webservers
  become: true  # повысить привилегии до root через sudo
  vars:
    app_version: "{{ lookup('env', 'APP_VERSION') | default('main') }}"
    app_repo: "https://github.com/myorg/myapp.git"

  tasks:
    - name: Install system dependencies
      ansible.builtin.apt:
        name:
          - python3
          - python3-pip
          - nginx
        state: present
        update_cache: true

    - name: Deploy application code
      ansible.builtin.git:
        repo: "{{ app_repo }}"
        version: "{{ app_version }}"
        dest: /opt/myapp
        force: true  # перезаписать локальные изменения — это намеренно при развёртывании
      notify: restart app  # запустить обработчик, только если задача внесла изменения

    - name: Write nginx config from template
      ansible.builtin.template:
        src: templates/nginx.conf.j2
        dest: /etc/nginx/sites-available/myapp
        owner: root
        group: root
        mode: "0644"
      notify: reload nginx

    - name: Enable nginx site
      ansible.builtin.file:
        src: /etc/nginx/sites-available/myapp
        dest: /etc/nginx/sites-enabled/myapp
        state: link

    - name: Run database migrations
      ansible.builtin.command:
        cmd: /opt/myapp/bin/migrate --env production
        chdir: /opt/myapp
      run_once: true          # выполнить только на одном узле, даже если целевых узлов несколько
      environment:
        DATABASE_URL: "{{ db_url }}"
      changed_when: true      # migrations always count as a change

  handlers:
    - name: restart app
      ansible.builtin.systemd:
        name: myapp
        state: restarted
        enabled: true

    - name: reload nginx
      ansible.builtin.systemd:
        name: nginx
        state: reloaded
```

Наиболее подходящие задачи для Ansible:
- Installing and pinning OS packages across a fleet
- Writing templated config files (nginx, systemd units, app config)
- Managing services: start, stop, enable, disable, reload
- Deploying application releases in a controlled, ordered sequence
- Running one-time operational tasks: database migrations, cache flushes, log rotation
- Ad-hoc fleet operations: `ansible all -m shell -a "systemctl status nginx"`
- Rolling deployments with `serial: 1` to update one server at a time
- Bootstrapping new hosts before a full config management system is in place

**Обработчики (handlers) — важный шаблон Ansible.** Они запускаются только тогда, когда уведомившая их задача сообщила об изменении. Поэтому `reload nginx` не выполняется при каждом запуске плейбука, а только после фактического изменения шаблона конфигурации. Обработчики также устраняют дублирование: если пять задач уведомили один обработчик, он выполнится один раз в конце play. Благодаря этому плейбуки эффективны и безопасны при повторном запуске.

### The Overlap Zone

Both tools can technically do what the other does. Neither does it well when used outside its core role.

| Task | Terraform | Ansible |
|---|---|---|
| Create EC2 instance | ✅ Right tool | ⚠️ Possible via `amazon.aws` — no state, can't cleanly destroy |
| Install nginx on EC2 | ⚠️ Possible via `user_data` — runs once at boot, not re-runnable | ✅ Right tool |
| Create S3 bucket | ✅ Right tool | ⚠️ Possible — no drift detection without state |
| Write `/etc/nginx/nginx.conf` | ❌ Awkward (`null_resource` + file provisioner) | ✅ Right tool |
| Deploy application code | ❌ Wrong tool (`null_resource` + `remote-exec`) | ✅ Right tool |
| Manage DNS record | ✅ Right tool | ⚠️ Possible — no cleanup on record removal |
| Create IAM policy | ✅ Right tool | ⚠️ Possible — no drift detection |
| Rolling restart of services | ❌ Not designed for this | ✅ Right tool (`serial`) |
| Manage Kubernetes manifests | ✅ Via `kubernetes` provider | ✅ Via `kubernetes.core` collection |

**Provisioner Terraform (`remote-exec`, `local-exec`) — ловушка.** Они запускают скрипты после создания ресурса, но при последующих вызовах `terraform apply` повторно не выполняются — только при создании ресурса. Если скрипт завершится ошибкой посередине, Terraform пометит ресурс как требующий пересоздания и при следующем применении может создать его заново, что грозит потерей данных или простоем. В документации Terraform provisioner прямо названы крайним средством. Задачи настройки, которые должны регулярно приводить систему к нужному состоянию, следует выполнять в Ansible, а не через provisioner.

**Ansible не хранит состояние облачных ресурсов**, что создаёт реальные операционные проблемы при масштабировании. Если задача Ansible создаёт экземпляр EC2, повторный запуск плейбука может создать второй экземпляр — это зависит от реализации идемпотентности модуля. Если удалить ресурс вручную, Ansible об этом не узнает. Нельзя запустить `ansible-playbook destroy.yml` и ожидать, что он надёжно удалит облачные ресурсы так же, как `terraform destroy`.

### The Standard Integration Pattern

Типовой подход для production-среды: Terraform создаёт инфраструктуру и выводит нужные значения, а Ansible использует их для настройки созданных ресурсов.

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│         TERRAFORM           │     │           ANSIBLE           │
│                             │     │                             │
│  • VPC, subnets, SGs        │     │  • Install app dependencies │
│  • EC2 instances            │────▶│  • Write config files       │
│  • RDS database             │     │  • Deploy application code  │
│  • EKS cluster              │     │  • Run DB migrations        │
│  • S3 buckets               │     │  • Configure systemd units  │
│  • Route53 records          │     │  • Set up cron jobs         │
│  • IAM roles                │     │  • Harden OS config         │
│         ↓                   │     │         ↑                   │
│  outputs: IPs, URLs,        │────▶│  vars: db_host, redis_url,  │
│           ARNs, endpoints   │     │         instance IPs         │
└─────────────────────────────┘     └─────────────────────────────┘
```

Точка передачи данных между инструментами — выходные значения Terraform. После `terraform apply` извлеките их и передайте Ansible как переменные inventory или дополнительные переменные:

```bash
# pipeline.sh — the glue between Terraform and Ansible
#!/usr/bin/env bash
set -euo pipefail

cd infra/
terraform init -input=false
terraform apply -auto-approve

# Extract Terraform outputs as plain strings
DB_HOST=$(terraform output -raw db_host)
REDIS_URL=$(terraform output -raw redis_url)
# -json gives a JSON array; jq converts it to newline-separated IPs
WEB_IPS=$(terraform output -json web_private_ips | jq -r '.[]')

# Build an Ansible inventory dynamically from Terraform outputs.
# A production pipeline would use a dynamic inventory plugin instead,
# but this approach is transparent and easy to debug.
INVENTORY_FILE=$(mktemp /tmp/inventory.XXXXXX.ini)
trap "rm -f $INVENTORY_FILE" EXIT  # всегда удалять временный файл

cat > "$INVENTORY_FILE" << EOF
[webservers]
$(echo "$WEB_IPS")

[webservers:vars]
db_host=${DB_HOST}
redis_url=${REDIS_URL}
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/deploy_key
ansible_ssh_common_args='-o StrictHostKeyChecking=no'
EOF

cd ../ansible/
ansible-playbook \
  -i "$INVENTORY_FILE" \
  --extra-vars "app_version=${APP_VERSION:-main}" \
  deploy.yml
```

Для более сложных конфигураций коллекция Ansible `cloud.terraform` предоставляет плагин динамического inventory, который читает данные непосредственно из состояния Terraform без ручного извлечения значений:

```yaml
# ansible/inventory/terraform.yml
plugin: cloud.terraform.terraform_provider
project_path: ../infra/
# Reads infra/terraform.tfstate and exposes resources as inventory hosts.
# Instances tagged with ansible_group=webservers appear in the [webservers] group.
# Requires: ansible-galaxy collection install cloud.terraform
```

**Почему бы не использовать Terraform для всего?** Некоторые команды применяют provisioner `remote-exec` или `local-exec`, чтобы обойтись одним инструментом. Обычно это создаёт проблемы: теряются идемпотентность Ansible, повторные попытки, шаблоны и возможность повторно настраивать систему независимо от жизненного цикла инфраструктуры. Поддерживать два инструмента обычно дешевле, чем в два часа ночи отлаживать неправильно настроенные provisioner.

### Idempotency: Where Each Tool Stands

Идемпотентность означает, что многократное выполнение одной операции приводит к одному и тому же результату. Оба инструмента стремятся к этому, но используют разные механизмы; у каждого есть характерные ошибки, о которых важно знать.

**Идемпотентность Terraform** обеспечивается самим движком. Файл состояния вместе с чтением актуального состояния через API (этап refresh) показывает Terraform, какие ресурсы существуют. Если ресурс соответствует конфигурации, API-вызов не выполняется. Это поведение предусмотрено по умолчанию — не нужно писать дополнительную защитную логику в HCL.

**Идемпотентность Ansible** зависит от конкретного модуля. Хорошо написанные модули проверяют состояние перед выполнением действий:
- `ansible.builtin.apt` checks if the package is already at the right version
- `ansible.builtin.template` checksums the rendered file against what's on disk
- `ansible.builtin.service` reads current service state before issuing start/stop

The idempotency traps in Ansible all involve `command` and `shell`:

```yaml
# ❌ NOT idempotent — appends every time the playbook runs
- name: Add line to config
  ansible.builtin.command:
    cmd: echo "option=value" >> /etc/myapp/config.ini

# ✅ Idempotent — checks if line exists before adding
- name: Ensure option is set in config
  ansible.builtin.lineinfile:
    path: /etc/myapp/config.ini
    line: "option=value"
    state: present

# ❌ NOT idempotent without changed_when — always reports "changed"
# and always triggers any downstream handlers unnecessarily
- name: Run migration
  ansible.builtin.command:
    cmd: /opt/myapp/bin/migrate

# ✅ Use changed_when to control when Ansible considers this a change
- name: Run migration (only if needed)
  ansible.builtin.command:
    cmd: /opt/myapp/bin/migrate --check-first
  register: migrate_result
  changed_when: "'Applied' in migrate_result.stdout"

# ✅ Use creates: to skip a command if its output artifact already exists
- name: Compile assets (skip if already done)
  ansible.builtin.command:
    cmd: /opt/myapp/bin/compile-assets
    creates: /opt/myapp/public/assets/manifest.json
```

**Шаблон `changed_when: false`** полезен для команд только на чтение — например, проверок работоспособности или запросов статуса, которые не должны отмечаться как изменения:

```yaml
- name: Check cluster node count
  ansible.builtin.command:
    cmd: kubectl get nodes --no-headers | wc -l
  register: node_count
  changed_when: false   # это операция чтения, а не изменение
```

**Summary of idempotency approach by tool:**

| Scenario | Terraform behavior | Ansible behavior |
|---|---|---|
| Resource already matches config | No-op, no API call | Depends on module — most skip, `command` acts |
| Resource drifted from config | Detects and corrects | Detects and corrects (for supported modules) |
| Resource deleted externally | Detects on refresh, recreates | Doesn't know — module may create duplicate |
| Script/command tasks | Not applicable | Not idempotent without `creates:` or `changed_when:` |

### When to Reach for Each Tool: Decision Heuristic

A practical mental flowchart for choosing the right tool:

```
Is the task creating or destroying a cloud resource (instance, DB, network, DNS)?
  └─ YES → Terraform

Is the task configuring, installing, or deploying onto an existing server?
  └─ YES → Ansible

Is the task a rolling update across a fleet of running servers?
  └─ YES → Ansible (serial, max_fail_percentage)

Does the task need to be repeated or re-run independently of infrastructure lifecycle?
  └─ YES → Ansible

Does the task need to be cleanly reversible with an automated destroy?
  └─ YES → Terraform

Вы управляете манифестами Kubernetes в уже существующем кластере?

**The "paved road" antipatterns to watch for in interviews and job descriptions:**
- "We use Terraform to install Docker on our servers" → should be Ansible
- "We use Ansible to manage our AWS VPCs" → should be Terraform
- "We use Terraform `remote-exec` to deploy our app" → should be split: Terraform provisions, Ansible deploys
- "We use Ansible to spin up and tear down test environments" → acceptable for simple cases, but Terraform handles the resource lifecycle better at any meaningful scale

## Примеры

### Example 1: Provision an EC2 Instance with Terraform, Then Configure It with Ansible

This is the end-to-end workflow that most production pipelines follow.

**Step 1: Terraform provisions the server**

```hcl
# infra/main.tf
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = "us-east-1"
}

resource "aws_security_group" "web" {
  name        = "web-sg"
  description = "Allow HTTP and SSH"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # restrict to your IP in production
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "web" {
  ami                    = "ami-0c55b159cbfafe1f0"  # Amazon Linux 2 us-east-1
  instance_type          = "t3.micro"
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.web.id]

  tags = {
    Name          = "web-server"
    ansible_group = "webservers"  # consumed by cloud.terraform dynamic inventory
  }
}

output "web_public_ip" {
  value = aws_instance.web.public_ip
}

output "web_public_dns" {
  value = aws_instance.web.public_dns
}
```

```bash
# Provision the infrastructure
cd infra/
terraform init
terraform plan   # review what will be created
terraform apply  # creates SG + EC2 instance

# Capture the IP for use in the next step
export WEB_IP=$(terraform output -raw web_public_ip)
echo "Server ready at: $WEB_IP"
```

**Step 2: Ansible configures nginx on the new server**

```yaml
# ansible/nginx.yml
---
- name: Configure nginx web server
  hosts: all
  become: true

  tasks:
    - name: Wait for SSH to be available
      ansible.builtin.wait_for_connection:
        timeout: 120  # новым экземплярам нужно время на загрузку и запуск sshd

    - name: Install nginx
      ansible.builtin.yum:
        name: nginx
        state: present

    - name: Write index page
      ansible.builtin.copy:
        content: "<h1>Deployed by Ansible on {{ inventory_hostname }}</h1>\n"
        dest: /usr/share/nginx/html/index.html
        mode: "0644"

    - name: Start and enable nginx
      ansible.builtin.systemd:
        name: nginx
        state: started
        enabled: true
```

```bash
# Run Ansible against the IP Terraform gave us
ansible-playbook \
  -i "${WEB_IP}," \           # завершающая запятая означает, что inventory задаётся прямо в командной строке
  -u ec2-user \
  --private-key ~/.ssh/my-key.pem \
  ansible/nginx.yml

# Verify it worked
curl "http://${WEB_IP}"
# Expected: <h1>Deployed by Ansible on <IP></h1>
```

---

### Example 2: Rolling Application Deployment with Ansible

This shows how Ansible handles a fleet update that Terraform cannot — updating servers one at a time to avoid downtime.

```yaml
# ansible/rolling-deploy.yml
---
- name: Rolling deploy of myapp
  hosts: webservers
  serial: 1              # обновлять строго один сервер за раз
  max_fail_percentage: 0 # прервать весь play, если произойдёт сбой хотя бы на одном узле
  become: true

  vars:
    deploy_version: "{{ app_version | mandatory }}"  # fail loudly if not passed

  pre_tasks:
    - name: Remove host from load balancer
      ansible.builtin.uri:
        url: "https://lb.internal/api/members/{{ inventory_hostname }}"
        method: DELETE
        headers:
          Authorization: "Bearer {{ lb_token }}"
      delegate_to: localhost  # выполнить запрос к API балансировщика с управляющего узла

    - name: Wait for in-flight requests to drain
      ansible.builtin.pause:
        seconds: 10

  tasks:
    - name: Deploy new application version
      ansible.builtin.git:
        repo: https://github.com/myorg/myapp.git
        version: "{{ deploy_version }}"
        dest: /opt/myapp
        force: true
      notify: restart myapp

    - name: Install updated Python dependencies
      ansible.builtin.pip:
        requirements: /opt/myapp/requirements.txt
        virtualenv: /opt/myapp/.venv

  handlers:
    - name: restart myapp
      ansible.builtin.systemd:
        name: myapp
        state: restarted

  post_tasks:
    - name: Wait for application health check to pass
      ansible.builtin.uri:
        url: "http://{{ inventory_hostname }}:8080/health"
        status_code: 200
      retries: 10
      delay: 5
      until: result.status == 200
      register: result

    - name: Re-add host to load balancer
      ansible.builtin.uri:
        url: "https://lb.internal/api/members"
        method: POST
        body_format: json
        body:
          host: "{{ inventory_hostname }}"
          weight: 100
        headers:
          Authorization: "Bearer {{ lb_token }}"
      delegate_to: localhost
```

```bash
# Trigger a rolling deploy to all webservers
ansible-playbook \
  -i inventory/production.ini \
  --extra-vars "app_version=v2.4.1" \
  ansible/rolling-deploy.yml

# Watch it progress: each host is drained, updated, health-checked, re-added
# If any host's health check fails, the play stops before touching remaining hosts
```

---

### Example 3: Terraform Manages Database; Ansible Configures Application to Use It

This demonstrates the practical handoff of credentials and endpoints.

```hcl
# infra/rds.tf
resource "aws_db_instance" "app" {
  identifier        = "myapp-production"
  engine            = "postgres"
  engine_version    = "15.3"
  instance_class    = "db.t3.medium"
  allocated_storage = 20
  db_name           = "myapp"
  username          = "myapp"
  password          = var.db_password  # passed in via TF_VAR_db_password env var

  # skip_final_snapshot = false in production; set to true only for throwaway envs
  skip_final_snapshot = true
}

output "db_host" {
  value = aws_db_instance.app.address
}

output "db_port" {
  value = aws_db_instance.app.port
}
```

```bash
# Apply and capture outputs
terraform apply -auto-approve
export DB_HOST=$(terraform output -raw db_host)
export DB_PORT=$(terraform output -raw db_port)
```

```yaml
# ansible/templates/database.yml.j2
# This template is rendered by Ansible using vars passed from Terraform outputs
production:
  adapter: postgresql
  host: {{ db_host }}
  port: {{ db_port }}
  database: myapp
  username: myapp
  password: {{ db_password }}
  pool: 5
```

```yaml
# ansible/configure-app.yml
---
- name: Configure application database connection
  hosts: webservers
  become: true

  tasks:
    - name: Write database config from Terraform outputs
      ansible.builtin.template:
        src: templates/database.yml.j2
        dest: /opt/myapp/config/database.yml
        owner: myapp
        group: myapp
        mode: "0600"   # файл с учётными данными — ограничить права доступа
      no_log: true      # не допустить появления db_password в выводе Ansible
      notify: restart myapp

  handlers:
    - name: restart myapp
      ansible.builtin.systemd:
        name: myapp
        state: restarted
```

```bash
ansible-playbook \
  -i inventory/production.ini \
  --extra-vars "db_host=${DB_HOST} db_port=${DB_PORT} db_password=${DB_PASSWORD}" \
  ansible/configure-app.yml

# Verify the app can reach the database
ansible webservers -i inventory/production.ini \
  -m command -a "/opt/myapp/bin/check-db-connection"
```

---

### Example 4: Using Terraform `user_data` vs Ansible for Bootstrap — Seeing the Difference

Этот пример показывает, почему `user_data` не подходит для полноценного управления конфигурацией и когда после него следует использовать Ansible.

```hcl
# infra/userdata.tf
# user_data runs ONCE at first boot — not re-runnable, not idempotent
resource "aws_instance" "app" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"

  # Only appropriate for minimal bootstrapping — install SSM agent,
  # set hostname, configure cloud-init. NOT for app deployment.
  user_data = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y python3
    # Stop here — hand off to Ansible for anything more complex
  EOF
}
```

```bash
# After Terraform creates the instance, Ansible handles everything else.
# If the nginx config changes next week, you re-run Ansible — not terraform apply.

WEB_IP=$(terraform output -raw web_public_ip)

# First run: installs everything
ansible-playbook -i "${WEB_IP}," -u ec2-user \
  --private-key ~/.ssh/key.pem playbook.yml

# второй запуск: ничего не менять, если состояние не изменилось, либо исправить отклонение
ansible-playbook -i "${WEB_IP}," -u ec2-user \
  --private-key ~/.ssh/key.pem playbook.yml
# Результат: changed=0 — так и должно быть в стабильной системе

# Если кто-то вручную изменит nginx.conf на сервере (отклонение конфигурации):
ansible-playbook -i "${WEB_IP}," -u ec2-user \
  --private-key ~/.ssh/key.pem playbook.yml
# Результат: changed=1 — Ansible автоматически исправляет конфигурацию
```

## Практические задания

### Exercise 1: Identify Misused Tools in a Pipeline Script

Прочитайте фрагмент CI-пайплайна и найдите каждый случай, когда используется неподходящий инструмент. Для каждого случая объясните проблему и предложите исправление.

```bash
#!/bin/bash
# deploy.sh — DO NOT USE AS-IS; contains intentional errors

# Step 1: Create VPC and subnets
ansible-playbook -i localhost, create-vpc.yml \
  -e "cidr=10.0.0.0/16 region=us-east-1"

# Step 2: Provision EC2 instance
ansible-playbook -i localhost, create-ec2.yml \
  -e "instance_type=t3.micro ami=ami-0c55b159cbfafe1f0"

# Step 3: Install nginx (runs once at launch)
cat > user_data.sh << 'EOF'
#!/bin/bash
apt-get install -y nginx
echo "server { listen 80; root /var/www/html; }" > /etc/nginx/sites-enabled/default
systemctl start nginx
EOF
# (user_data passed to EC2 above)

# Step 4: Deploy application
terraform apply -auto-approve \
  -var "app_version=${APP_VERSION}" \
  # Terraform null_resource runs remote-exec to git clone the app
```

В ответе укажите, какие шаги должны выполняться Terraform, какие — Ansible, и почему настройка nginx через `user_data` усложняет сопровождение. Код сдавать не нужно — оформите анализ списком.

---

### Exercise 2: Write an Idempotent Ansible Task Block

В следующем блоке задач есть три ошибки, нарушающие идемпотентность. Исправьте их, не меняя назначения задач.

```yaml
tasks:
  - name: Create app directory
    ansible.builtin.command:
      cmd: mkdir -p /opt/myapp

  - name: Add database URL to environment file
    ansible.builtin.command:
      cmd: echo "DATABASE_URL=postgres://localhost/myapp" >> /etc/environment

  - name: Generate self-signed TLS cert
    ansible.builtin.command:
      cmd: >
        openssl req -x509 -nodes -days 365 -newkey rsa:2048
        -keyout /etc/ssl/myapp.key
        -out /etc/ssl/myapp.crt
        -subj "/CN=myapp.internal"
```

Подсказка: где уместно, используйте `ansible.builtin.file`, `ansible.builtin.lineinfile` и параметр `creates:`. После исправления второй запуск плейбука должен завершиться с `changed=0`.

---

### Exercise 3: Build the Terraform-to-Ansible Handoff

Настройте минимальную рабочую интеграцию Terraform и Ansible с помощью LocalStack (локального эмулятора AWS) или настоящего аккаунта AWS.

1. Write a `main.tf` that creates one EC2 instance (or LocalStack equivalent) and outputs its IP address and a fake `db_host` value using a `local_file` resource if you don't have AWS credentials.
2. Write a `pipeline.sh` that:
   - Runs `terraform apply`
   - Extracts the IP and db_host outputs
   - Builds a temporary Ansible inventory file with those values as `[webservers:vars]`
   - Runs `ansible-playbook -i` against that inventory
   - Cleans up the temp file on exit (use `trap`)
3. Write an `install.yml` playbook that installs nginx and writes a file to `/tmp/db_host.txt` containing the value of `{{ db_host }}`.
4. Verify: after running `pipeline.sh`, SSH to the server and confirm `/tmp/db_host.txt` contains the expected value.

**На что обратить внимание:** запустите `pipeline.sh` дважды. При втором запуске Terraform не должен показывать изменений. Ansible должен выводить `changed=0` или `changed=1` только для задач, в которых состояние действительно отличалось от требуемого.

---

### Exercise 4: Terraform Destroy vs Ansible Cleanup — Observe the Difference

This exercise builds intuition for the state gap between the two tools.

1. Use Terraform to provision two EC2 instances tagged `env=test`.
2. Write an Ansible playbook that installs a package and creates a file on both instances.
3. Manually terminate one instance through the AWS console (simulating unexpected deletion).
4. Run `terraform plan` — observe how Terraform detects the missing resource and proposes to recreate it.
5. Run the same Ansible playbook — observe what happens when Ansible tries to reach the terminated instance (it fails; Ansible has no awareness that the instance is gone).
6. Run `terraform destroy` — observe that it cleanly removes both instances (recreating the missing one first if you didn't run apply, or just destroying the remaining one).

В одном абзаце объясните, как каждый инструмент реагирует на внешние изменения состояния и что это означает для выбора инструмента, который должен управлять жизненным циклом облачных ресурсов.

---

### Быстрая проверка

7. Identify which tool uses declarative state management. Run: `printf 'ansible:stateless\nterraform:declarative-state\n' | awk -F: '/declarative-state/{print $1}'`

```expected_output
terraform
```

hint: Think about how awk can filter lines based on a pattern match and then extract a specific field from those lines.
hint: Use awk with -F: to set the colon as a field separator, then match lines containing your target pattern inside /.../ and print the first field with {print $1}.

8. Count YAML playbook files in a directory listing. Run: `printf 'main.yml\ninventory.ini\nplaybook.yml\nrequirements.yml\n' | grep -c '\.yml$'`

```expected_output
3
```

hint: Think about how grep can be used to filter lines by a file extension pattern and also count matches directly.
hint: Use grep with the -c flag and the regex pattern \.yml$ to count only lines ending in .yml.
