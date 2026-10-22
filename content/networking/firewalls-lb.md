---
title: Межсетевые экраны и балансировщики нагрузки
module: networking
duration_min: 20
difficulty: intermediate
tags: [networking, firewall, iptables, ufw, security-groups, load-balancer, nginx]
exercises: 4
---

## Обзор

Межсетевые экраны и балансировщики нагрузки — привратники любой production-системы. Firewall применяет политику доступа: определяет, какие пакеты могут дойти до сервиса, а какие будут отброшены. Балансировщик распределяет разрешённый трафик между несколькими backend-экземплярами, обеспечивая горизонтальное масштабирование и отказоустойчивость. На практике эти компоненты почти всегда работают вместе: firewall контролирует доступ к балансировщику, а балансировщик выбирает backend для обработки запроса.

DevOps-инженеру необходимо разбираться в обоих компонентах. Неверная настройка firewall — одна из самых частых причин ситуации «у меня на машине работает», когда соединение не работает в staging или production. Ошибки балансировщика приводят к незаметной потере данных, неравномерному распределению трафика и health checks, направляющим запросы на неработающие экземпляры. Нужно уметь читать и создавать наборы правил, а также диагностировать сбои на bare metal, в виртуальных машинах и облачной инфраструктуре.

Обе технологии могут одновременно работать на разных уровнях стека. На одном Linux-хосте могут действовать правила `iptables` в ядре, облачная security group на уровне гипервизора (до поступления пакетов в ОС) и расположенный впереди балансировщик прикладного уровня. Эти уровни взаимодействуют. Понимание их границ и возможных противоречий отличает инженера, способного диагностировать production-инциденты, от того, кто лишь гадает и перезапускает службы.

---

## Основные понятия

### Как обрабатываются правила firewall

Firewall — это упорядоченный список правил. У каждого правила есть **условие совпадения** (к каким пакетам оно применяется) и **действие** (что делать с совпавшим пакетом: ACCEPT, DROP, REJECT, LOG и т. д.). Правила проверяются сверху вниз; первое совпавшее правило завершает обработку пакета.

Порядок правил имеет важные последствия:

- Широкое правило ACCEPT перед конкретным DROP сделает DROP недостижимым.
- Широкое правило DROP в начале цепочки заблокирует весь трафик, включая текущее SSH-соединение.
- Никогда не срабатывающие правила добавляют задержку (небольшую, но измеримую при высокой скорости пакетов).

| Действие | Поведение | Видно отправителю? |
|--------|----------|--------------------|
| `ACCEPT` | Пропустить пакет | Да — соединение продолжается |
| `DROP` | Молча отбросить | Нет — отправитель ждёт тайм-аута |
| `REJECT` | Отбросить и отправить ошибку ICMP | Да — отправитель сразу получает ошибку |
| `LOG` | Записать в журнал и продолжить проверку | Неприменимо — обработка продолжается |

**DROP и REJECT:** используйте `DROP` для правил, обращённых к внешней сети: отсутствие ответа замедляет сканирование портов и даёт атакующему меньше информации. Внутри системы (между сервисами) используйте `REJECT`, чтобы легитимные клиенты быстро получали ошибку, а не ждали тайм-аут.

**Состояние соединения имеет значение:** современные firewall отслеживают состояние соединений. Для пакета существующего TCP-соединения (`ESTABLISHED`) или связанного с ним (`RELATED`, например ответа об ошибке ICMP) не требуется отдельное правило ACCEPT. Всегда добавляйте правило для установленных и связанных соединений в начало цепочки INPUT. Иначе при политике DROP по умолчанию можно случайно заблокировать себе доступ.

---

### iptables (межсетевой экран ядра Linux)

`iptables` — традиционный пользовательский интерфейс к подсистеме фильтрации пакетов `netfilter` ядра Linux. В Ubuntu 20.04+ и RHEL 9+ фактическим backend является `nftables`, а команды `iptables` преобразуются совместимым слоем `iptables-nft`. Синтаксис и поведение при этом остаются прежними.

Правила организованы в **цепочки (chains)** внутри **таблиц (tables)**:

| Таблица | Назначение | Цепочки |
|-------|---------|--------|
| `filter` | Разрешение и блокировка пакетов (по умолчанию) | INPUT, OUTPUT, FORWARD |
| `nat` | Трансляция адресов | PREROUTING, POSTROUTING, OUTPUT |
| `mangle` | Изменение заголовков пакетов | Все пять цепочек |
| `raw` | Отключение отслеживания соединений | PREROUTING, OUTPUT |

