---
title: SSH и управление ключами
module: linux
duration_min: 15
difficulty: beginner
tags: [ssh, scp, keys, authorized_keys, ssh-keygen, agent]
exercises: 3
---

## Обзор

SSH (Secure Shell) — стандартный протокол защищённого удалённого доступа к Linux-системам. В DevOps он используется постоянно: для подключения к серверам, выполнения удалённых команд, копирования файлов и туннелирования трафика. SSH лежит в основе множества инструментов: Ansible использует его как транспорт, CI/CD-пайплайны аутентифицируются с помощью SSH-ключей в репозиториях и целевых системах развёртывания, а облачные платформы и реестры контейнеров применяют ключевую аутентификацию для автоматизации. Даже `git push` в GitHub обычно работает через SSH. Неправильно настроенный ключ или отсутствующая запись в `known_hosts` способны незаметно сломать пайплайн развёртывания посреди ночи.

В основе SSH лежит асимметричная криптография: пара математически связанных ключей, при которой данные, зашифрованные одним ключом, могут быть расшифрованы другим. Приватный ключ хранится в секрете, а публичный можно свободно распространять. Сервер никогда не получает приватный ключ — клиент лишь доказывает, что владеет им. Это безопаснее паролей: учётные данные не передаются по сети, перебор ключа практически нереализуем, а доступ можно отозвать на конкретном сервере, не меняя общий пароль повсюду.

В цепочке DevOps SSH находится на уровне доступа к инфраструктуре. Выше располагаются управление конфигурацией (Ansible), управление секретами (Vault) и оркестрация (Kubernetes), ниже — сеть и операционная система. Прежде чем работать с этими уровнями, нужно освоить безопасное хранение ключей, SSH-agent, проверку подлинности хостов и укрепление конфигурации SSH-сервера.

---

## Основные понятия

### Как работает аутентификация по ключу

Установление SSH-соединения состоит из четырёх шагов. Понимание этих шагов помогает диагностировать ошибки, а не гадать об их причине.

1. **TCP-соединение** — SSH-клиент подключается к порту 22 (или заданному порту) сервера. Стороны согласуют версию протокола и алгоритмы симметричного шифрования для сессии.
2. **Проверка хоста** — сервер предъявляет *host key* (собственную пару ключей, хранящуюся в `/etc/ssh/ssh_host_*`). Клиент ищет соответствующий отпечаток в `~/.ssh/known_hosts`. Если записи нет, он предложит подтвердить ключ. Если запись есть, но отпечаток не совпадает, SSH прервёт соединение — это защита от атаки посредника (MITM).
3. **Аутентификация пользователя** — сервер ищет ваш публичный ключ в `~/.ssh/authorized_keys`. Он создаёт случайный challenge, шифрует его публичным ключом и отправляет клиенту. Клиент расшифровывает challenge приватным ключом, объединяет его с идентификатором сессии, вычисляет хеш и отправляет результат обратно.
4. **Начало сессии** — сервер проверяет хеш. Если он верен, аутентификация завершена. Пароль и приватный ключ по сети не передаются.

```
Client                          Server
  |                               |
  |------- TCP SYN -------------> |
  |<------ Server Host Key ------ |   ← you verify this against known_hosts
  |                               |
  |------- Public Key ID -------> |   ← "I want to auth with this key"
  |<------ Encrypted Challenge -- |   ← encrypted with YOUR public key
  |                               |
  |------- Signed Response -----> |   ← proves you hold the private key
  |<------ Auth Success --------- |
```

**Важный нюанс host key:** после пересоздания сервера (новый AMI или VM) его host key меняется. SSH откажется подключаться и покажет предупреждение `REMOTE HOST IDENTIFICATION HAS CHANGED`. Если вы подтвердили, что ключ действительно изменился ожидаемым образом, удалите устаревшую запись:

```bash
ssh-keygen -R hostname          # removes all entries for that hostname from known_hosts
ssh-keygen -R 203.0.113.50      # also works with IP addresses
```

Подключитесь повторно и подтвердите новый отпечаток. **Никогда** не отключайте `StrictHostKeyChecking` глобально: это полностью убирает защиту от MITM. Если в автоматизации невозможно заранее заполнить `known_hosts`, используйте `ssh-keyscan`, чтобы получить и записать отпечатки до подключения, а не отключайте проверку.

```bash
# Заранее заполнить known_hosts в CI-конвейере
ssh-keyscan -H 203.0.113.50 >> ~/.ssh/known_hosts

# Хешировать имя хоста, чтобы не раскрывать топологию инфраструктуры
# -H хеширует записи: IP и имя хоста нельзя прочитать напрямую
ssh-keyscan -H bastion.example.com >> ~/.ssh/known_hosts
```

---

### Типы ключей

