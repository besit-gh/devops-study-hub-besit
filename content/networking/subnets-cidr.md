---
title: Подсети и CIDR
module: networking
duration_min: 15
difficulty: intermediate
tags: [networking, cidr, subnets, ip, vpc, routing]
exercises: 4
---

## Обзор

Нотация CIDR (Classless Inter-Domain Routing) и разбиение сетей на подсети — базовые навыки DevOps-инженера, работающего с облаками, контейнерами или локальной инфраструктурой. CIDR встречается при создании VPC, настройке security group только для офисного IP, назначении подсетей Pod и Service в Kubernetes, настройке split tunneling VPN и проверке пересечения адресных диапазонов связанных VPC. Ошибка в этих вопросах может привести к незаметным проблемам маршрутизации, уязвимостям или необходимости переработать сеть после исчерпания адресов.

Основной принцип подсетей — иерархическое распределение адресов: большой диапазон делится на меньшие блоки, каждый с фиксированным сетевым префиксом и переменной частью для узлов. Длина префикса (`/N`) определяет границу между ними. Из этого следуют остальные свойства: сколько узлов помещается в подсеть, находятся ли два IP в одной подсети, нужен ли маршрутизатор и как эффективно агрегировать маршруты.

В DevOps CIDR относится к инфраструктурному уровню, но постоянно встречается и в инструментах более высокого уровня: ресурсах Terraform `aws_subnet`, values Helm-чартов для CNI-плагинов Kubernetes, правилах firewall в Ansible и сетевых конфигурациях Docker. Правильное планирование подсетей на этапе проектирования избавляет от серьёзных проблем: изменить CIDR production-VPC с работающими нагрузками непросто.

---

## Основные понятия

### IP-адреса и двоичное представление

IPv4-адрес — 32-битное целое число, записываемое четырьмя октетами, разделёнными точками. Все операции с подсетями — маскирование, побитовое AND и проверка диапазонов — выполняются на двоичном уровне. Десятичная запись с точками лишь удобна для человека.

```
192     .168    .1      .100
11000000.10101000.00000001.01100100
```

Каждый октет содержит 8 бит, поэтому весь адрес — 32-битный. Максимальное значение октета — 255 (все 8 бит равны 1). Подсеть делит эти 32 бита на две части:

- **Сетевая часть** (N крайних левых бит): определяет подсеть и одинакова для всех узлов в ней
- **Часть узла** (оставшиеся 32−N бит): определяет конкретный узел подсети

Граница между этими частями задаётся длиной префикса. Вся логика разбиения на подсети сводится к вопросу: «где проходит граница и что из этого следует?»

Чтобы освоить двоичное представление, запомните следующие значения:

| Десятичное | Двоичное |
|---------|----------|
| 128     | 10000000 |
| 192     | 11000000 |
| 224     | 11100000 |
| 240     | 11110000 |
| 248     | 11111000 |
| 252     | 11111100 |
| 254     | 11111110 |
| 255     | 11111111 |

Именно эти значения встречаются в последнем октете масок, граница которых проходит не по октету. Их стоит запомнить.

### Нотация CIDR

Нотация CIDR записывает адресный блок как `<адрес сети>/<длина префикса>`. В адресе сети все биты узла равны нулю. Длина префикса показывает, сколько из 32 бит относятся к сетевой части.

`10.0.1.0/24` означает:
- Первые 24 бита (3 октета) фиксированы: `10.0.1`
- Последние 8 бит изменяются от `.0` до `.255`
- Всего адресов: 2⁸ = 256
- Доступно адресов узлов: 254 (адрес сети `.0` и широковещательный адрес `.255` зарезервированы)

| CIDR | Всего адресов | Доступно узлам | Типичное применение |
|------|----------------|--------------|-------------|
| /32 | 1 | 1 | Один узел; правило security group для одного IP |
| /31 | 2 | 2 | Соединения point-to-point (RFC 3021) |
| /30 | 4 | 2 | Минимальная подсеть общего назначения |
| /28 | 16 | 14 | Небольшая изолированная подсеть |
| /27 | 32 | 30 | Маленькая подсеть |
| /26 | 64 | 62 | Средняя подсеть |
| /25 | 128 | 126 | Половина /24 |
| /24 | 256 | 254 | Стандартная подсеть на зону доступности |
| /23 | 512 | 510 | Две подсети /24 |
| /22 | 1 024 | 1 022 | Пул узлов с запасом для роста |
| /20 | 4 096 | 4 094 | Большая подсеть |
| /16 | 65 536 | 65 534 | Типичный CIDR VPC |
| /8 | 16 777 216 | — | Полный приватный блок класса A RFC 1918 |