Для большинства задач с firewall достаточно таблицы `filter`.

```bash
# Show current rules with line numbers, packet/byte counts, no DNS lookup
iptables -L -v -n --line-numbers

# Show only the INPUT chain
iptables -L INPUT -v -n --line-numbers

# Set default policies for OUTPUT and FORWARD first — safe operations
iptables -P OUTPUT ACCEPT
iptables -P FORWARD DROP

# --- Build INPUT rules in order BEFORE setting default DROP ---

# 1. Allow loopback (required for many local services)
iptables -A INPUT -i lo -j ACCEPT

# 2. Allow established/related connections — critical: do this before DROP policy
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# 3. Allow new SSH connections
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# 4. Allow HTTP and HTTPS
iptables -A INPUT -p tcp -m multiport --dports 80,443 -j ACCEPT

# 5. Allow PostgreSQL only from a specific application server IP
iptables -A INPUT -p tcp --dport 5432 -s 10.0.0.50 -j ACCEPT

# 6. Set default DROP only after all ACCEPT rules are in place
iptables -P INPUT DROP

# --- Rule management ---

# Insert a rule at position 3 (pushes existing rule 3 down)
iptables -I INPUT 3 -p tcp --dport 8080 -j ACCEPT

# Delete a rule by line number (use -L --line-numbers to find it first)
iptables -D INPUT 3

# Flush all rules in a chain (dangerous — removes all rules immediately)
iptables -F INPUT

# Save rules to survive reboot (Debian/Ubuntu)
iptables-save > /etc/iptables/rules.v4

# Save rules (RHEL/CentOS with iptables-services package)
service iptables save

# Restore saved rules
iptables-restore < /etc/iptables/rules.v4
```

**Ловушка блокировки доступа:** если выполнить `iptables -P INPUT DROP` до добавления правил ACCEPT для ESTABLISHED/RELATED и SSH, текущее SSH-соединение продолжит работать (ядро сохраняет существующие соединения), но повторно подключиться после отключения уже не получится. Сначала добавляйте правила ACCEPT и только потом устанавливайте политику DROP по умолчанию.

**Правила по умолчанию не сохраняются после перезагрузки:** правила `iptables` находятся в памяти ядра и исчезают после reboot. В Debian/Ubuntu установите `iptables-persistent` и сохраните правила через `netfilter-persistent save`. В RHEL используйте `firewalld` или службу `iptables` из пакета `iptables-services`.

**Порядок правил с `-A` и `-I`:** `-A` добавляет правило в конец цепочки. Если раньше уже сработало DROP, добавленное в конец ACCEPT не будет достигнуто. Используйте `-I` с номером позиции, чтобы вставить правило в нужное место.

---

### ufw — простой межсетевой экран

`ufw` предоставляет более простой интерфейс к `iptables`, предназначенный для серверов. Это стандартный инструмент Ubuntu. Внутри он всё равно создаёт правила `iptables`, поэтому можно управлять firewall через `ufw`, а проверять правила командой `iptables -L`.

```bash
# Initial setup — set defaults before enabling
ufw default deny incoming      # default DROP on INPUT
ufw default allow outgoing     # default ACCEPT on OUTPUT

# Enable (applies rules, persists across reboots automatically)
ufw enable

# Status — always check this after changes
ufw status verbose
ufw status numbered             # shows line numbers for deletion

# Allow rules
ufw allow 22/tcp                                       # SSH
ufw allow 80/tcp                                       # HTTP
ufw allow 443/tcp                                      # HTTPS
ufw allow from 10.0.0.50 to any port 5432 proto tcp   # DB from one host
ufw allow from 10.0.0.0/8 to any port 9090            # monitoring from internal net

# Deny rules (explicit deny — useful for documentation even with deny-incoming default)
ufw deny 3306                   # block MySQL from everywhere

# Allow by application profile (reads /etc/ufw/applications.d/)
ufw allow OpenSSH
ufw allow 'Nginx Full'          # opens both 80 and 443
ufw app list                    # see available profiles

# Delete rules
ufw delete allow 80/tcp         # by rule specification
ufw delete 3                    # by number from 'ufw status numbered'

# Reset everything (disables ufw, flushes all rules — use with caution)
ufw reset
```

**Когда использовать ufw, а когда iptables напрямую:** `ufw` подходит для простой защиты сервера с небольшим набором статических правил. Используйте `iptables` или `nftables`, когда нужен точный контроль: собственные цепочки, маркировка пакетов, NAT или интеграция с Docker.