| Тип | Флаг | Размер ключа | Безопасность | Когда использовать |
|------|------|----------|----------|-------------|
| **Ed25519** | `-t ed25519` | 256 бит (фиксированный) | Отличная | По умолчанию для современных систем |
| **RSA** | `-t rsa -b 4096` | 4096 бит | Хорошая | Устаревшие системы, среды с требованиями FIPS |
| **ECDSA** | `-t ecdsa -b 521` | 256–521 бит | Хорошая | Обычно не нужен; Ed25519 предпочтительнее |
| **DSA** | `-t dsa` | 1024 бита (фиксированный) | Небезопасный | Не использовать — устарел с OpenSSH 7.0 |

**Ed25519 — предпочтительный выбор** для систем с OpenSSH 6.5 и новее (выпущен в 2014 году). Ключи короче, вычисления быстрее, а реализация имеет меньшую поверхность атаки, чем RSA. RSA длиной 4096 бит допустим для GitHub Enterprise, старого сетевого оборудования или сред с требованиями FIPS, где кривые Ed25519 ещё не разрешены.

```bash
# Создать ключ Ed25519 — рекомендуемый вариант
ssh-keygen -t ed25519 -C "user@workstation"

# Создать RSA-ключ длиной 4096 бит для совместимости со старыми системами
ssh-keygen -t rsa -b 4096 -C "user@workstation"

# Создать отдельный ключ для конкретной задачи (не перезаписывайте ключ по умолчанию)
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_github -C "github-personal"

# Изменить парольную фразу существующего ключа (сам ключ не меняется)
ssh-keygen -p -f ~/.ssh/id_ed25519

# Показать отпечаток ключа — полезно для проверки перед тем, как ему доверять
ssh-keygen -lf ~/.ssh/id_ed25519.pub
# 256 SHA256:abc123xyz... user@workstation (ED25519)
```

**Размер ключа и парольная фраза:** ключ RSA длиной 4096 бит без парольной фразы менее защищён, чем ключ Ed25519 длиной 256 бит с надёжной парольной фразой. Она шифрует файл приватного ключа на диске с помощью AES-256. Без неё любой, кто прочитает файл, сможет выдавать себя за вас на всех серверах, где этот ключ разрешён. Парольная фраза не покидает вашу машину — она только разблокирует локальный файл.

**Рекомендация для комментария (`-C`):** используйте `user@machine` или описание назначения, например `ci-deploy-prod`. Комментарий отображается в `authorized_keys` на каждом сервере, куда добавлен ключ, и упрощает аудит и отзыв доступа. Если у вас 40 серверов и нужно заменить ключ, по комментарию можно найти все записи, которые требуется обновить.

---

### Файлы ключей и права доступа

SSH строго проверяет права доступа к файлам. Неверные права приводят к отказу аутентификации, иногда без очевидного объяснения. Это частая ошибка новичков и популярная тема на собеседованиях.

```
~/.ssh/
├── id_ed25519              # private key         — chmod 600
├── id_ed25519.pub          # public key          — chmod 644
├── id_ed25519_github       # named private key   — chmod 600
├── id_ed25519_github.pub   # named public key    — chmod 644
├── authorized_keys         # server-side: who may log in — chmod 600
├── known_hosts             # trusted server fingerprints — chmod 644
└── config                  # client config       — chmod 600
```

Сам каталог `~/.ssh/` должен иметь права `chmod 700`. Если группа или остальные пользователи могут изменять его содержимое, SSH откажется использовать находящиеся внутри ключи: это считается признаком возможной подмены файлов.

```bash
# Исправить права доступа после копирования ключей между машинами
chmod 700 ~/.ssh
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub
chmod 600 ~/.ssh/authorized_keys
chmod 600 ~/.ssh/config

# Проверить командой ls -la
ls -la ~/.ssh/
```

**`authorized_keys` на сервере:** здесь хранятся публичные ключи пользователей, которым разрешён доступ. Один ключ на строку. Перед ключом можно указать параметры, ограничивающие способы его использования — это особенно полезно для автоматизации:

```
# ~/.ssh/authorized_keys на сервере

# Стандартная запись без ограничений
ssh-ed25519 AAAA...base64... user@workstation

# Ключ развёртывания: разрешён только один скрипт, интерактивный терминал запрещён
command="/usr/local/bin/deploy.sh",no-pty,no-agent-forwarding,no-x11-forwarding ssh-ed25519 AAAA...base64... ci-deploy-key

# Ограничить определённым диапазоном исходных IP; из остальных сетей доступ запрещён
from="203.0.113.0/24" ssh-ed25519 AAAA...base64... restricted-user

# Ограничить одной командой и одним IP — дополнительная защита для чувствительной автоматизации
from="10.0.0.5",command="/usr/bin/rsync --server -vlogDtpre.iLsfxC . /var/www/",no-pty ssh-ed25519 AAAA...base64... rsync-deploy
```

**Безопасное добавление публичного ключа на удалённый сервер:**