**Быстрый расчёт в уме:** при уменьшении префикса на 1 (например, `/24` → `/23`) адресное пространство удваивается. При увеличении на 1 — уменьшается вдвое. В `/24` 256 адресов; в `/20` часть узла на 4 бита длиннее, поэтому 2⁴ × 256 = 4 096 адресов.

**Зарезервированные адреса AWS и GCP:** облачные провайдеры резервируют не только адрес сети и broadcast. AWS резервирует пять адресов в каждой подсети (адрес сети, маршрутизатор VPC, DNS-резолвер, будущие нужды и broadcast). Поэтому в `/28` остаётся 11 доступных IP вместо 14. GCP резервирует четыре адреса на подсеть. Перед точным расчётом проверяйте документацию провайдера.

### Маска подсети

Маска подсети — более старый способ записи длины префикса: 32-битное значение, где первые N бит равны 1, а остальные — 0. Она передаёт ту же информацию, что и CIDR-префикс, но в десятичной форме с точками; такой формат всё ещё встречается в конфигурациях ОС и устаревших инструментах.

| Префикс CIDR | Маска подсети | Двоичное представление последнего октета |
|-------------|-------------------|-------------------|
| /24         | 255.255.255.0     | 00000000          |
| /25         | 255.255.255.128   | 10000000          |
| /26         | 255.255.255.192   | 11000000          |
| /27         | 255.255.255.224   | 11100000          |
| /28         | 255.255.255.240   | 11110000          |
| /29         | 255.255.255.248   | 11111000          |
| /16         | 255.255.0.0       | —                 |
| /8          | 255.0.0.0         | —                 |

Путаница чаще всего возникает с масками, граница которых проходит внутри октета (`/25`, `/26`, `/27`, `/28`, `/29`). Маска `/26` — `255.255.255.192`, а последний октет в двоичном виде — `11000000`: два старших бита относятся к сети, шесть младших — к узлу. Поэтому блок `/26` всегда начинается с адреса, у которого последний октет кратен 64: `.0`, `.64`, `.128` или `.192`.

**Правило выравнивания:** подсеть размера S должна начинаться с адреса, кратного S. `10.0.1.64/26` корректен, а `10.0.1.70/26` — нет: в адресе сети установлены биты узла. Для автоматической проверки используйте `strict=True` в модуле Python `ipaddress`.

```python
import ipaddress

# This raises ValueError: host bits set
try:
    ipaddress.ip_network("10.0.1.70/26", strict=True)
except ValueError as e:
    print(e)  # 10.0.1.70/26 has host bits set

# Correct: strip host bits to get the network address
net = ipaddress.ip_network("10.0.1.70/26", strict=False)
print(net)  # 10.0.1.64/26
```

### Как определяется принадлежность к подсети

Ядро определяет, находится ли IP назначения в локальной подсети или нужен маршрутизатор, с помощью побитовой операции AND:

```
IP:      10.0.1.55  = 00001010.00000000.00000001.00110111
Mask:  255.255.255.0 = 11111111.11111111.11111111.00000000
AND:    10.0.1.0    = 00001010.00000000.00000001.00000000
```

Если `IP AND mask == адрес сети`, узел находится в локальной подсети — пакет отправляется напрямую через ARP.
В противном случае пакет отправляется на шлюз по умолчанию, который маршрутизирует его дальше.

Именно поэтому `10.0.1.5/24` и `10.0.2.5/24` не могут обмениваться данными без маршрутизатора, хотя оба входят в `10.0.0.0/16`. Каждый узел использует собственную маску `/24`:

```
10.0.1.5  AND 255.255.255.0 = 10.0.1.0   ← host A's network
10.0.2.5  AND 255.255.255.0 = 10.0.2.0   ← host B's network
```

Результаты различаются, поэтому узел A считает B внешним для своей подсети и отправляет трафик на шлюз. Суперсеть `/16` здесь не влияет на решение: ядро использует маску, настроенную на локальном интерфейсе.

**Частый вопрос на собеседовании:** «Оба адреса находятся в `10.0.0.0/16`, почему они не общаются напрямую?» Потому что локальную или удалённую сеть определяет *префикс, настроенный на каждом интерфейсе*, а не охватывающая суперсеть. Межсетевое взаимодействие обеспечивает таблица маршрутизации.

