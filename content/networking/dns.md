---
title: DNS — система доменных имён
module: networking
duration_min: 15
difficulty: beginner
tags: [networking, dns, dig, nslookup, records, resolution]
exercises: 4
---

## Обзор

DNS (Domain Name System) — распределённая система, преобразующая понятные человеку имена вроде `api.example.com` в IP-адреса, с которыми работают сетевые устройства. Любое обращение приложения к сервису — базе данных, стороннему API или Kubernetes Service — начинается с DNS-запроса. При сбое DNS появляются тайм-ауты соединения, ошибки NXDOMAIN и загадочные задержки, похожие на ошибки приложения. Понимание DNS необходимо для первичной диагностики сетевых проблем.

DNS опирается на три принципа: **делегирование** — ни один сервер не знает всего, полномочия передаются по иерархии; **кэширование** — каждый ответ содержит TTL, определяющий срок повторного использования; **согласованность с течением времени** — изменения распространяются по мере истечения кэшей, а не мгновенно. Эти принципы объясняют, почему DNS-изменения требуют времени, разные клиенты могут видеть разные ответы, а запросы к двум DNS-серверам иногда возвращают разные результаты.

В DevOps DNS находится на пересечении инфраструктуры, сетей и развёртывания. DNS-записи настраивают при запуске сервиса, TTL регулируют при blue-green-развёртываниях, внутренний DNS используют для обнаружения сервисов Kubernetes, а при проблемах связи между сервисами — диагностируют. Облачные провайдеры (AWS Route 53, GCP Cloud DNS, Cloudflare) предоставляют DNS через API, поэтому DNS становится полноценной частью Infrastructure as Code. Глубокое понимание DNS помогает быстрее диагностировать инциденты, проектировать безопасные стратегии развёртывания и находить первопричины сбоев.

---

## Основные понятия

### Цепочка разрешения DNS-имени

Когда процесс Linux разрешает имя, запрос проходит несколько уровней, прежде чем попасть в сеть. Важно понимать эту цепочку: в зависимости от конфигурации приложение может получить ответ из локального кэша, `/etc/hosts` или в результате полного рекурсивного запроса.

```
Your app (getaddrinfo() syscall)
  → /etc/nsswitch.conf  ← determines lookup order: "files dns" or "files mdns dns"
    → /etc/hosts        ← checked first; static overrides always win
    → Local stub resolver
        systemd-resolved: 127.0.0.53:53
        OR the nameserver listed in /etc/resolv.conf directly
      → Recursive resolver (8.8.8.8, 1.1.1.1, or your VPC's resolver)
        → Root nameservers (13 clusters: a.root-servers.net … m.root-servers.net)
          → TLD nameservers (.com, .net, .io — managed by registries)
            → Authoritative nameservers for the zone (your DNS provider)
              → Final answer
```

Каждый этап кэширует результат на время TTL. Основное кэширование происходит на рекурсивном резолвере, который отдаёт сохранённые ответы всем клиентам за ним. Корневые DNS-серверы и серверы доменов верхнего уровня запрашиваются только при отсутствии кэшированной делегации.

**Важно:** `dig` обходит `/etc/hosts` и `nsswitch.conf`, обращаясь напрямую к DNS. `getent hosts` и `ping` используют полный механизм разрешения имён, включая `/etc/hosts`. Поэтому `dig test.local` может вернуть NXDOMAIN, а `ping test.local` — успешно разрешить имя из `/etc/hosts`.

```bash
# Which resolver is your system actually using?
cat /etc/resolv.conf

# On systemd-resolved systems, the real config is here:
resolvectl status

# Test the full nsswitch stack (includes /etc/hosts):
getent hosts api.example.com

# Test only DNS (bypasses /etc/hosts):
dig +short api.example.com

# See the full resolution chain step by step:
dig +trace api.example.com
```

**Особенность `nsswitch.conf`:** если `files` указан перед `dns` (значение по умолчанию), неверная запись в `/etc/hosts` незаметно перекрывает DNS. Такое случается, когда инженер добавляет временную запись для тестирования и забывает её удалить.