**Особенность Docker и ufw:** Docker обходит `ufw`, напрямую записывая правила в `iptables`. Если выполнить `ufw deny 8080`, но запустить контейнер с `-p 8080:8080`, порт всё равно может быть доступен извне. Решения: запретить Docker управлять iptables (`"iptables": false` в `/etc/docker/daemon.json`) либо привязать контейнер к localhost (`-p 127.0.0.1:8080:8080`) и поручить внешний доступ reverse proxy.

---

### Облачные security groups

Облачные security group — stateful firewall на уровне гипервизора или сетевого интерфейса, то есть до того, как пакет попадёт в ОС экземпляра. Они работают независимо от процессов внутри ВМ и не могут быть обойдены из самой ОС.

| Свойство | iptables (хост) | AWS Security Group |
|---------|----------------|-------------------|
| Уровень применения | Ядро ОС | Гипервизор/NIC |
| Отслеживание состояния | Требуется модуль conntrack | Всегда stateful |
| Порядок правил | Важен (первое совпадение) | Проверяются все правила; действует наиболее разрешающее |
| Ссылки на другие группы | Нет | Да — можно указать SG как источник |
| Журналирование | Через действие LOG | Через VPC Flow Logs |
| Сохранение | Нужно сохранять явно | Сохраняется автоматически |

**Проверяются все правила, порядка нет:** в отличие от iptables, AWS security groups учитывают все входящие правила и применяют наиболее разрешающий результат. Принципа «первое совпадение» нет. Поэтому нельзя заблокировать конкретный IP, если другое правило разрешает весь трафик на этом порту: победит ALLOW. Для блокировки отдельных IP используйте Network ACL (NACL), где можно задать упорядоченные правила DENY.

**Ссылки на security group:** вместо CIDR-диапазона можно указать другую security group как источник. Любой экземпляр с этой группой автоматически получит доступ. Это рекомендуемый способ организовать внутреннее взаимодействие сервисов AWS: при добавлении или удалении экземпляров правила менять не нужно.

```
# Example: 3-tier application security group structure

# Web tier SG (sg-web)
Inbound:
  TCP  80    0.0.0.0/0, ::/0   ← HTTP from internet
  TCP  443   0.0.0.0/0, ::/0   ← HTTPS from internet

# App tier SG (sg-app)
Inbound:
  TCP  8080  sg-web              ← only from web tier (SG reference, not IPs)

# DB tier SG (sg-db)
Inbound:
  TCP  5432  sg-app              ← only from app tier

# All SGs — Outbound:
  All traffic  0.0.0.0/0        ← AWS default; restrict if compliance requires it
```

**Правила firewall в GCP** работают похоже, но применяются на уровне сети VPC, а не отдельных экземпляров. Для выбора целей используются **target tags** или **service accounts**; приоритет (0–65535, меньшее значение означает более высокий приоритет) определяет порядок обработки совпавших правил. В отличие от AWS security groups, GCP поддерживает явные правила DENY.

**NACL и Security Groups в AWS:** security groups отслеживают состояние соединений, поэтому при разрешении входящего порта 80 ответный исходящий трафик автоматически разрешается. NACL stateless: для каждого порта нужно отдельно разрешать входящий и исходящий трафик. NACL действуют на всю подсеть, security groups — на уровне экземпляра. Используйте NACL для ограничения последствий компрометации подсети, а security groups — для точной политики отдельных экземпляров.

---

### Типы балансировщиков нагрузки and Layer Differences

| Тип | Уровень OSI | Что анализирует | Типичное применение |
|------|-----------|-----------------|-------------|
| L4 (транспортный) | 4 — TCP/UDP | IP, порт, протокол | Любой TCP/UDP-протокол, минимальная задержка |
| L7 (прикладной) | 7 — HTTP | URL, заголовки, cookies, тело | Маршрутизация HTTP/HTTPS, завершение SSL/TLS |

**Балансировщики L4** передают TCP/UDP-соединения без анализа содержимого. Они быстрые, поскольку проверяют минимум данных. Они не различают `/api` и `/static`: видят только порт и протокол. Используйте L4 для балансировки не-HTTP-протоколов (gRPC поверх TCP, MQTT, протоколы баз данных, игровые серверы) или когда критична задержка.

**L7 load balancers** parse the HTTP request before routing. This enables:

- **Path-based routing:** `/api/*` → backend cluster A, `/images/*` → CDN or object storage
- **Host-based routing:** `api.example.com` → API fleet, `app.example.com` → frontend fleet
- **SSL/TLS termination:** handle certificates centrally; backends receive plain HTTP
- **Header manipulation:** inject `X-Real-IP`, `X-Forwarded-For`, custom auth headers
- **Active health checks:** send HTTP requests to `/health` and remove failing backends
- **Session affinity (sticky sessions):** route the same client to the same backend using cookies