```bash
# Check your interface's address and prefix length
ip addr show eth0

# See the routing table — "scope link" entries are local subnet routes
ip route show

# Which route would be used to reach a specific address?
ip route get 10.0.2.5
# output: 10.0.2.5 via 10.0.1.1 dev eth0 src 10.0.1.55
#         shows gateway is used → off-subnet

# Verify two IPs are in the same subnet using ipcalc
ipcalc 10.0.1.55/24
ipcalc 10.0.1.200/24
# Compare the "Network:" lines — if they match, same subnet
```

### Диапазоны частных адресов (RFC 1918)

Эти три блока зарезервированы для частного использования и не маршрутизируются в публичном интернете. Используйте их во внутренней инфраструктуре, но тщательно планируйте адресацию, чтобы избежать пересечений между VPC, локальными сетями, Docker и Kubernetes.

| Название | Диапазон | CIDR | Размер | Типичное применение |
|----------|-------------------------------|----------------|---------|---------------------------------|
| Класс A | 10.0.0.0 – 10.255.255.255 | 10.0.0.0/8 | ~16 млн | Корпоративные VPC и большие кластеры |
| Class B  | 172.16.0.0 – 172.31.255.255   | 172.16.0.0/12  | ~1M     | Docker default bridge networks  |
| Class C  | 192.168.0.0 – 192.168.255.255 | 192.168.0.0/16 | ~65K    | Home networks, small offices    |

**Docker default bridge conflict:** Docker uses `172.17.0.0/16` for its default bridge network. Additional user-defined networks are allocated from `172.18.0.0/16`, `172.19.0.0/16`, etc., stepping through the `172.16.0.0/12` block. If your VPC, VPN, or corporate network uses any address in `172.16.0.0/12`, containers on that host will have routing conflicts — packets destined for your corporate network will be incorrectly sent to the Docker bridge instead of the gateway.

Override Docker's address pool in `/etc/docker/daemon.json` and restart the daemon:

```json
{
  "bip": "192.168.200.1/24",
  "default-address-pools": [
    { "base": "192.168.201.0/24", "size": 28 }
  ]
}
```

```bash
sudo systemctl restart docker
# Verify the new bridge address
docker network inspect bridge | grep Subnet
```

**Kubernetes default CIDRs by CNI plugin:**

| CNI         | Default pod CIDR  | Default service CIDR | Notes                               |
|-------------|-------------------|----------------------|-------------------------------------|
| Flannel     | 10.244.0.0/16     | 10.96.0.0/12         | Set via `--pod-network-cidr` in kubeadm |
| Calico      | 192.168.0.0/16    | 10.96.0.0/12         | Conflicts with home/office networks |
| Weave       | 10.32.0.0/12      | 10.96.0.0/12         | Large pod range by default          |
| AWS VPC CNI | Same as node VPC  | 10.100.0.0/16        | Pods get real VPC IPs               |

With AWS VPC CNI, pods get real VPC IP addresses — which means your VPC subnets must be large enough to accommodate pods, not just nodes. A node pool of 10 nodes each running 110 pods needs 1,100+ IP addresses in those subnets. A `/24` per AZ is dangerously small for EKS with VPC CNI; use `/20` or larger.

**Overlapping CIDRs will silently break routing.** Two peered VPCs with overlapping CIDRs cannot communicate — AWS will reject the peering. VPN split tunneling will misdirect traffic. Always check for overlaps before allocating a new CIDR block.

```python
import ipaddress

def check_overlap(cidr1, cidr2):
    a = ipaddress.ip_network(cidr1)
    b = ipaddress.ip_network(cidr2)
    return a.overlaps(b)

print(check_overlap("10.0.0.0/16", "10.0.1.0/24"))  # True — contained within
print(check_overlap("10.0.0.0/24", "10.0.1.0/24"))  # False — adjacent, no overlap
print(check_overlap("172.16.0.0/12", "172.20.0.0/16"))  # True — 172.20 is inside /12
```

### Supernets and Route Aggregation

A supernet (or aggregate) is a larger block that encompasses multiple smaller blocks. Route aggregation reduces routing table size by replacing many specific routes with one summary route — this is critical for BGP scaling and clean security group rule sets.

`10.0.0.0/16` is the supernet for all of these:
- `10.0.1.0/24`
- `10.0.2.0/24`
- `10.0.128.0/17`

To check whether a CIDR is a valid aggregate, verify that all the specific blocks are contiguous and the supernet's network bits match across all of them.