```bash
# ssh-copy-id автоматически задаёт права; предпочтительнее ручного копирования ключа
ssh-copy-id -i ~/.ssh/id_ed25519.pub user@server

# Если сервер использует нестандартный порт
ssh-copy-id -i ~/.ssh/id_ed25519.pub -p 2222 user@server

# Ручной вариант, если ssh-copy-id недоступен
cat ~/.ssh/id_ed25519.pub | ssh user@server \
  "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

**Важен и владелец файлов:** если `~/.ssh/authorized_keys` принадлежит root, хотя используется обычной учётной записью (или наоборот), SSH полностью проигнорирует файл. После копирования ключей от имени другого пользователя, например через `sudo`, проверьте владельца командой `ls -la ~/.ssh/` и при необходимости исправьте его через `chown`.

---

### Конфигурационный файл SSH

`~/.ssh/config` — один из самых полезных файлов в арсенале DevOps-инженера. Команды `ssh`, `scp`, `rsync` и `git` читают его автоматически. Хорошо настроенный файл избавляет от длинных команд, документирует топологию инфраструктуры и делает подключения через bastion прозрачными.

```
# ~/.ssh/config

# ── Глобальные значения по умолчанию ───────────────────────────────────────
Host *
    ServerAliveInterval 60        # keepalive every 60s — prevents idle connection drops
    ServerAliveCountMax 3         # drop connection after 3 missed keepalives
    AddKeysToAgent yes            # auto-add to agent on first use
    IdentitiesOnly yes            # only offer keys listed in this file; don't dump entire agent

# ── Production-веб-сервер ───────────────────────────────────────────────────
Host prod-web
    HostName 203.0.113.50
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519_prod
    Port 22

# ── Bastion-хост AWS ────────────────────────────────────────────────────────
Host bastion
    HostName 203.0.113.10
    User ec2-user
    IdentityFile ~/.ssh/id_ed25519_aws

# ── Приватная БД, доступная только через bastion ────────────────────────────
Host prod-db
    HostName 10.0.1.20
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519_aws
    ProxyJump bastion             # SSH opens bastion first, then forwards to this host

# ── GitHub (полезно при работе с несколькими аккаунтами) ────────────────────
Host github-work
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_github_work

Host github-personal
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_github_personal
```

С такой конфигурацией:
- `ssh prod-web` — подключение с нужным пользователем, ключом и адресом хоста
- `ssh prod-db` — автоматическое подключение через bastion
- `git clone github-work:myorg/repo.git` — использует рабочий ключ без дополнительных флагов

**Важный нюанс `IdentitiesOnly yes`:** без этой директивы SSH по очереди предлагает все ключи из agent и все стандартные файлы ключей (`id_rsa`, `id_ed25519` и другие). Многие серверы закрывают соединение после нескольких неудачных попыток аутентификации (`MaxAuthTries 3` — распространённая настройка усиления безопасности). Если загружено пять и более ключей, сервер может заблокировать соединение ещё до проверки нужного ключа. Установите `IdentitiesOnly yes` глобально и задавайте `IdentityFile` для каждого хоста.

**Порядок чтения конфигурации:** SSH сначала читает `~/.ssh/config`, затем `/etc/ssh/ssh_config`. Для каждой директивы действует первое совпавшее правило `Host`, поэтому более конкретные записи нужно располагать перед общими блоками `Host *`. Это работает не так, как многие ожидают.

---

### SSH-agent

SSH-agent — фоновый процесс, который хранит расшифрованные приватные ключи в памяти. Парольную фразу нужно ввести один раз при добавлении ключа; после этого инструменты SSH — `ssh`, `scp`, `git`, Ansible и Terraform — выполняют аутентификацию без повторного запроса.

```bash
# Запустить agent (графические окружения обычно запускают его при входе)
eval "$(ssh-agent -s)"
# Вывод: Agent pid 12345

# Добавить основной ключ — парольная фраза запрашивается один раз
ssh-add ~/.ssh/id_ed25519

# Добавить с ограничением времени — удалить автоматически через 4 часа
# Полезно для production-ключей, которые не должны оставаться загруженными весь день
ssh-add -t 4h ~/.ssh/id_ed25519_prod

# Показать ключи, загруженные в agent
ssh-add -l
# 256 SHA256:abc123... user@workstation (ED25519)
# 3072 SHA256:def456... user@workstation (RSA)

# Показать полный публичный ключ из agent (например, для добавления в authorized_keys)
ssh-add -L

# Удалить один ключ из agent
ssh-add -d ~/.ssh/id_ed25519_github