---

### Основные файлы конфигурации

Работу DNS на Linux-узле определяют два файла. Ошибка в любом из них может вызвать сбой, который трудно диагностировать.

**`/etc/resolv.conf`** — задаёт DNS-серверы для запросов и правила обработки коротких имён:

```
nameserver 10.0.0.2        # primary resolver (e.g. VPC internal resolver)
nameserver 8.8.8.8         # fallback — only used if primary times out or is unreachable
search us-east-1.compute.internal example.internal  # appended to single-label names
options ndots:5            # names with fewer than 5 dots get search domains appended first
options timeout:2          # seconds before trying next nameserver
options attempts:3         # total attempts per nameserver
```

**`/etc/hosts`** — статические сопоставления имён и IP-адресов, проверяемые до DNS:

```
127.0.0.1   localhost
::1         localhost ip6-localhost
10.0.0.100  db.internal db   # multiple aliases on one line — all resolve to same IP
10.0.0.101  redis.internal
```

**Особенность `ndots`:** параметр `ndots:5` в `/etc/resolv.conf` Kubernetes означает, что для `api.example.com` (три точки, четыре метки — меньше пяти) сначала добавляются поисковые домены и только потом выполняется запрос полного доменного имени (FQDN). Внутри pod поиск может пройти так:
1. `api.example.com.default.svc.cluster.local`
2. `api.example.com.svc.cluster.local`
3. `api.example.com.cluster.local`
4. `api.example.com.` ← наконец, исходное имя

Каждая неудачная попытка добавляет задержку 5–30 мс. При тысячах запросов это превращается в проблему производительности, похожую на медленную работу приложения. **Решение:** добавьте точку в конце имени, чтобы принудительно выполнить поиск FQDN: `api.example.com.`

```bash
# Verify what ndots is set to in your pod:
kubectl exec -it <pod> -- cat /etc/resolv.conf

# Check how many search attempts a lookup is making:
dig +stats api.example.com  # shows query count; high = search domain expansion
```

---

### Типы DNS-записей

| Тип | Назначение | Пример значения |
|------|---------|--------------|
| **A** | Сопоставляет имя с IPv4-адресом | `1.2.3.4` |
| **AAAA** | Сопоставляет имя с IPv6-адресом | `2001:db8::1` |
| **CNAME** | Псевдоним: сопоставляет имя с другим именем | `www.example.com → example.com` |
| **MX** | Почтовый сервер с приоритетом | `10 mail.example.com` |
| **TXT** | Произвольный текст; используется для SPF, DKIM и подтверждения домена | `"v=spf1 include:sendgrid.net ~all"` |
| **NS** | Авторитетные DNS-серверы зоны | `ns1.dnsprovider.com` |
| **PTR** | Обратный DNS: IP → имя | `4.3.2.1.in-addr.arpa → api.example.com` |
| **SRV** | Параметры сервиса: приоритет, вес, порт и узел | `10 20 443 backend.example.com` |
| **SOA** | Start of Authority: serial, refresh, retry, expire, negative TTL | Используется резолверами для управления поведением зоны |
| **CAA** | Определяет, каким центрам сертификации разрешено выпускать TLS-сертификаты | `0 issue "letsencrypt.org"` |

**Ограничение CNAME:** запись CNAME не может сосуществовать с другими записями для того же имени. Нельзя назначить CNAME корневому домену (`example.com`), поскольку для зоны также нужны записи SOA и NS. Поэтому DNS-провайдеры предлагают собственные записи ALIAS или ANAME: они разрешают цель CNAME на стороне сервера и возвращают итоговую A-запись, что безопасно для корня зоны.

**Несколько A-записей — примитивная балансировка:** для одного имени можно опубликовать несколько A-записей с разными IP. Резолверы возвращают их все, а клиенты обычно используют первую. Это не замена настоящему балансировщику: проверка состояния отсутствует.

```bash
# See all A records for a name (multiple = round-robin DNS)
dig +noall +answer api.example.com A

# SRV records in Kubernetes: expose port alongside hostname
dig +short _http._tcp.my-service.my-namespace.svc.cluster.local SRV
```