**The TLS termination trade-off:** Terminating TLS at the load balancer means traffic between the LB and backends is unencrypted (typically acceptable within a private VPC network). If compliance requires end-to-end encryption, use TLS passthrough (L4) or re-encrypt at the backend (TLS bridging). Certificate management is significantly more complex in both cases and is usually avoided unless there's a hard compliance requirement.

**Load balancing algorithms comparison:**

| Algorithm | How it works | Best for |
|-----------|-------------|----------|
| Round Robin | Requests distributed sequentially | Stateless services with uniform request cost |
| Weighted Round Robin | Sequential but with proportional bias | Mixed instance sizes (e.g., 2 large + 4 small) |
| Least Connections | Next request goes to backend with fewest active connections | Variable request duration (long-lived sessions) |
| IP Hash | Hash of client IP determines backend | Sticky sessions without cookies |
| Random | Random backend selection | Simple, low-coordination environments |

**Least connections vs round robin:** Round robin breaks down when requests have highly variable durations — one slow backend accumulates connections while others sit idle. Least connections routes around this naturally. Prefer it for API services where some endpoints are significantly slower than others.

---

### nginx as a Load Balancer

nginx is both a web server and a capable L7 load balancer. It's widely used in environments where a dedicated LB (like HAProxy or an AWS ALB) isn't available or is overkill.

```nginx
# /etc/nginx/conf.d/api-lb.conf

upstream api_backends {
    # Default algorithm: round-robin
    server 10.0.0.10:8080;
    server 10.0.0.11:8080;
    server 10.0.0.12:8080;

    # Weight — 10.0.0.10 gets 50% of traffic, others get 25% each
    # server 10.0.0.10:8080 weight=2;
    # server 10.0.0.11:8080 weight=1;
    # server 10.0.0.12:8080 weight=1;

    # Least connections — better than round-robin for variable request durations
    # least_conn;

    # IP hash — sticky sessions based on client IP (same client → same backend)
    # ip_hash;

    # Mark a server as backup — only used if all primary servers are down
    # server 10.0.0.13:8080 backup;

    # Take a server out of rotation without removing the config
    # server 10.0.0.12:8080 down;

    # Connection keepalive pool to backends (reduces TCP handshake overhead)
    # Requires proxy_http_version 1.1 and clearing Connection header in location block
    keepalive 32;
}

server {
    listen 80;
    server_name api.example.com;
    return 301 https://$host$request_uri;   # Force HTTPS
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate     /etc/ssl/certs/api.example.com.crt;
    ssl_certificate_key /etc/ssl/private/api.example.com.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # Health check endpoint — respond directly, don't proxy to backends
    location /lb-health {
        access_log off;
        return 200 "ok\n";
        add_header Content-Type text/plain;
    }

    location /api/ {
        proxy_pass http://api_backends;     # no trailing slash — preserves /api/ prefix

        # Pass real client info to backends
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts — tune based on actual backend performance budgets
        proxy_connect_timeout  5s;    # time to establish connection to backend
        proxy_send_timeout    10s;    # time to send request to backend
        proxy_read_timeout    30s;    # time to wait for backend response

        # Enable keepalive to upstream (requires keepalive directive in upstream block)
        proxy_http_version 1.1;
        proxy_set_header Connection "";   # clear Connection header to allow keepalive
    }

    location /static/ {
        # Route static assets to object storage, bypassing app backends entirely
        proxy_pass https://my-bucket.s3.amazonaws.com/static/;
    }
}
```

**Gotcha — trailing slash in `proxy_pass`:** `proxy_pass http://api_backends` (no trailing slash) passes the full URI including `/api/` to the backend. `proxy_pass http://api_backends/` strips `/api/` and only sends the remainder. This is a frequent source of 404s that are hard to trace — always verify which behavior your backend expects.

**Passive vs active health checks:** By default, nginx uses passive health checks — it marks a backend as down only after it fails a real request. The `max_fails` and `fail_timeout` parameters control this behavior. Active health checks (polling `/health` periodically) require the `nginx_upstream_check_module` or nginx Plus. For production, active checks are strongly preferred because they detect failures before real user traffic is impacted.

```nginx
upstream api_backends {
    server 10.0.0.10:8080 max_fails=3 fail_timeout=30s;
    server 10.0.0.11:8080 max_fails=3 fail_timeout=30s;
    # After 3 failures within 30s, backend is removed for 30s
}
```