```python
import ipaddress

# Find the immediate supernet (one prefix bit shorter)
net = ipaddress.ip_network("10.0.1.0/24")
print(net.supernet())  # 10.0.0.0/23

# Collapse a list of networks into the minimal set of CIDRs
addresses = [
    ipaddress.ip_network("10.0.0.0/25"),
    ipaddress.ip_network("10.0.0.128/25"),
]
collapsed = list(ipaddress.collapse_addresses(addresses))
print(collapsed)  # [IPv4Network('10.0.0.0/24')]

# Non-contiguous blocks do NOT collapse cleanly
addresses2 = [
    ipaddress.ip_network("10.0.0.0/24"),
    ipaddress.ip_network("10.0.2.0/24"),  # gap at 10.0.1.0/24
]
collapsed2 = list(ipaddress.collapse_addresses(addresses2))
print(collapsed2)  # [IPv4Network('10.0.0.0/24'), IPv4Network('10.0.2.0/24')]
# Cannot collapse — they don't form a valid supernet without including 10.0.1.0/24
```

This matters for security group rules and firewall policies — instead of 8 separate rules for 8 adjacent /24s, one /21 rule covers the same space with one rule. It also matters for Transit Gateway route tables: aggregate routes where possible to avoid hitting route table limits.

### Subnetting a Block: Splitting CIDRs

When you receive an address block and need to divide it, you extend the prefix length. Each additional bit splits the space in half.

Splitting `10.0.0.0/24` into four `/26` subnets:

| Subnet | CIDR            | Host range                | Usable hosts |
|--------|-----------------|---------------------------|--------------|
| 1st    | 10.0.0.0/26    | 10.0.0.1 – 10.0.0.62     | 62           |
| 2nd    | 10.0.0.64/26   | 10.0.0.65 – 10.0.0.126   | 62           |
| 3rd    | 10.0.0.128/26  | 10.0.0.129 – 10.0.0.190  | 62           |
| 4th    | 10.0.0.192/26  | 10.0.0.193 – 10.0.0.254  | 62           |

```python
import ipaddress

parent = ipaddress.ip_network("10.0.0.0/24")

# Split into /26 subnets
for subnet in parent.subnets(new_prefix=26):
    hosts = list(subnet.hosts())
    print(f"{subnet}  first={hosts[0]}  last={hosts[-1]}  count={len(hosts)}")

# Split into exactly 2 halves (/25 each)
for subnet in parent.subnets(prefixlen_diff=1):
    print(subnet)
# 10.0.0.0/25
# 10.0.0.128/25
```

**The new prefix must be longer than the parent prefix.** You can split a `/24` into `/25`, `/26`, `/27` etc. — but not into `/23`. Calling `subnets(new_prefix=23)` on a `/24` raises `ValueError`.

**Unequal splits are not directly supported in CIDR.** CIDR blocks are always powers of two. If you need 100 hosts and 50 hosts from a `/24`, you'd allocate a `/25` (126 hosts) and a `/26` (62 hosts), accepting some waste. This is the standard trade-off in VLSM (Variable Length Subnet Masking).

### Designing a VPC Subnet Layout

A production AWS VPC needs subnets that are:
- Spread across availability zones for resilience
- Sized for the workloads they'll contain (with growth room)
- Separated by tier (public / private / data) for security group and NACL control
- Planned with future expansion in mind — re-CIDRing a running VPC is painful

Example layout for `10.0.0.0/16` across two AZs with three tiers:

| Subnet name | CIDR           | AZ         | Tier    | Purpose                      |
|-------------|----------------|------------|---------|------------------------------|
| public-1a   | 10.0.0.0/24    | us-east-1a | Public  | ALB, NAT Gateway             |
| public-1b   | 10.0.1.0/24    | us-east-1b | Public  | ALB, NAT Gateway             |
| private-1a  | 10.0.16.0/20   | us-east-1a | Private | EKS nodes, app servers       |
| private-1b  | 10.0.32.0/20   | us-east-1b | Private | EKS nodes, app servers       |
| data-1a     | 10.0.48.0/24   | us-east-1a | Data    | RDS, ElastiCache             |
| data-1b     | 10.0.49.0/24   | us-east-1b | Data    | RDS, ElastiCache             |

The private subnets use `/20` (4,094 usable addresses each) rather than `/24` — intentional when EKS nodes each consume dozens of pod IPs via AWS VPC CNI. The gap between `10.0.1.0/24` and `10.0.16.0/20` (`10.0.2.0` through `10.0.15.255`) is deliberately reserved for a third AZ.