# Удалить все ключи
ssh-add -D
```

**Перенаправление agent и ProxyJump:** при подключении к bastion с последующим доступом к внутреннему хосту есть два варианта. Важно понимать различия — это частая тема на собеседованиях.

| Возможность | `ProxyJump` | `ForwardAgent` |
|---------|-------------|----------------|
| Приватный ключ остаётся на вашей машине | ✅ | ✅ |
| Сокет agent доступен на промежуточном хосте | ❌ | ✅ ← security risk |
| Root на промежуточном хосте может злоупотребить agent | ❌ | ✅ |
| Работает без shell на промежуточном хосте | ✅ (TCP only) | ❌ |
| Требует явного доверия промежуточному хосту | No | Yes |
| Рекомендуемый вариант по умолчанию | ✅ | Only for fully trusted hosts |

**Предупреждение о безопасности `ForwardAgent`:** при `ForwardAgent yes` пользователь с правами root на bastion может подключиться к Unix-сокету agent (`SSH_AUTH_SOCK`) и аутентифицироваться от вашего имени на всех серверах, где разрешён ваш ключ, пока действует сессия. По умолчанию используйте `ProxyJump`. `ForwardAgent` оставляйте только для полностью доверенных хостов.

```bash
# Перенаправление agent — только для отдельной сессии (не задавайте глобально)
ssh -A user@bastion

# ProxyJump — предпочтительный вариант; ключ не покидает вашу машину
ssh -J ec2-user@bastion ubuntu@10.0.1.20

# Многоступенчатый ProxyJump
ssh -J user@jump1,user@jump2 user@final-destination
```

**Переменная окружения `SSH_AUTH_SOCK`** указывает на Unix-сокет SSH-agent. При использовании `sudo` или переключении пользователя переменная часто не сохраняется. Поэтому `sudo ansible-playbook` иногда не находит ключи, хотя agent запущен. Передайте переменную явно: `sudo SSH_AUTH_SOCK=$SSH_AUTH_SOCK ansible-playbook ...` или добавьте `Defaults env_keep += "SSH_AUTH_SOCK"` в `/etc/sudoers`.

---

### Перенаправление портов и туннелирование

SSH умеет перенаправлять TCP-порты между локальной машиной и удалёнными сетями. Так можно обращаться к приватным сервисам (базам данных, внутренним дашбордам и административным интерфейсам), не открывая их в интернет.

| Тип туннеля | Флаг | Направление | Типичный сценарий |
|-------------|------|-----------|-------------|
| **Локальный** | `-L` | Удалённый сервис → локальный порт | Доступ к приватной БД с ноутбука |
| **Удалённый** | `-R` | Локальный сервис → удалённый порт | Открыть локальный dev-сервер для удалённой машины |
| **Динамический** | `-D` | SOCKS5-прокси на локальном порту | Направить трафик браузера через сервер |

```bash
# ── Локальное перенаправление ─────────────────────────────────────────────────────────
# Доступ к RDS (порт 5432) в приватной VPC через localhost:5433
# Синтаксис: -L локальный_порт:целевой_хост:целевой_порт jump_host
ssh -L 5433:my-rds.cluster-xyz.us-east-1.rds.amazonaws.com:5432 ec2-user@bastion
# Теперь подключите клиент БД к localhost:5433

# ── Удалённое перенаправление ────────────────────────────────────────────────────────
# Открыть локальный dev-сервер (порт 3000) на порту 8080 удалённого сервера
# Полезно для совместной работы и проверки webhook от GitHub
ssh -R 8080:localhost:3000 user@remote-server

# ── Динамический режим (SOCKS5) ─────────────────────────────────────────────────────────
# Создать SOCKS5-прокси — настройте браузер на localhost:1080
ssh -D 1080 user@server

# ── Постоянный туннель в фоне ─────────────────────────────────────────────
# -N: не запускать shell; -f: перейти в фон
ssh -fN -L 5432:my-rds.cluster-xyz.us-east-1.rds.amazonaws.com:5432 ec2-user@bastion

# Найти и завершить фоновый туннель после использования
ps aux | grep ssh
kill <pid>
```

**`-N` и интерактивная сессия:** без `-N` SSH помимо туннеля открывает shell на промежуточном хосте. С `-N` SSH только подключается и настраивает перенаправление порта — без приглашения shell и лишней нагрузки на удалённой стороне. Для туннелирования используйте `-N`.

**`GatewayPorts` для удалённого перенаправления:** по умолчанию `-R` привязывается только к `127.0.0.1` удалённого сервера, поэтому порт доступен лишь процессам на этом хосте. Чтобы слушать `0.0.0.0` (все интерфейсы) и принимать внешние подключения, в `/etc/ssh/sshd_config` нужна директива `GatewayPorts yes`. По соображениям безопасности она отключена по умолчанию.

---

### Усиление безопасности SSH-сервера

Стандартная установка `sshd` работает, но не усилена с точки зрения безопасности. Изменение настроек в `/etc/ssh/sshd_config` — обычная практика для production-хостов. После правок всегда проверяйте конфигурацию перед перезагрузкой службы: опечатка может лишить вас доступа.

```bash
# ── /etc/ssh/sshd_config — усиление безопасности production ───────────────────────────