---

### Health Checks and Backend Failure Handling

Health checks are how a load balancer detects that a backend is unavailable and stops routing traffic to it. Without them, the LB continues sending requests to dead instances, causing user-visible errors.

| Check type | How it works | Failure detection speed | Cost |
|------------|-------------|------------------------|------|
| Passive | Observes real request failures | Slow — requires real user failures | Zero overhead |
| Active (TCP) | Opens TCP connection to backend port | Fast — detects port-level failures | Low |
| Active (HTTP) | Sends HTTP request, checks status code | Fast — detects application-level failures | Low-medium |
| Active (deep) | HTTP request that exercises a DB/cache dependency | Accurate — detects dependency failures | Medium-high |

**Designing a `/health` endpoint:** A good health endpoint returns 200 only when the instance is ready to serve traffic. A minimal endpoint that always returns 200 defeats the purpose. A useful endpoint checks:
- Can the application connect to its database?
- Are required config files present?
- Is memory below a threshold?

However, **don't make health checks too strict** — if your `/health` endpoint checks every dependency and your shared Redis cluster has a blip, you'll drain all backends simultaneously and cause a full outage. The common pattern is a two-tier approach: a liveness check (is the process alive?) and a readiness check (is it ready to serve traffic?). Kubernetes formalizes this distinction with `livenessProbe` and `readinessProbe`.

```yaml
# Kubernetes deployment with separate liveness and readiness probes
containers:
  - name: api
    image: myapp:latest
    livenessProbe:
      httpGet:
        path: /healthz/live      # is the process alive? failure = restart container
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 10
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /healthz/ready     # is it ready for traffic? failure = remove from LB
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5
      failureThreshold: 2
```

**Connection draining:** When a backend is removed from rotation (scale-in, deployment, health failure), in-flight requests should be allowed to complete rather than being abruptly terminated. AWS ALB calls this "deregistration delay" (default 300s). nginx has no built-in draining for dynamic upstream changes, but you can achieve it by marking a backend `down` and waiting before removing it.

---

## Примеры

### Example 1: Hardening a New Ubuntu Server with ufw

Scenario: You've just provisioned a new Ubuntu 22.04 server. It has a public IP. Your goal is to allow SSH from your office IP only, allow web traffic from everywhere, and drop everything else.

```bash
# Step 1: Verify ufw is installed (it is by default on Ubuntu)
ufw version

# Step 2: Set default policies BEFORE enabling
ufw default deny incoming
ufw default allow outgoing

# Step 3: Add rules BEFORE enabling — you're not protected yet, but also not locked out
# Allow SSH only from your office IP (replace with your actual IP)
ufw allow from 203.0.113.10 to any port 22 proto tcp

# Allow web traffic from anywhere
ufw allow 80/tcp
ufw allow 443/tcp

# Allow ICMP (ping) for diagnostics — ufw doesn't expose this via 'allow' commands
# Edit /etc/ufw/before.rules and ensure the ICMP rules in the INPUT section are present
# (they are by default on Ubuntu — verify before removing)

# Step 4: Enable ufw
ufw enable
# You will see: "Command may disrupt existing ssh connections. Proceed with operation (y|n)?"
# Answer y — your SSH rule is already in place

# Step 5: Verify the ruleset
ufw status verbose
# Expected output:
# Status: active
# Default: deny (incoming), allow (outgoing), disabled (routed)
# New profiles: skip
#
# To                         Action      From
# --                         ------      ----
# 22/tcp                     ALLOW IN    203.0.113.10
# 80/tcp                     ALLOW IN    Anywhere
# 443/tcp                    ALLOW IN    Anywhere

# Step 6: Test from a different IP that should be blocked
# From a machine that is NOT 203.0.113.10:
ssh root@<server-ip>
# Expected: Connection timed out (DROP, not REJECT — no response)

# From 203.0.113.10:
ssh root@<server-ip>
# Expected: normal SSH prompt
```

---

### Example 2: Setting Up iptables Rules and Persisting Them

Scenario: A Debian production server running a REST API on port 8080. You need to lock it down, allow monitoring from an internal subnet, and ensure rules survive reboot.