---

### `dig` — основной инструмент диагностики DNS

`dig` — стандартный инструмент для исследования DNS. Изучите его флаги: они постоянно нужны при отладке и расследовании инцидентов.

```bash
# Basic A record lookup
dig api.example.com

# Short output (just the answer, no metadata)
dig +short api.example.com

# Query a specific record type
dig api.example.com AAAA
dig api.example.com MX
dig api.example.com TXT
dig api.example.com NS
dig api.example.com SOA
dig api.example.com CAA

# Query a specific nameserver (bypasses local resolver entirely)
dig @8.8.8.8 api.example.com           # Google Public DNS
dig @1.1.1.1 api.example.com           # Cloudflare
dig @ns1.dnsprovider.com example.com   # Ask the authoritative server directly

# Trace every delegation step from root to authoritative
dig +trace api.example.com

# Reverse lookup (IP → hostname via PTR record)
dig -x 8.8.8.8

# Show TTL alongside the answer
dig +noall +answer +ttlid api.example.com A

# Batch queries from a file (one name per line)
dig -f domains.txt +short

# Check if DNSSEC validation is working
dig +dnssec +short api.example.com A
```

**`nslookup` и `dig`:** `nslookup` удобен в интерактивном режиме, но его вывод сложнее обрабатывать скриптами, а некоторые пограничные случаи он обрабатывает иначе. Для диагностики предпочтителен `dig`: его вывод однозначен и стабилен.

---

### Как читать вывод `dig`

Многие инженеры смотрят только на ANSWER SECTION и игнорируют остальное. Другие секции содержат важную диагностическую информацию для расследования инцидентов.

```
; <<>> DiG 9.18.1 <<>> api.example.com
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 12345
;;                              ^^^^^^^^
;;                              Status tells you the result class — read this first

;; QUESTION SECTION:
;api.example.com.       IN      A      ← what we asked for (note trailing dot = FQDN)

;; ANSWER SECTION:
api.example.com.  300   IN  A   52.14.123.45
;;               ^^^              ^^^^^^^^^^^^
;;               TTL in seconds   The actual answer

;; AUTHORITY SECTION:
example.com.      3600  IN  NS  ns1.dnsprovider.com.
;;  Who is authoritative for this zone
;;  If this is empty on a positive answer, the response came from cache

;; ADDITIONAL SECTION:
ns1.dnsprovider.com.  3600  IN  A  198.51.100.1
;;  Glue records: the resolver includes the NS server's IP so you don't
;;  need another full lookup just to contact the nameserver

;; Query time: 12 msec
;; SERVER: 8.8.8.8#53    ← which resolver actually answered this query
;; WHEN: Mon Jan 01 00:00:00 UTC 2025
;; MSG SIZE  rcvd: 88
```

**Коды `status`, которые нужно знать:**

| Статус | Значение | Частая причина |
|--------|---------|-------------|
| `NOERROR` | Запрос обработан успешно | — |
| `NXDOMAIN` | Домен не существует | Опечатка, удалённая запись, неверная зона |
| `SERVFAIL` | Резолвер не получил авторитетный ответ | Ошибка зоны, недоступный NS, сбой DNSSEC |
| `REFUSED` | Сервер отказался обрабатывать запрос | Firewall, ACL, запрещена рекурсия |
| `NOERROR` с пустым ANSWER | Домен существует, но записи такого типа нет | Запрошен неверный тип или запись ещё не создана |

**`NOERROR` без ответа — не то же самое, что `NXDOMAIN`.** `NXDOMAIN` означает, что имя вообще не существует. Пустой ответ `NOERROR` означает, что имя существует, но записи запрошенного типа нет. Если перепутать эти случаи, диагностика будет неверной.

---

### TTL и распространение DNS-изменений

TTL (Time To Live) — количество секунд, в течение которых резолвер может хранить ответ в кэше. Его задаёт администратор авторитетной зоны, а не клиент и не резолвер.