# Полностью отключить вход по паролю — только ключи
PasswordAuthentication no
ChallengeResponseAuthentication no

# Запретить вход root — использовать именованного пользователя и sudo
PermitRootLogin no

# Ограничить список пользователей, которым разрешён вход
AllowUsers ubuntu deploy-user

# Уменьшить время ожидания неаутентифицированного подключения (по умолчанию 120 с)
LoginGraceTime 30

# Ограничить число попыток аутентификации в одном подключении
MaxAuthTries 3

# Отключить неиспользуемые функции, увеличивающие поверхность атаки
X11Forwarding no
AllowAgentForwarding no        # при необходимости включать отдельно для пользователя
AllowTcpForwarding no          # re-enable if you use tunnels intentionally

# Слушать только заданный интерфейс, если у хоста несколько сетевых интерфейсов
ListenAddress 0.0.0.0

# Использовать только современные алгоритмы обмена ключами и шифрования
KexAlgorithms curve25519-sha256,diffie-hellman-group16-sha512
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com
MACs hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com
```

```bash
# Проверить синтаксис sshd_config перед перезагрузкой — это обнаружит опечатки, которые могут лишить вас доступа
sshd -t

# Перезагрузить конфигурацию без разрыва существующих сессий
systemctl reload sshd

# Проверить, что после перезагрузки демон работает
systemctl status sshd
```

**Как не потерять доступ:** всегда держите открытой одну SSH-сессию, пока проверяете новый `sshd_config`. Если перезагрузка завершится ошибкой или конфигурация окажется неверной, существующая сессия останется активной и позволит исправить проблему. Сначала откройте новое соединение и убедитесь, что доступ работает, и только потом закрывайте старую сессию — это важное правило production-эксплуатации.

**Порт 22 и нестандартный порт:** перенос SSH на другой порт, например 2222, уменьшает количество шума от автоматических сканеров, но не обеспечивает реальную защиту — сканирование обнаружит порт за секунды. Для атакующего это небольшое неудобство, а для команды — постоянное. Вместо смены порта ради сокрытия используйте `AllowUsers`, вход только по ключам и firewall.

---

### Копирование файлов через SCP и Rsync по SSH

Оба инструмента используют SSH в качестве транспорта и учитывают алиасы из `~/.ssh/config`.

```bash
# ── scp — simple file copy ────────────────────────────────────────────────────
# Локальная машина → удалённая
scp ./app.tar.gz ubuntu@prod-web:/tmp/

# Удалённая машина → локальная
scp ubuntu@prod-web:/var/log/app.log ./

# Рекурсивное копирование каталога
scp -r ./dist/ ubuntu@prod-web:/var/www/html/

# Использовать нестандартный ключ
scp -i ~/.ssh/id_ed25519_prod ./config.yml ubuntu@prod-web:/etc/app/

# ── rsync — efficient incremental sync ───────────────────────────────────────
# -a: режим архива (сохраняет права, временные метки и символические ссылки)
# -v: подробный вывод   -z: сжатие при передаче   --delete: удалять файлы, удалённые локально
rsync -avz --delete ./dist/ ubuntu@prod-web:/var/www/html/

# rsync через нестандартный SSH-порт
rsync -avz -e "ssh -p 2222" ./dist/ ubuntu@prod-web:/var/www/html/

# Сначала пробный запуск — показывает изменения, не применяя их
rsync -avz --dry-run --delete ./dist/ ubuntu@prod-web:/var/www/html/

# Используйте алиас из ssh config — rsync прочитает его автоматически
rsync -avz ./dist/ prod-web:/var/www/html/
```

**scp и rsync:** используйте `scp` для разовой передачи отдельных файлов. Для каталогов, развёртываний и повторяющихся передач выбирайте `rsync`: после первой передачи он отправляет только изменившиеся данные. На медленном канале или при большом коде инкрементальное обновление через `rsync` может быть в 100 раз быстрее `scp`.

**Устаревший протокол `scp`:** начиная с OpenSSH 9.0 по умолчанию используется SFTP вместо старого протокола scp. Команда продолжает работать, но при подключении к старым серверам могут появляться предупреждения. Для скриптовой передачи предпочтительнее `rsync` или `sftp`.

---

## Примеры

### Пример 1: настройка доступа к новому серверу по ключу с нуля

**Сценарий:** вы только что запустили новый экземпляр Ubuntu EC2. AWS выдал файл `.pem`. Нужно перейти на стандартную схему с Ed25519 и отключить парольную аутентификацию.

```bash
# Шаг 1 — подключиться с PEM-ключом AWS (формат RSA)
chmod 400 ~/Downloads/my-instance.pem
ssh -i ~/Downloads/my-instance.pem ubuntu@203.0.113.50