**Routing rules for each tier:**
- Public subnets: route `0.0.0.0/0 → internet gateway`; instances can have public IPs
- Private subnets: route `0.0.0.0/0 → NAT gateway` (which lives in the public subnet); no inbound from internet
- Data subnets: no internet route at all; only VPC-local routes; access controlled by security groups

**Reserve the upper half of your VPC CIDR.** With `10.0.0.0/16`, you have 256 possible `/24` subnets. Use the low range now; reserve `10.0.128.0/17` for future expansion — adding AZs, VPC peering, or Transit Gateway attachments that require non-overlapping space.

```hcl
# Terraform example: defining subnets programmatically
variable "vpc_cidr" {
  default = "10.0.0.0/16"
}

locals {
  # Public subnets: 10.0.0.0/24 and 10.0.1.0/24
  public_cidrs = ["10.0.0.0/24", "10.0.1.0/24"]
  # Private subnets: /20 each for EKS pod IP headroom
  private_cidrs = ["10.0.16.0/20", "10.0.32.0/20"]
  azs = ["us-east-1a", "us-east-1b"]
}

resource "aws_subnet" "public" {
  count             = length(local.public_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = local.public_cidrs[count.index]
  availability_zone = local.azs[count.index]

  # Instances in public subnets get public IPs automatically
  map_public_ip_on_launch = true

  tags = {
    Name = "public-${local.azs[count.index]}"
    Tier = "public"
  }
}

resource "aws_subnet" "private" {
  count             = length(local.private_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = local.private_cidrs[count.index]
  availability_zone = local.azs[count.index]

  # No public IPs in private subnets
  map_public_ip_on_launch = false

  tags = {
    Name                              = "private-${local.azs[count.index]}"
    Tier                              = "private"
    # Required tag for EKS to discover subnets for internal load balancers
    "kubernetes.io/role/internal-elb" = "1"
  }
}
```

### Using `ipcalc` and `sipcalc` for Quick Verification

You shouldn't do subnet math by hand in production. Use command-line tools to verify your calculations before committing to Terraform or a YAML config.

```bash
# ipcalc: shows network, broadcast, first/last host, and mask
ipcalc 10.0.16.0/20
# Network:   10.0.16.0/20
# Broadcast: 10.0.31.255
# HostMin:   10.0.16.1
# HostMax:   10.0.31.254
# Hosts/Net: 4094

# Check if an IP is inside a given CIDR (exit code 0 = yes)
ipcalc -c 10.0.16.50/20  # checks if .50 is a valid host in /20

# sipcalc: more verbose, shows binary representation
sipcalc 10.0.16.0/20

# Python one-liner for quick checks in scripts
python3 -c "
import ipaddress
n = ipaddress.ip_network('10.0.16.0/20')
print(f'first={n.network_address+1} last={n.broadcast_address-1} size={n.num_addresses}')
"

# Check if an IP belongs to a subnet
python3 -c "
import ipaddress
ip = ipaddress.ip_address('10.0.16.50')
net = ipaddress.ip_network('10.0.16.0/20')
print(ip in net)  # True
"
```

---

## Примеры

### Example 1: Auditing a VPC for Overlapping Subnets Before Peering

You want to peer two VPCs. Before requesting the peering, verify their subnets don't overlap — AWS will reject the peering if they do, but better to catch it before writing the Terraform.

```python
#!/usr/bin/env python3
# check_vpc_overlap.py
import ipaddress

# Subnet CIDRs from VPC A (us-east-1)
vpc_a = [
    "10.0.0.0/24",    # public-1a
    "10.0.1.0/24",    # public-1b
    "10.0.16.0/20",   # private-1a
    "10.0.32.0/20",   # private-1b
]

# Subnet CIDRs from VPC B (us-west-2) — note 10.0.16.0/20 appears in both!
vpc_b = [
    "10.0.100.0/24",
    "10.0.101.0/24",
    "10.0.16.0/20",   # ← conflict
    "10.0.120.0/20",
]

nets_a = [ipaddress.ip_network(c) for c in vpc_a]
nets_b = [ipaddress.ip_network(c) for c in vpc_b]

conflicts = []
for a in nets_a:
    for b in nets_b:
        if a.overlaps(b):
            conflicts.append((str(a), str(b)))

if conflicts:
    print("OVERLAP DETECTED — peering will fail:")
    for a, b in conflicts:
        print(f"  VPC-A {a} overlaps VPC-B {b}")
else:
    print("No overlaps found — safe to peer.")
```