| TTL | Применение |
|-----|---------|
| 30–60 с | Активные развёртывания, canary-релизы, blue-green-переключения |
| 300 с | Сервисы, которые меняются время от времени |
| 3600s | Stable infrastructure (origin IPs, MX records) |
| 86400s | Near-static records (NS records, rarely-changed infra) |

**Pre-change checklist for safe DNS cutover:**
1. Check current TTL: `dig +ttlid api.example.com A`
2. If TTL > 300, lower it to 60 and **wait for at least the current TTL duration** before proceeding — every resolver that cached the old value needs to expire it
3. Make your record change
4. Verify from multiple resolvers (`@8.8.8.8`, `@1.1.1.1`, `@your-internal-resolver`)
5. Raise TTL back after you're confident the change is stable

```bash
# Check current TTL (the value decrements as cache ages — query twice to confirm)
dig +noall +answer +ttlid @8.8.8.8 api.example.com A

# Poll until the new IP appears across the cutover window
watch -n 5 'dig +short @8.8.8.8 api.example.com A'

# Check what the authoritative server says right now (ignores all caching)
dig @$(dig +short api.example.com NS | head -1) api.example.com A
```

**Negative TTL:** NXDOMAIN responses are also cached, for the duration specified in the SOA record's minimum TTL field. If you create a record for a name that was recently queried and got NXDOMAIN, resolvers may continue returning NXDOMAIN until their negative cache expires. This trips up engineers who delete and recreate records quickly.

```bash
# Find the negative TTL (the last number in the SOA record)
dig +short example.com SOA
# ns1.provider.com. admin.example.com. 2024010101 3600 900 604800 300
#                                                                  ^^^
#                                                         negative TTL: 300 seconds
```

---

### Internal DNS and Service Discovery

In modern infrastructure, DNS is the universal service discovery mechanism. Cloud and container platforms all rely on it, and understanding their conventions saves significant debugging time.

**Kubernetes DNS (CoreDNS):**

```bash
# Full FQDN format:
# <service>.<namespace>.svc.cluster.local

# From within the same namespace, short names resolve via search domains:
curl http://my-service                              # resolves in same namespace
curl http://my-service.my-ns                       # explicit namespace
curl http://my-service.my-ns.svc.cluster.local     # FQDN — always works everywhere

# Headless services (clusterIP: None) return individual pod IPs:
# <pod-ip-dashes>.<service>.<namespace>.svc.cluster.local
# e.g., 10-0-1-50.my-service.my-ns.svc.cluster.local

# Debug CoreDNS from inside a pod:
kubectl exec -it <pod> -- nslookup kubernetes.default
kubectl exec -it <pod> -- cat /etc/resolv.conf
```

**Docker Compose:**
```yaml
services:
  api:
    image: myapp:latest
    # Can reach "db" simply by hostname "db" — Docker's embedded resolver handles it
    environment:
      - DB_HOST=db
  db:
    image: postgres:15
  cache:
    image: redis:7
    # "api" reaches this as hostname "cache"
```

**AWS VPC DNS:**
```bash
# VPC resolver is always at: base_of_VPC_CIDR + 2
# VPC 10.0.0.0/16 → resolver at 10.0.0.2
# VPC 172.31.0.0/16 → resolver at 172.31.0.2

# EC2 private DNS (enabled by default in VPCs):
# ip-<private-ip-dashes>.<region>.compute.internal
# e.g., ip-10-0-1-50.us-east-1.compute.internal

# Never hardcode IPs for managed services — they change without warning:
mydb.abc123.us-east-1.rds.amazonaws.com
my-alb-1234567890.us-east-1.elb.amazonaws.com
mycluster.abc123.ng.0001.use1.cache.amazonaws.com
```

**Split-horizon DNS:** the same name resolves to different IPs depending on where the query originates. Common pattern: `api.example.com` returns a public IP from the internet but a private VPC IP from inside the VPC. This is intentional — it avoids hairpinning through a public load balancer for internal traffic. Debugging requires querying both resolvers and comparing.