```bash
# Step 1: Install persistence package
apt install -y iptables-persistent

# Step 2: Flush existing rules to start clean (verify nothing important is in place first)
iptables -F
iptables -X   # delete user-defined chains
iptables -Z   # zero counters

# Step 3: Set permissive defaults temporarily while building rules
iptables -P INPUT ACCEPT
iptables -P OUTPUT ACCEPT
iptables -P FORWARD DROP

# Step 4: Build the INPUT chain
# Loopback
iptables -A INPUT -i lo -j ACCEPT

# Stateful — allow established/related connections
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# SSH — allow from anywhere (or restrict to bastion IP in production)
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# API port — allow from anywhere (public-facing)
iptables -A INPUT -p tcp --dport 8080 -j ACCEPT

# Prometheus node_exporter — allow only from monitoring subnet
iptables -A INPUT -p tcp --dport 9100 -s 10.0.10.0/24 -j ACCEPT

# ICMP ping — allow for diagnostics
iptables -A INPUT -p icmp --icmp-type echo-request -j ACCEPT

# Step 5: Now set default DROP
iptables -P INPUT DROP

# Step 6: Verify rules look correct before saving
iptables -L -v -n --line-numbers
# Check: ESTABLISHED/RELATED appears before DROP policy
# Check: SSH rule is present
# Check: node_exporter only from 10.0.10.0/24

# Step 7: Persist rules
netfilter-persistent save
# Writes to /etc/iptables/rules.v4 and /etc/iptables/rules.v6

# Step 8: Simulate reboot and verify
netfilter-persistent reload
iptables -L -v -n --line-numbers
# Rules should be identical to before

# Step 9: Test that node_exporter is not accessible from outside the monitoring subnet
# From a host NOT in 10.0.10.0/24:
curl --connect-timeout 5 http://<server-ip>:9100/metrics
# Expected: curl: (28) Connection timed out — DROP in effect

# From monitoring host in 10.0.10.0/24:
curl http://<server-ip>:9100/metrics
# Expected: Prometheus metrics output
```

---

### Example 3: nginx Load Balancer with Health Check and Path-Based Routing

Scenario: You have two backend API servers (`10.0.0.10:8080`, `10.0.0.11:8080`) and a separate static content server (`10.0.0.20:80`). You want nginx to route `/api/` to the API backends and `/static/` to the content server, with health checks.

```bash
# Step 1: Install nginx on the load balancer host
apt install -y nginx

# Step 2: Create the load balancer config
cat > /etc/nginx/conf.d/app-lb.conf << 'EOF'
upstream api_backends {
    least_conn;   # better than round-robin for variable API response times

    server 10.0.0.10:8080 max_fails=3 fail_timeout=15s;
    server 10.0.0.11:8080 max_fails=3 fail_timeout=15s;

    keepalive 16;   # maintain up to 16 idle keepalive connections per worker
}

upstream static_backend {
    server 10.0.0.20:80;
}

server {
    listen 80;
    server_name app.example.com;

    # Access log with upstream response time for performance monitoring
    log_format upstream_timing '$remote_addr - $upstream_addr [$time_local] '
                                '"$request" $status $body_bytes_sent '
                                'rt=$request_time uct=$upstream_connect_time '
                                'uht=$upstream_header_time urt=$upstream_response_time';
    access_log /var/log/nginx/app-lb.access.log upstream_timing;

    # LB health check — cloud load balancers and uptime monitors hit this
    location /lb-health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    # API traffic
    location /api/ {
        proxy_pass http://api_backends;   # no trailing slash — /api/users → /api/users

        proxy_http_version 1.1;
        proxy_set_header Connection "";   # required for keepalive to upstream

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout  3s;
        proxy_read_timeout    20s;

        # Return 502 immediately if all upstreams are down rather than queuing
        proxy_next_upstream error timeout http_502 http_503;
        proxy_next_upstream_tries 2;
    }

    # Static content
    location /static/ {
        proxy_pass http://static_backend/;   # trailing slash strips /static/ prefix

        proxy_cache_valid 200 1h;
        add_header X-Cache-Status $upstream_cache_status;
    }

    # Catch-all — return 404 for anything not explicitly routed
    location / {
        return 404;
    }
}
EOF

# Step 3: Test the nginx config syntax
nginx -t
# Expected: nginx: configuration file /etc/nginx/nginx.conf syntax is ok
#           nginx: configuration file /etc/nginx/nginx.conf test is successful

# Step 4: Reload nginx (no downtime — in-flight requests complete on old workers)
systemctl reload nginx

# Step 5: Verify load balancing is working
# Send 6 requests and watch which backend responds (add a response header on backends)
for i in {1..6}; do
    curl -s -o /dev/null -w "Backend: %{http_code} - %{url_effective}\n" \
         http://app.example.com/api/users
done

# Step 6: Simulate a backend failure — bring down 10.0.0.10
# On 10.0.0.10:
systemctl stop myapi

# Back on the LB host — watch error log for failure detection
tail -f /var/log/nginx/error.log
# After 3 failures within 15s, nginx marks 10.0.0.10 as down
# All subsequent requests should go to 10.0.0.11

# Step 7: Verify the static routing strips the /static/ prefix correctly
curl -v http://app.example.com/static/logo.png
# Request should reach static_backend as GET /logo.png (not /static/logo.png)
```