```bash
python3 check_vpc_overlap.py
# OVERLAP DETECTED — peering will fail:
#   VPC-A 10.0.16.0/20 overlaps VPC-B 10.0.16.0/20
```

**Fix:** reassign VPC B's private subnets to `10.1.16.0/20` and `10.1.32.0/20`. Re-run the script to confirm no overlap before proceeding.

---

### Example 2: Calculating Kubernetes Node Capacity for AWS VPC CNI

With AWS VPC CNI, each pod gets a real VPC IP. The number of pods per node is limited by the instance type's network interfaces and IPs per interface. You need to ensure your subnets have enough IPs before scaling.

```bash
# Check the max pods per node type (requires aws CLI and kubectl)
# AWS publishes these limits: https://github.com/awslabs/amazon-eks-ami/blob/master/files/eni-max-pods.txt

# m5.xlarge: 4 ENIs × 15 IPs − 4 (one per ENI for the ENI itself) = 56 pods max
# (formula: (ENIs × (IPs_per_ENI − 1)) + 2 for kube-system daemonsets)

# For a cluster: 20 nodes × 56 pods = 1,120 pod IPs
# Plus 20 node IPs = 1,140 total IPs needed per AZ (if spread across 2 AZs → 570 per AZ)

python3 - <<'EOF'
import ipaddress

subnet_cidr = "10.0.16.0/20"
net = ipaddress.ip_network(subnet_cidr)

total_ips = net.num_addresses
# AWS reserves 5 IPs per subnet
usable_ips = total_ips - 5

nodes = 10
pods_per_node = 56
node_ips = nodes
pod_ips = nodes * pods_per_node

required = node_ips + pod_ips
print(f"Subnet: {subnet_cidr}")
print(f"Usable IPs: {usable_ips}")
print(f"Required IPs ({nodes} nodes × {pods_per_node} pods): {required}")
print(f"Remaining after allocation: {usable_ips - required}")
print(f"Sufficient: {usable_ips >= required}")
EOF
# Subnet: 10.0.16.0/20
# Usable IPs: 4091
# Required IPs (10 nodes × 56 pods): 570
# Remaining after allocation: 3521
# Sufficient: True
```

**Verify after cluster creation:**

```bash
# Check IPs currently in use in a subnet
aws ec2 describe-network-interfaces \
  --filters "Name=subnet-id,Values=subnet-xxxxxxxx" \
  --query 'NetworkInterfaces[*].PrivateIpAddresses[*].PrivateIpAddress' \
  --output text | wc -w

# Check available IPs remaining in the subnet
aws ec2 describe-subnets \
  --subnet-ids subnet-xxxxxxxx \
  --query 'Subnets[0].AvailableIpAddressCount'
```

---

### Example 3: Fixing a Docker / VPN Routing Conflict

Your corporate VPN uses `172.16.0.0/12`. Docker's default bridge allocates from the same range. After connecting to VPN, containers can't reach corporate services.

```bash
# Diagnose: see what Docker networks exist and their CIDRs
docker network ls
docker network inspect bridge | grep -A2 '"Subnet"'
# "Subnet": "172.17.0.0/16"   ← overlaps corporate VPN range

# Check routing table — both Docker and VPN are competing for 172.x traffic
ip route show | grep 172

# Fix: reconfigure Docker to use a non-conflicting range
sudo tee /etc/docker/daemon.json <<'EOF'
{
  "bip": "192.168.200.1/24",
  "default-address-pools": [
    {
      "base": "192.168.201.0/24",
      "size": 28
    }
  ]
}
EOF

# Restart Docker — WARNING: this stops all running containers
sudo systemctl restart docker

# Verify the new bridge address
docker network inspect bridge | grep Subnet
# "Subnet": "192.168.200.0/24"   ← no longer conflicts with VPN

# Test: spin up a container and verify it gets an IP from the new range
docker run --rm alpine ip addr show eth0
# inet 192.168.200.2/24 ...

# Test: from inside the container, reach a corporate host
docker run --rm alpine ping -c 2 172.16.10.5
# Should now route via VPN instead of Docker bridge
```

---

### Example 4: Generating a Subnet Plan for a Three-Tier, Three-AZ VPC in Terraform