# Шаг 2 — добавить публичный ключ Ed25519 на сервер
# (выполните на ноутбуке, а не на сервере)
ssh-copy-id -i ~/.ssh/id_ed25519.pub -o "IdentityFile=~/Downloads/my-instance.pem" ubuntu@203.0.113.50

# Шаг 3 — проверить новый ключ ДО отключения пароля и PEM-доступа
ssh -i ~/.ssh/id_ed25519 ubuntu@203.0.113.50
# Убедиться, что открылась оболочка

# Шаг 4 — усилить настройки sshd на сервере
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sshd -t && sudo systemctl reload sshd

# Шаг 5 — добавить настройки в локальный ~/.ssh/config
cat >> ~/.ssh/config <<'EOF'

Host my-ec2
    HostName 203.0.113.50
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519
EOF

# Шаг 6 — проверить работу алиаса
ssh my-ec2
```

**Проверка:** `ssh my-ec2` подключается без запроса пароля. Команда `ssh -o PasswordAuthentication=yes ubuntu@203.0.113.50` должна вернуть `Permission denied`.

---

### Пример 2: доступ к приватной базе данных через bastion

**Сценарий:** база PostgreSQL находится в приватной подсети (`10.0.1.50:5432`) и не имеет публичного IP. Единственный путь доступа — bastion с адресом `203.0.113.10`.

```bash
# Step 1 — Add both hosts to ~/.ssh/config
cat >> ~/.ssh/config <<'EOF'

Host bastion-prod
    HostName 203.0.113.10
    User ec2-user
    IdentityFile ~/.ssh/id_ed25519_aws
    IdentitiesOnly yes

Host prod-db
    HostName 10.0.1.50
    User ubuntu
    IdentityFile ~/.ssh/id_ed25519_aws
    IdentitiesOnly yes
    ProxyJump bastion-prod        # transparent hop through bastion
EOF

# Step 2 — Verify SSH connectivity to the DB (no special tunnel needed for shells)
ssh prod-db
# You should get a shell on 10.0.1.50 — SSH handled the bastion hop silently

# Step 3 — Open a local port tunnel to reach the DB with psql or a GUI client
# Forwards localhost:5433 → 10.0.1.50:5432 through bastion, runs in background
ssh -fN -L 5433:10.0.1.50:5432 bastion-prod

# Step 4 — Connect with psql
psql -h localhost -p 5433 -U appuser -d mydb

# Step 5 — Verify the tunnel is active
ss -tlnp | grep 5433
# LISTEN  0  128  127.0.0.1:5433  ...

# Kill the tunnel when done
pkill -f "ssh.*5433"
```

**Почему здесь `ProxyJump`, а не `ForwardAgent`:** bastion никогда не получает ваш приватный ключ. SSH на ноутбуке открывает TCP-канал к `10.0.1.50` через bastion, а затем выполняет полную аутентификацию ключом непосредственно с целевым узлом. Bastion служит лишь каналом передачи.

---

### Пример 3: развёртывание веб-приложения через CI/CD с ограниченным ключом

**Сценарий:** pipeline GitHub Actions должен передать собранные файлы на production-сервер через `rsync`. Ключ должен позволять запускать только скрипт развёртывания и ничего больше.

```bash
# Step 1 — Generate a dedicated deploy key with no passphrase
# (CI runners can't type passphrases; use the agent or a keyless key scoped tightly)
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_ci_deploy -N "" -C "ci-deploy-prod"
# -N "": empty passphrase — acceptable because the key is locked down server-side

# Step 2 — On the production server, add the key with command restriction
# Only allows running /usr/local/bin/deploy.sh — nothing else
echo 'command="/usr/local/bin/deploy.sh",no-pty,no-agent-forwarding,no-x11-forwarding,no-port-forwarding ssh-ed25519 AAAA...pubkey... ci-deploy-prod' \
  >> ~/.ssh/authorized_keys

# Step 3 — Write the deploy script on the server
sudo tee /usr/local/bin/deploy.sh > /dev/null <<'SCRIPT'
#!/bin/bash
set -euo pipefail
rsync -a --delete /tmp/deploy_staging/ /var/www/html/
systemctl reload nginx
echo "Deploy complete: $(date)"
SCRIPT
sudo chmod +x /usr/local/bin/deploy.sh

# Step 4 — Store the private key in GitHub Actions secrets as CI_DEPLOY_KEY

# Step 5 — GitHub Actions workflow
# .github/workflows/deploy.yml
```

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build assets
        run: npm ci && npm run build

      - name: Install SSH key
        run: |
          install -m 600 -D /dev/null ~/.ssh/id_ed25519_deploy
          echo "${{ secrets.CI_DEPLOY_KEY }}" > ~/.ssh/id_ed25519_deploy
          # Pre-populate known_hosts — never use StrictHostKeyChecking=no
          ssh-keyscan -H 203.0.113.50 >> ~/.ssh/known_hosts

      - name: Copy assets to server
        run: |
          rsync -az ./dist/ ubuntu@203.0.113.50:/tmp/deploy_staging/

      - name: Trigger deploy script
        run: |
          # The server ignores this argument — it runs deploy.sh regardless
          # but sending *something* keeps the command readable in logs
          ssh -i ~/.ssh/id_ed25519_deploy ubuntu@203.0.113.50 deploy

      - name: Clean up key
        if: always()
        run: rm -f ~/.ssh/id_ed25519_deploy
```