---

### Example 4: Diagnosing a Connectivity Failure Across Firewall Layers

Scenario: A developer reports that their new microservice can't reach the PostgreSQL database at `10.0.1.5:5432`. The service runs on `10.0.1.10`. You need to systematically diagnose which firewall layer is dropping the connection.

```bash
# ---- On the application host (10.0.1.10) ----

# Step 1: Verify the target is reachable at the network layer (ICMP)
ping -c 3 10.0.1.5
# If this fails: routing problem or ICMP is blocked — check VPC routing tables

# Step 2: Test TCP connectivity to the specific port
# nc (netcat) is the right tool — curl won't work for PostgreSQL
nc -zv 10.0.1.5 5432
# Connection to 10.0.1.5 5432 port [tcp/postgresql] succeeded!
# If this hangs: firewall is DROPping (no response)
# If this fails immediately: firewall is REJECTing

# Step 3: Check if the local OS firewall is interfering outbound
iptables -L OUTPUT -v -n
# Look for any rules that could match outbound TCP to 10.0.1.5:5432

# Step 4: Use traceroute to see where packets stop
traceroute -T -p 5432 10.0.1.5
# -T uses TCP SYN packets (more likely to match real firewall behavior than ICMP)

# ---- On the database host (10.0.1.5) ----

# Step 5: Check if PostgreSQL is actually listening
ss -tlnp | grep 5432
# Expected: LISTEN  0  128  0.0.0.0:5432  0.0.0.0:*  users:(("postgres",...))
# If not listening: PostgreSQL isn't running or is bound to a different interface

# Step 6: Check the INPUT chain for rules allowing/blocking port 5432
iptables -L INPUT -v -n --line-numbers | grep -E "5432|ACCEPT|DROP"

# Step 7: Temporarily test by adding a permissive rule (REMOVE after testing)
iptables -I INPUT 1 -p tcp --dport 5432 -s 10.0.1.10 -j ACCEPT -m comment --comment "DEBUG TEMP"
# Re-test from 10.0.1.10: nc -zv 10.0.1.5 5432
# If this fixes it: the original ruleset is missing this ACCEPT rule
# Remove the temp rule after confirming:
iptables -D INPUT 1

# ---- Cloud layer check ----

# Step 8: If the above is clear, check cloud security groups
# AWS CLI — check the security group attached to the DB instance
aws ec2 describe-security-groups \
    --group-ids sg-0123456789abcdef0 \
    --query 'SecurityGroups[0].IpPermissions'
# Look for an inbound rule: TCP 5432 from sg-app or 10.0.1.0/24

# If the SG is missing the rule, add it:
aws ec2 authorize-security-group-ingress \
    --group-id sg-0123456789abcdef0 \
    --protocol tcp \
    --port 5432 \
    --source-group sg-0987654321fedcba0   # the app tier's security group ID

# Step 9: Final verification from application host
nc -zv 10.0.1.5 5432
# Should now succeed at every layer
```

---

## Практические задания

### Exercise 1: Build and Test an iptables Ruleset

Set up a Linux VM (Vagrant, VirtualBox, or any cloud instance) with at least two network interfaces or test using two terminals on the same machine.

1. Flush all existing iptables rules and start from a clean state.
2. Build a ruleset that allows: SSH (port 22), HTTP (port 80), and ICMP. Block everything else on INPUT with a default DROP policy.
3. Add a rule that allows traffic to port 8080 **only** from the loopback interface (`127.0.0.1`).
4. Verify your rules with `iptables -L -v -n --line-numbers` and confirm the rule order is correct.
5. Test that port 9090 is unreachable from an external address but that SSH and HTTP work.
6. Save the rules using `iptables-save` and simulate a reload by flushing all rules and restoring from the saved file. Confirm the rules are identical after restore.

**Challenge:** Add a rule that rate-limits new SSH connections to 3 per minute per source IP using the `hashlimit` module. Research the `hashlimit` module syntax — it is not covered in this lesson but is commonly used in production to prevent brute-force attacks.

---

### Exercise 2: nginx Load Balancer with Weighted Backends and Failure Simulation