You need to programmatically compute subnet CIDRs for a new VPC without hardcoding every CIDR. Use Terraform's `cidrsubnet` function to derive subnets from the parent VPC CIDR.

```hcl
# variables.tf
variable "vpc_cidr" {
  description = "Parent VPC CIDR block"
  default     = "10.10.0.0/16"
}

variable "azs" {
  description = "Availability zones to deploy into"
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}
```

```hcl
# main.tf
locals {
  # cidrsubnet(prefix, newbits, netnum)
  # newbits: how many bits to add to the prefix length
  # netnum:  which subnet number (0-indexed)

  # Public subnets: /24 each (newbits=8 from /16, nets 0-2)
  public_cidrs = [for i, az in var.azs :
    cidrsubnet(var.vpc_cidr, 8, i)
    # i=0 → 10.10.0.0/24, i=1 → 10.10.1.0/24, i=2 → 10.10.2.0/24
  ]

  # Private subnets: /20 each (newbits=4 from /16, nets 4-6)
  # Start at netnum=4 to leave a gap from public subnets
  private_cidrs = [for i, az in var.azs :
    cidrsubnet(var.vpc_cidr, 4, i + 4)
    # i=0 → 10.10.64.0/20, i=1 → 10.10.80.0/20, i=2 → 10.10.96.0/20
  ]

  # Data subnets: /24 each (newbits=8, nets 48-50)
  data_cidrs = [for i, az in var.azs :
    cidrsubnet(var.vpc_cidr, 8, i + 48)
    # i=0 → 10.10.48.0/24, i=1 → 10.10.49.0/24, i=2 → 10.10.50.0/24
  ]
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "main" }
}

resource "aws_subnet" "public" {
  count             = length(var.azs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = local.public_cidrs[count.index]
  availability_zone = var.azs[count.index]
  map_public_ip_on_launch = true
  tags = { Name = "public-${var.azs[count.index]}", Tier = "public" }
}

resource "aws_subnet" "private" {
  count             = length(var.azs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = local.private_cidrs[count.index]
  availability_zone = var.azs[count.index]
  tags = {
    Name                              = "private-${var.azs[count.index]}"
    Tier                              = "private"
    "kubernetes.io/role/internal-elb" = "1"
  }
}

resource "aws_subnet" "data" {
  count             = length(var.azs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = local.data_cidrs[count.index]
  availability_zone = var.azs[count.index]
  tags = { Name = "data-${var.azs[count.index]}", Tier = "data" }
}

# Verify the computed CIDRs before applying
output "public_cidrs"  { value = local.public_cidrs }
output "private_cidrs" { value = local.private_cidrs }
output "data_cidrs"    { value = local.data_cidrs }
```

```bash
# Preview the computed CIDRs without deploying anything
terraform init
terraform plan -target=output.public_cidrs -target=output.private_cidrs -target=output.data_cidrs
# Changes to Outputs:
#   + data_cidrs    = ["10.10.48.0/24", "10.10.49.0/24", "10.10.50.0/24"]
#   + private_cidrs = ["10.10.64.0/20", "10.10.80.0/20", "10.10.96.0/20"]
#   + public_cidrs  = ["10.10.0.0/24",  "10.10.1.0/24",  "10.10.2.0/24"]
```

---

## Практические задания

### Exercise 1: Binary Subnet Math Without a Calculator

Given the following, answer all questions by hand, then verify with `ipcalc` or Python:

1. What is the network address of `10.4.67.200/26`?
2. What is the broadcast address?
3. Is `10.4.67.250` in the same subnet as `10.4.67.200/26`?
4. Is `10.4.67.128` the correct network address for a `/26`? Why or why not?

**Procedure:**
- Convert `67` and `200` to binary
- Apply the `/26` mask (`255.255.255.192`, last octet `11000000`)
- AND to find the network address
- Set all host bits to 1 for the broadcast address

```bash
# Verify your answers
ipcalc 10.4.67.200/26
python3 -c "
import ipaddress
net = ipaddress.ip_network('10.4.67.200/26', strict=False)
print('Network:', net.network_address)
print('Broadcast:', net.broadcast_address)
print('10.4.67.250 in subnet:', ipaddress.ip_address('10.4.67.250') in net)
"
```

---

### Exercise 2: Design a Subnet Layout Under Constraints

You are given `172.20.0.0/22` (1,024 addresses) and must allocate subnets for:

- 3 public subnets (one per AZ) — each needs ~20 usable IPs for load balancers
- 3 private subnets (one per AZ) — each needs ~100 usable IPs for app servers
- 1 management subnet — needs ~10 usable IPs
- Reserve at least 25% of the block for future use