```bash
# Detect split-horizon: are you getting internal or external answers?
dig @10.0.0.2 api.example.com A     # internal VPC resolver → private IP expected
dig @8.8.8.8 api.example.com A      # external resolver → public IP expected

# If both return the same IP when you expected different, split-horizon isn't configured
```

---

### DNS in the Context of TLS and Security

DNS affects security in ways that catch engineers off guard. Several security mechanisms are implemented entirely as DNS records.

**CAA records** restrict which Certificate Authorities can issue certificates for your domain. If your CA isn't listed, issuance fails silently during cert renewal — a common cause of unexpected TLS outages:

```bash
dig example.com CAA
# 0 issue "letsencrypt.org"       ← only Let's Encrypt may issue
# 0 issuewild ";"                 ← no wildcard certs allowed from any CA
# 0 iodef "mailto:security@example.com"  ← notify on unauthorized issuance attempts
```

**SPF/DKIM/DMARC** are TXT records. Email deliverability failures are almost always DNS problems:

```bash
# SPF: which servers may send email for this domain
dig example.com TXT | grep spf
# "v=spf1 include:sendgrid.net include:amazonses.com ~all"

# DMARC: policy for handling SPF/DKIM failures
dig _dmarc.example.com TXT
# "v=DMARC1; p=reject; rua=mailto:dmarc@example.com"

# DKIM: public key for verifying email signatures (selector varies)
dig selector1._domainkey.example.com TXT
```

**DNSSEC** adds cryptographic signatures to DNS responses, preventing cache poisoning and spoofing. Check if a domain uses it:

```bash
dig +dnssec example.com A
# Look for RRSIG records in the ANSWER section — presence means DNSSEC is active

# Validate the DNSSEC chain explicitly:
dig +sigchase +trusted-key=/etc/trusted-key.key example.com A  # if supported

# SERVFAIL + DNSSEC = almost always a DNSSEC misconfiguration:
dig @8.8.8.8 example.com A        # SERVFAIL
dig @8.8.8.8 +cd example.com A    # +cd disables DNSSEC validation — if this works,
                                   # DNSSEC is the problem
```

---

### Common DNS Failure Patterns

```bash
# ── PATTERN 1: "Name or service not known" ──────────────────────────────────
# Resolver unreachable or /etc/resolv.conf misconfigured
ping 8.8.8.8                            # check network first — is it a DNS problem or routing?
cat /etc/resolv.conf                    # is there a valid nameserver entry?
dig @8.8.8.8 api.example.com           # bypass local resolver entirely

# ── PATTERN 2: Stale cached record ──────────────────────────────────────────
# You updated DNS but old IP is still returned
dig +ttlid api.example.com A            # how many seconds until cache expires?
dig @ns1.authoritative.com api.example.com  # what does authoritative server say now?

# Flush local DNS cache:
resolvectl flush-caches                 # systemd-resolved (Ubuntu 18.04+, Debian, CentOS 8+)
dscacheutil -flushcache                 # macOS (also: sudo killall -HUP mDNSResponder)

# ── PATTERN 3: SERVFAIL ─────────────────────────────────────────────────────
# Resolver can't get an authoritative answer
dig +trace api.example.com              # where exactly does the chain break?
dig @ns1.authoritative.com example.com SOA  # is the authoritative server responding at all?
dig +cd @8.8.8.8 api.example.com A     # if +cd fixes it, DNSSEC misconfiguration

# ── PATTERN 4: Works from some places, not others ───────────────────────────
# Split-horizon, negative TTL, or propagation lag
dig @8.8.8.8 api.example.com A         # external resolver
dig @1.1.1.1 api.example.com A         # different external resolver
dig @10.0.0.2 api.example.com A        # internal resolver
# Compare all three — different answers = split-horizon or caching inconsistency

# ── PATTERN 5: Kubernetes pod can't resolve external names ──────────────────
kubectl exec -it <pod> -- cat /etc/resolv.conf    # verify CoreDNS is the nameserver
kubectl exec -it <pod> -- nslookup google.com     # does external resolution work?
kubectl get pods -n kube-system | grep coredns    # are CoreDNS pods running?
kubectl logs -n kube-system -l k8s-app=kube-dns  # any errors in CoreDNS logs?
```