Use three terminals or three Docker containers as backends.

1. Start three simple HTTP servers on ports 8081, 8082, and 8083 that return different responses so you can identify which backend is serving (use `python3 -m http.server` with different `index.html` files, or simple `nc` listeners).
2. Write an nginx `upstream` block that distributes traffic with weights: 8081 gets 50% of requests, 8082 gets 30%, 8083 gets 20%.
3. Configure passive health checks so that after 2 failures within 10 seconds, a backend is removed for 20 seconds.
4. Send 20 requests using a loop and verify the distribution roughly matches the weights.
5. Stop the process on port 8081 and send another 20 requests. Confirm that after the initial failures, traffic is redistributed to the remaining backends.
6. Restart port 8081. Verify nginx resumes sending traffic to it after the `fail_timeout` expires.

**Explain in writing:** Why does round-robin work less well than weighted round-robin here? When would `least_conn` be a better choice than weighted round-robin?

---

### Exercise 3: Debug a Deliberately Misconfigured Firewall

This exercise requires two machines on the same network (or two Docker containers with a shared network).

**Setup (run these on machine B):**

```bash
# Machine B: Start a web server on port 80
python3 -m http.server 80 &

# Add a misconfigured iptables rule:
iptables -A INPUT -p tcp --dport 80 -j DROP
iptables -I INPUT 1 -p tcp --dport 22 -j ACCEPT
# NOTE: The ESTABLISHED/RELATED rule is intentionally missing
iptables -P INPUT DROP
```

From machine A, attempt to connect to machine B on port 80. You should observe a timeout.

Your tasks:
1. From machine A, determine whether the port is being DROPped or REJECTed without logging into machine B. Explain how you determined this.
2. Log into machine B via SSH (this still works — your existing session is ESTABLISHED). Identify the specific rule causing the problem using `iptables -L`.
3. Fix the firewall so that: port 80 is accessible from machine A, SSH remains accessible, and the missing stateful rule is added in the correct position.
4. Verify the fix without flushing all rules — use `-I` to insert at the correct position and `-D` to remove the blocking rule.

**Explain:** What would happen to your SSH session if you had added `iptables -P INPUT DROP` without the ESTABLISHED/RELATED rule in place and then disconnected? Why?

---

### Exercise 4: AWS Security Group Design for a Two-Tier App

This exercise is design and CLI-based. You need AWS CLI access and an AWS account (free tier is sufficient).

**Scenario:** You are deploying a web application with a frontend (port 443, public) and a backend API (port 8080, internal only). Both tiers run on EC2 instances.

1. Using the AWS CLI, create two security groups: `sg-frontend` and `sg-backend` in the same VPC.
2. Configure `sg-frontend` to allow inbound TCP 443 from `0.0.0.0/0` and inbound TCP 22 from your IP only.
3. Configure `sg-backend` to allow inbound TCP 8080 **only from `sg-frontend`** using a security group reference (not a CIDR range).
4. Launch two t2.micro instances: one with `sg-frontend`, one with `sg-backend`. Run `python3 -m http.server 8080` on the backend instance.
5. From the frontend instance, verify you can reach port 8080 on the backend instance. From your laptop, verify you **cannot** reach port 8080 on the backend instance directly.
6. Add a rule to `sg-backend` that accidentally allows all inbound traffic (`0.0.0.0/0` on all ports). Verify that port 8080 is now accessible from your laptop.
7. Remove the overly permissive rule. Verify access is restricted again.

**Explain:** Why did step 6 work even though the original rules were still present? What AWS mechanism would you use if you needed a rule to explicitly DENY a specific IP even if another rule allows it?

---

### Быстрая проверка

1. Parse the default policy from an `iptables -L` chain header.

   ```bash
   echo "Chain INPUT (policy DROP)" | awk '{print $4}' | tr -d ')'
   ```

   ```expected_output
   DROP
   ```

hint: Focus on how iptables displays chain policy information in the header line of its output and what text parsing tool can extract a specific field from that line.
hint: Use grep to isolate the chain header line, then pipe it to awk and target the field inside the parentheses with a pattern like awk -F'[()]' '{print $2}' to pull out the policy word.

2. Determine which backend a round-robin load balancer sends request #7 to (0-indexed, 3 backends).

   ```bash
   python3 -c "print(7 % 3)"
   ```

   ```expected_output
   1
   ```
hint: Think about how round-robin distribution cycles through backends using the request index and the total number of backends.
hint: Use the modulo operation: request_index % number_of_backends (i.e., 7 % 3) to find which backend index receives the request.