**Проверка:** при ручном подключении deploy-ключом должен выполниться скрипт и завершиться без shell-приглашения и возможности запускать другие команды. Попробуйте `ssh -i ~/.ssh/id_ed25519_ci_deploy ubuntu@203.0.113.50 "cat /etc/passwd"`: сервер проигнорирует переданную команду и вместо неё запустит `deploy.sh`.

---

### Пример 4: аудит и ротация ключей на нескольких серверах

**Сценарий:** сотрудник покинул команду. Нужно удалить его ключ со всех серверов и убедиться, что доступ отозван.

```bash
# Step 1 — Identify the key to remove (get the fingerprint or comment)
# If you have their public key file:
ssh-keygen -lf /tmp/departed-user.pub
# 256 SHA256:xK9mN2... alice@laptop (ED25519)

# Step 2 — On each server, remove the matching line from authorized_keys
# Match by comment (last field) — safe because it's human-readable
ssh prod-web "sed -i '/alice@laptop/d' ~/.ssh/authorized_keys"
ssh prod-db  "sed -i '/alice@laptop/d' ~/.ssh/authorized_keys"

# Step 3 — Verify the key is gone
ssh prod-web "grep -c 'alice@laptop' ~/.ssh/authorized_keys || echo 'Key not found — clean'"

# Step 4 — Check for the key in other locations (some automation puts keys in /root)
ssh prod-web "sudo grep -r 'alice@laptop' /home /root /etc/ssh/ 2>/dev/null"

# Step 5 — Audit who currently has access (list all authorized keys on a host)
ssh prod-web "cat ~/.ssh/authorized_keys"

# Step 6 — If you manage many servers with Ansible, do this at scale
ansible all -m shell -a "sed -i '/alice@laptop/d' ~/.ssh/authorized_keys" \
  --become -i inventory/production
ansible all -m shell -a "grep 'alice@laptop' ~/.ssh/authorized_keys && echo FOUND || echo clean" \
  -i inventory/production
```

**Ротация и отзыв ключей:** в SSH нет встроенного отзыва сертификатов, как в TLS. Отзыв означает ручное удаление публичного ключа из каждого `authorized_keys` на каждом сервере. Поэтому важны правила хранения ключей: отдельный ключ на человека и назначение, осмысленные комментарии и централизованный реестр. Крупные организации переходят к SSH Certificate Authority (в OpenSSH для этого есть `ssh-keygen -s`) или к инструментам вроде SSH secrets engine в HashiCorp Vault, выдающим короткоживущие сертификаты вместо долгоживущих ключей.

---

## Практические задания

### Задание 1: создать, установить и ограничить ключ

**Цель:** отработать полный жизненный цикл ключа и ограничения на стороне сервера.

1. Generate a new Ed25519 key pair named `id_ed25519_exercise` with the comment `exercise-key`. Give it a passphrase.
2. Add the public key to a test server (or a second user account on your local machine via `ssh localhost`) using `ssh-copy-id`.
3. Verify you can SSH using only this key by passing `-i ~/.ssh/id_ed25519_exercise` and `-o IdentitiesOnly=yes`.
4. On the server, edit `authorized_keys` to restrict the key: prepend `command="echo hello-from-restricted-key",no-pty` before the key entry.
5. SSH again with the same command. Confirm it prints `hello-from-restricted-key` and immediately exits instead of giving a shell.
6. Try running `ssh -i ~/.ssh/id_ed25519_exercise user@host "cat /etc/hostname"` — observe that the server ignores your command and runs the forced command instead.

**Что нужно понять:** ограничения команд в `authorized_keys` имеют приоритет над запросами клиента. Благодаря этому deploy keys можно использовать безопасно.

---

### Задание 2: настроить SSH для нескольких хостов через bastion

**Цель:** настроить прозрачное многоступенчатое SSH-подключение только через `~/.ssh/config`.

Вам понадобятся два хоста: `bastion` с одним IP и приватный хост, доступный только через bastion. Их можно смоделировать локально с помощью Docker или двух виртуальных машин либо использовать два доступных сервера, где первый видит второй, а ваш ноутбук не может подключиться ко второму напрямую.