---

## Примеры

### Example 1: Diagnosing a Failed Deployment Cutover

Your team just updated the DNS A record for `api.example.com` from `1.2.3.4` to `5.6.7.8` as part of a blue-green deployment. Users on some networks are still hitting the old server. Diagnose the situation and confirm the cutover is complete.

```bash
# Step 1: Check what the authoritative nameserver says (ground truth)
# First, find the authoritative NS for the zone:
dig +short example.com NS
# ns1.dnsprovider.com.
# ns2.dnsprovider.com.

# Ask the authoritative server directly — bypasses all caching:
dig @ns1.dnsprovider.com +noall +answer +ttlid api.example.com A
# api.example.com.  60  IN  A  5.6.7.8
# TTL=60 is good — the new record is live

# Step 2: Check what major public resolvers have cached:
for resolver in 8.8.8.8 1.1.1.1 9.9.9.9; do
  echo -n "Resolver $resolver: "
  dig +short @$resolver api.example.com A
done
# Resolver 8.8.8.8: 5.6.7.8      ← updated
# Resolver 1.1.1.1: 1.2.3.4      ← still old (hasn't expired yet)
# Resolver 9.9.9.9: 5.6.7.8      ← updated

# Step 3: Check remaining TTL on the stale resolver
dig +noall +answer +ttlid @1.1.1.1 api.example.com A
# api.example.com.  47  IN  A  1.2.3.4
# This cache entry expires in 47 seconds — users on Cloudflare will auto-update

# Step 4: Poll until all public resolvers converge
watch -n 10 'for r in 8.8.8.8 1.1.1.1 9.9.9.9; do echo -n "$r: "; dig +short @$r api.example.com A; done'

# Step 5: After confirmation, raise the TTL back to a stable value
# (Done via your DNS provider's API or UI — not via dig)
```

**What to look for:** if any resolver is still returning the old IP after `old_TTL + 60` seconds, something is wrong — either the authoritative server wasn't updated, or an intermediate resolver is violating TTL. Use `dig +trace` to identify where the chain is breaking.

---

### Example 2: Debugging a Kubernetes Pod That Can't Reach an External API

An application pod is failing to connect to `api.stripe.com`. The error is `dial tcp: lookup api.stripe.com: no such host`. The service works fine from your laptop.

```bash
# Step 1: Exec into the pod and verify basic DNS works
kubectl exec -it deploy/my-app -- sh

# Can it resolve anything at all?
nslookup kubernetes.default
# Server:   10.96.0.10       ← CoreDNS ClusterIP
# Address:  10.96.0.10:53
# Name:     kubernetes.default.svc.cluster.local
# Address:  10.96.0.1        ← success: internal DNS works

# Step 2: Try resolving the external name
nslookup api.stripe.com
# Server:   10.96.0.10
# ** server can't find api.stripe.com: SERVFAIL

# Step 3: Check the pod's resolv.conf
cat /etc/resolv.conf
# nameserver 10.96.0.10
# search default.svc.cluster.local svc.cluster.local cluster.local
# options ndots:5
# ← ndots:5 means api.stripe.com (3 dots) gets search domains prepended first

# Step 4: Check if CoreDNS is forwarding external queries correctly
# (exit the pod first)
kubectl get configmap coredns -n kube-system -o yaml
```

```yaml
# CoreDNS Corefile — the forward block controls external resolution:
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health
        kubernetes cluster.local in-addr.arpa ip6.arpa {
            pods insecure
            fallthrough in-addr.arpa ip6.arpa
        }
        forward . 8.8.8.8 8.8.4.4   # ← forwards non-cluster names to Google DNS
        cache 30
        loop
        reload
        loadbalance
    }
```

```bash
# Step 5: If the forward block is missing or pointing to an unreachable resolver,
# test reachability from a node:
kubectl get nodes -o wide             # get a node IP
# SSH to the node and verify:
dig @8.8.8.8 api.stripe.com A        # can the node reach 8.8.8.8:53?

# Step 6: Fix — if the cluster's nodes can't reach external DNS,
# update CoreDNS to use the VPC resolver instead:
# Edit the configmap: forward . 10.0.0.2  (your VPC resolver)
kubectl edit configmap coredns -n kube-system
# CoreDNS auto-reloads the config (the "reload" plugin handles this)
```