Write out your allocation table (subnet name, CIDR, first host, last host, usable IPs). Then verify that:
1. No two CIDRs overlap
2. All CIDRs fit within `172.20.0.0/22`
3. The reserved space is contiguous and documented

```python
# Starter: enumerate possible subnets from the parent
import ipaddress
parent = ipaddress.ip_network("172.20.0.0/22")
# List all /27 subnets within the parent to see what you have to work with
for s in parent.subnets(new_prefix=27):
    print(s, "hosts:", s.num_addresses - 2)
```

---

### Exercise 3: Diagnose a Routing Problem

Set up two network namespaces on a Linux host to simulate two hosts on different subnets, then diagnose why they can't communicate and fix it.

```bash
# Create two namespaces simulating hosts on different /24 subnets
sudo ip netns add host-a
sudo ip netns add host-b

# Create veth pairs and assign IPs
sudo ip link add veth-a type veth peer name veth-b
sudo ip link set veth-a netns host-a
sudo ip link set veth-b netns host-b

# Assign IPs — same /16 supernet, different /24 subnets
sudo ip netns exec host-a ip addr add 10.1.1.10/24 dev veth-a
sudo ip netns exec host-b ip addr add 10.1.2.10/24 dev veth-b
sudo ip netns exec host-a ip link set veth-a up
sudo ip netns exec host-b ip link set veth-b up

# Try to ping — this will fail
sudo ip netns exec host-a ping -c 2 10.1.2.10
# Why does it fail? What does 'ip route show' tell you inside host-a?
sudo ip netns exec host-a ip route show

# Your task: add the correct static routes to make communication work
# Hint: each host needs a route to the other's /24 via the peer veth IP
# Fix it, verify ping succeeds, then explain why this mirrors how
# a router enables inter-subnet communication in a VPC

# Cleanup
sudo ip netns del host-a
sudo ip netns del host-b
```

---

### Exercise 4: Audit and Resize a Kubernetes Cluster's IP Allocation

You have a kubeadm cluster with the following configuration. Answer the questions and implement the check as a shell script.

Given:
- Node subnet: `192.168.10.0/24`
- Pod CIDR: `10.244.0.0/16` (Flannel)
- Service CIDR: `10.96.0.0/12`
- Current nodes: 5, max planned nodes: 20
- Flannel allocates one `/24` per node from the pod CIDR

1. How many `/24` pod subnets can Flannel allocate from `10.244.0.0/16`?
2. Is the pod CIDR large enough for 20 nodes?
3. Does the service CIDR `10.96.0.0/12` overlap with the pod CIDR `10.244.0.0/16`? Show your work.
4. The node subnet is `192.168.10.0/24` — how many nodes can it support (accounting for 2 reserved addresses)?

Write a Python script that takes three CIDRs as arguments (node subnet, pod CIDR, service CIDR) and outputs:
- Whether any two overlap
- Maximum node count from the node subnet
- Maximum per-node pod subnets allocatable from the pod CIDR (assuming `/24` per node)

```bash
python3 audit_cidrs.py 192.168.10.0/24 10.244.0.0/16 10.96.0.0/12
# Expected output:
# Overlap check: no overlaps detected
# Max nodes (node subnet): 254
# Max pod subnets (/24 per node from pod CIDR): 256
# Sufficient for 20 planned nodes: yes
```

---

### Быстрая проверка

1. Calculate the number of usable host addresses in a `/20` subnet.

   ```python
   print(2 ** (32 - 20) - 2)
   ```

   ```expected_output
   4094
   ```

hint: Think about how the subnet mask's prefix length determines how many bits are left for host addresses.
hint: With a /20 prefix, calculate 2 raised to the power of (32 minus 20), then subtract 2 to account for the network and broadcast addresses.

2. Check whether two CIDRs overlap — the first step in validating a VPC or Kubernetes network plan.

   ```python
   import ipaddress; a=ipaddress.ip_network('10.244.0.0/16'); b=ipaddress.ip_network('10.96.0.0/12'); print('overlap' if a.overlaps(b) else 'no overlap')
   ```

   ```expected_output
   no overlap
   ```
hint: Think about how Python or a CLI tool can parse and compare CIDR ranges to determine if their address spaces intersect.
hint: Use Python's built-in ipaddress module and call network_a.overlaps(network_b) on two IPv4Network objects constructed from your CIDR strings.