1. Add both hosts to `~/.ssh/config` — one as `Host lab-bastion`, one as `Host lab-private` with `ProxyJump lab-bastion`.
2. Set `IdentitiesOnly yes` globally and specify `IdentityFile` for each host.
3. Set `ServerAliveInterval 30` globally.
4. Run `ssh lab-private` and confirm you land on the private host (not the bastion).
5. Run `ssh -v lab-private 2>&1 | grep -E "proxy|jump|connect"` to observe in the verbose output that SSH is making a proxied connection.
6. Without modifying the command, run `scp /etc/hostname lab-private:/tmp/from-laptop.txt` — verify the file appears on the private host, demonstrating that `scp` reads your config automatically.

**Что нужно понять:** `ProxyJump` прозрачен для всех инструментов, которые используют SSH внутри себя. Конфигурационный файл — центральное место для описания топологии инфраструктуры.

---

### Задание 3: диагностировать и исправить сломанную настройку SSH

**Цель:** научиться быстро диагностировать и устранять ошибки SSH.

Настройте вход на тестовый хост по SSH-ключу, затем по очереди намеренно сломайте конфигурацию перечисленными способами и попробуйте диагностировать каждый сбой без подсказок из урока:

1. **Permissions break:** run `chmod 644 ~/.ssh/id_ed25519` (private key world-readable). Attempt to connect. Read the error. Fix it. Understand why SSH refuses.
2. **Wrong authorized_keys permissions:** on the server, run `chmod 644 ~/.ssh/authorized_keys`. Attempt to connect. SSH will fall back to password auth (or fail if passwords are disabled). Fix it.
3. **Stale known_hosts:** delete the server's entry from `known_hosts` and regenerate the server's host key with `sudo ssh-keygen -A && sudo systemctl restart sshd`. Attempt to connect — read the MITM warning. Use `ssh-keyscan` to correctly update `known_hosts` rather than deleting the entry.
4. **Key not in agent:** run `ssh-add -D` to clear the agent. Then attempt `ssh -o IdentitiesOnly=yes user@host` *without* specifying `-i` and without any `IdentityFile` in config. Observe the failure. Add the key with `ssh-add` and retry.

Перед исправлением каждого сбоя выполните `ssh -v user@host` и найдите точную строку журнала, указывающую на причину. Флаги `-v`, `-vv` и `-vvv` — основные инструменты диагностики SSH.

**Что нужно понять:** SSH может завершаться без подробностей или показывать общее `Permission denied`. Подробный режим показывает, на каком шаге произошёл сбой: проверка хоста, предложение ключа или согласование метода аутентификации. Практическая диагностика SSH в основном сводится к внимательному чтению вывода `-v`.

---

### Задание 4: создать постоянный локальный туннель и подключиться через него

**Цель:** отработать SSH-туннелирование для доступа к базе данных — обычную задачу DevOps-инженера.

1. Choose a service running on a remote host that listens on a non-default port — for example, a web server on port 8080, or start a simple one with `python3 -m http.server 8080` on the remote host.
2. Open a background tunnel: `ssh -fN -L 9090:localhost:8080 user@remote-host`
3. Verify the tunnel is listening locally: `ss -tlnp | grep 9090`
4. Access the service through the tunnel: `curl http://localhost:9090`
5. Find the background SSH process with `ps aux | grep ssh` and kill it.
6. Verify the tunnel is gone: `ss -tlnp | grep 9090` should return nothing. Confirm `curl http://localhost:9090` now fails.
7. **Bonus:** add a `LocalForward 9090 localhost:8080` directive under the host in `~/.ssh/config`, then use `ssh -fN remote-host` and confirm the same tunnel opens without `-L` on the command line.

**Что нужно понять:** перенаправление портов позволяет безопасно подключаться к приватным сервисам из локальных инструментов — GUI баз данных, внутренних дашбордов и административных панелей — без изменения правил firewall. Принцип одинаков, обращаетесь ли вы к локальному порту jump-хоста или к имени хоста в приватной VPC.

---

### Быстрая проверка

1. Создайте временную пару ключей Ed25519 и выведите тип ключа из открытого ключа.

   ```bash
   ssh-keygen -t ed25519 -f /tmp/sshtest -N "" -q 2>/dev/null; awk '{print $1}' /tmp/sshtest.pub; rm -f /tmp/sshtest /tmp/sshtest.pub
   ```

   ```expected_output
   ssh-ed25519
   ```

Подсказка: используйте утилиту OpenSSH для генерации ключей; выберите современный тип, например Ed25519.
Подсказка: выполните `ssh-keygen -t ed25519`, указав временный выходной файл, затем извлеките первое поле открытого ключа командой `awk '{print $1}'`.

2. Извлеките значение `HostName` из форматированного блока конфигурации SSH.

   ```bash
   printf 'Host myserver\n  HostName 10.0.0.1\n  User devops\n' | awk '/HostName/{print $2}'
   ```

   ```expected_output
   10.0.0.1
   ```
Подсказка: найдите в тексте нужное ключевое слово и извлеките значение после него.
Подсказка: найдите строку `HostName` с помощью `grep`, затем передайте её в `awk '{print $2}'`, чтобы получить второе поле.