---

### Example 3: Setting Up Split-Horizon DNS for a Service on AWS

You're deploying a service that should resolve to a private IP inside your VPC and a public IP from the internet. This is the split-horizon pattern.

```bash
# Verify current behavior (both should return the same public IP before the change):
dig @8.8.8.8 api.example.com A        # external: 203.0.113.10 (public ALB)
dig @10.0.0.2 api.example.com A       # internal: 203.0.113.10 (same — wrong)

# With AWS Route 53, you create two hosted zones:
# 1. Public hosted zone: example.com  — serves internet traffic
# 2. Private hosted zone: example.com — associated with your VPC, serves internal traffic

# After setup, verify split-horizon is working:
dig @8.8.8.8 api.example.com A
# 203.0.113.10   ← public ALB (correct for external clients)

dig @10.0.0.2 api.example.com A
# 10.0.1.50      ← internal load balancer or direct pod IP (correct for internal)

# Useful for: avoiding hairpinning through the internet for internal service calls,
# hiding internal topology from public DNS, and reducing latency for intra-VPC traffic.

# Verify you're using the VPC resolver on an EC2 instance:
cat /etc/resolv.conf
# nameserver 10.0.0.2   ← should be VPC base + 2

# If it's wrong (pointing to 8.8.8.8), you'll never get the private answer:
# Fix for Ubuntu: edit /etc/netplan/ or use cloud-init to set nameservers
```

---

### Example 4: Validating DNS Before a TLS Certificate Renewal

Your Let's Encrypt cert renewal is failing. The ACME challenge requires a specific TXT record to be visible publicly. Diagnose and confirm the record is propagated before retrying.

```bash
# Step 1: Check what the ACME client is trying to create
# Let's Encrypt HTTP-01 uses /.well-known/acme-challenge/
# DNS-01 uses a TXT record: _acme-challenge.<domain>

# Step 2: Verify the TXT record exists at the authoritative server
dig +noall +answer _acme-challenge.example.com TXT @ns1.dnsprovider.com
# _acme-challenge.example.com.  60  IN  TXT  "abc123xyz-validation-token"
# Good — the record is at the authoritative server

# Step 3: Verify it's visible from Let's Encrypt's perspective (public resolvers)
dig +noall +answer _acme-challenge.example.com TXT @8.8.8.8
dig +noall +answer _acme-challenge.example.com TXT @1.1.1.1

# Step 4: If the record doesn't appear yet, check the TTL on the old answer
dig +ttlid _acme-challenge.example.com TXT @8.8.8.8
# If this returns NXDOMAIN with a short TTL, you're waiting on negative cache expiry

# Step 5: Also verify CAA records won't block issuance
dig example.com CAA
# If there's a CAA record, "letsencrypt.org" must be listed, or issuance is blocked:
# 0 issue "letsencrypt.org"   ← required

# Step 6: Once propagated, retry the cert renewal
# (certbot / acme.sh will query public resolvers before submitting the challenge)
certbot renew --dry-run --cert-name example.com

# Cleanup: TXT records created for ACME challenges should be deleted after use
# (most ACME clients do this automatically)
```

---

## Практические задания

### Exercise 1: Trace and Interpret a Full Resolution Chain

**Goal:** understand how delegation works from root to authoritative.

1. Pick any public domain (e.g., `github.com`).
2. Run `dig +trace github.com A` and capture the output.
3. Identify each of the following in the output: the root nameserver that was queried, the TLD nameserver for `.com`, the authoritative nameserver for `github.com`, and the final A record with its TTL.
4. Now run `dig +trace nonexistent-12345.github.com A` and explain why the trace stops where it does and what status code appears.
5. Answer: at which layer in the chain would a SERVFAIL most likely originate, versus an NXDOMAIN?

---

### Exercise 2: Reproduce and Fix the Kubernetes `ndots` Latency Problem

**Goal:** observe how `ndots:5` affects lookup behavior and understand the fix.

1. If you have a Kubernetes cluster available: `kubectl run dns-debug --image=busybox --restart=Never -- sleep 3600` then exec into it. Otherwise, simulate by temporarily modifying your own `/etc/resolv.conf` to add `options ndots:5` and `search default.svc.cluster.local svc.cluster.local cluster.local`.
2. Run `dig +stats api.stripe.com A` and note the number of queries made (visible in `+stats` output). Then run `dig +stats api.stripe.com. A` (with trailing dot). Compare the query counts and explain the difference.
3. Determine the exact sequence of names the resolver tries before reaching `api.stripe.com.` for the version without the trailing dot.
4. Find or construct an example where appending a trailing dot would break resolution (hint: think about internal-only names with short forms).

---

### Exercise 3: Diagnose a Simulated DNS Failure

**Goal:** use `dig` flags and systematic reasoning to diagnose DNS problems without guessing.

Set up the following scenario (or observe it if it already exists): configure `/etc/hosts` to map `test-service.internal` to `127.0.0.1`. Then answer these questions using only command-line tools:

1. Run both `ping -c 1 test-service.internal` and `dig +short test-service.internal A`. One will resolve, one won't. Explain exactly why each behaves as it does.
2. Run `getent hosts test-service.internal`. Which layer of the resolution chain is this testing?
3. Now remove the `/etc/hosts` entry and query a name that doesn't exist: `dig +noall +answer +status nxdomain-test-12345.example.com A @8.8.8.8`. What status code do you see? What status code would you see if you queried for an existing domain but a record type that doesn't exist (e.g., `dig example.com AAAA @8.8.8.8` for a domain with no IPv6)?
4. Run `dig +short example.com SOA` and identify the negative TTL value. Explain what would happen if you rapidly deleted and recreated a DNS record for a subdomain of that domain.

---

### Exercise 4: Audit a Domain's DNS Security Posture

**Goal:** use DNS record lookups to assess a domain's email authentication and TLS certificate issuance controls.

Pick a domain you control, or use a public domain for read-only analysis (e.g., `cloudflare.com`).

1. Retrieve and interpret the SPF record. Does it use `~all` (soft fail) or `-all` (hard fail)? What does the difference mean for email security?
2. Retrieve the DMARC record at `_dmarc.<domain>`. What is the policy (`p=`)? What would happen to an email that fails both SPF and DKIM checks under each of the three possible policy values?
3. Retrieve the CAA record. Which CAs are authorized? If there is no CAA record, what does that mean for cert issuance?
4. Run `dig +dnssec <domain> A @8.8.8.8`. Is there an RRSIG record in the answer? Now run the same command with `+cd` (checking disabled). If the results differ, what does that tell you?
5. Explain in one paragraph how a compromised DNS record (e.g., an attacker who gains access to your DNS provider) could affect TLS certificate issuance, email delivery, and DNSSEC validation simultaneously.

---

### Быстрая проверка

1. Extract the TTL from a mock DNS A record — the same field you read in `dig` output.

   ```bash
   echo "github.com. 60 IN A 140.82.113.4" | awk '{print $2}'
   ```

   ```expected_output
   60
   ```

hint: Think about how DNS record fields are structured and which position in a typical A record line holds the TTL value.
hint: Use awk to parse the record and print the second field with `awk '{print $2}'`, since TTL occupies that column in standard dig-style output.

2. Detect whether an FQDN has a trailing dot (which bypasses `ndots` search-domain expansion).

   ```bash
   echo "api.stripe.com." | grep -q '\.$' && echo "FQDN (no expansion)" || echo "relative (ndots applies)"
   ```

   ```expected_output
   FQDN (no expansion)
   ```
hint: Consider how DNS resolution behaves differently when a hostname ends with a dot, and think about what string pattern you would check for.
hint: Use a conditional test in bash with a case statement or parameter expansion like [[ "$fqdn" == *. ]] to detect the trailing dot character.
