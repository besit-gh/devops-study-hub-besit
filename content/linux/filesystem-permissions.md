---
title: Файловая система и права доступа
module: linux
duration_min: 15
difficulty: intermediate
tags: [permissions, chmod, chown, acl, umask, setuid, sticky, filesystem]
exercises: 4
---

## Обзор

Права доступа Linux — первая линия защиты каждого файла и каталога в системе. Ошибки настройки приводят к двум типам проблем: службы не могут получить доступ к собственным файлам из-за слишком строгих прав, либо возникают уязвимости, позволяющие посторонним пользователям и процессам читать секреты, изменять конфигурации или выполнять произвольный код. Полная модель прав — включая специальные биты, umask и ACL — необходима для настройки веб-серверов, развёртывания приложений, управления SSH-ключами и создания рабочих CI/CD-пайплайнов.

## Основные понятия

### Модель прав доступа

У каждого файла и каталога есть:
- **Владелец** — пользователь
- **Группа** — набор пользователей
- **Набор прав** для трёх категорий: владелец, группа и остальные

Права доступа отображаются в выводе `ls -la` в виде строки из 10 символов:

```
-rwxr-xr-x  1 ubuntu www-data 4096 deploy.sh
│└──┘└──┘└──┘
│  │   │   └── others: r-x (read + execute, no write)
│  │   └────── group:  r-x (read + execute, no write)
│  └────────── owner:  rwx (read + write + execute)
└───────────── file type: - (regular file), d (directory), l (symlink)
```

Каждому символу права соответствует числовое значение:
- `r` = 4 (read)
- `w` = 2 (write)
- `x` = 1 (execute)
- `-` = 0 (no permission)

В восьмеричной записи значения складываются: `rwx` = 7, `r-x` = 5, `r--` = 4, `---` = 0.

Таким образом, `chmod 755` означает: владелец — rwx (7), группа — r-x (5), остальные — r-x (5).

### Чтение прав доступа

```bash
# Detailed listing: permissions, links, owner, group, size, date, name
ls -la /var/www/

# Output:
# drwxr-xr-x  4 root    www-data 4096 Jan 15 10:00 .
# -rw-r--r--  1 root    root      253 Jan 15 10:00 index.html
# -rwxr-xr-x  1 ubuntu  www-data  512 Jan 15 10:00 deploy.sh
# lrwxrwxrwx  1 root    root       12 Jan 15 10:00 logs -> /var/log/nginx

# First character indicates file type:
# -  regular file
# d  directory
# l  symbolic link
# b  block device (disks)
# c  character device (terminals)
# p  named pipe (FIFO)
# s  socket
```

Для **каталогов** бит `x` означает возможность *войти* в каталог (пройти по пути), а не выполнить его. Каталог с правами `r--` можно просмотреть, но нельзя открыть. Каталог с `--x` можно открыть по известному пути, но нельзя получить список содержимого.

### chmod — изменение прав

Есть два режима задания прав: восьмеричный и символьный.

**Восьмеричный режим:**
```bash
# Owner: full access | Group: read+execute | Others: read+execute
chmod 755 deploy.sh

# Owner: read+write | Group: read only | Others: read only
chmod 644 config.yaml

# Owner: full access | Group: full access | Others: none
chmod 770 shared-dir/

# Only owner can read+write, no one else can see it
chmod 600 ~/.ssh/id_ed25519     # private key MUST be 600
chmod 644 ~/.ssh/id_ed25519.pub # public key: world-readable is fine
```

**Символьный режим — удобнее для точечных изменений:**
```bash
# Add execute for owner
chmod u+x script.sh

# Remove write from group and others
chmod go-w important.conf

# Give everyone execute (use carefully)
chmod a+x runme.sh

# Set exact permissions symbolically
chmod u=rwx,g=rx,o= deploy.sh

# Recursive: apply to directory and all contents
chmod -R 755 /var/www/html/
```

### chown и chgrp — изменение владельца

```bash
# Change owner and group
chown ubuntu:www-data /var/www/html

# Change owner only (group stays the same)
chown ubuntu deploy.sh

# Change group only
chgrp www-data /var/www/html

# Recursive ownership change
chown -R ubuntu:www-data /var/www/

# Same as chown ubuntu:ubuntu (use current user's primary group)
chown ubuntu: deploy.sh

# Reference another file's ownership
chown --reference=/etc/nginx/nginx.conf target.conf
```

### Специальные биты прав

Помимо стандартных rwx существуют три специальных бита, меняющих поведение файлов и каталогов:

| Бит | Восьмеричное значение | Название | Для файлов | Для каталогов |
|-----|-------|------|----------|----------------|
| setuid | 4000 | SUID | Выполнение от имени владельца файла | В основном игнорируется |
| setgid | 2000 | SGID | Выполнение от имени группы файла | Новые файлы наследуют группу каталога |
| sticky | 1000 | Sticky | Игнорируется | Удалять файл может только его владелец |

**setuid (`s` в позиции бита выполнения владельца):**
```bash
# Программы с setuid выполняются от имени владельца файла, а не пользователя, который их запустил
ls -la /usr/bin/passwd
# -rwsr-xr-x 1 root root /usr/bin/passwd
#      ^--- 's' means setuid + execute; 'S' means setuid but NOT executable

# Set setuid (add 4 to the front of octal)
chmod 4755 /usr/bin/myapp     # rwsr-xr-x
chmod u+s /usr/bin/myapp      # symbolic
```

Файл `passwd` принадлежит root и выполняется с правами root, когда его запускает любой пользователь. Это позволяет пользователю изменить собственный пароль. Linux игнорирует SUID на shell-скриптах.

**setgid (`s` в позиции бита выполнения группы):**
```bash
# Set setgid on a directory — new files inherit the directory's group
mkdir /shared
chgrp devs /shared
chmod 2775 /shared            # rwxrwsr-x
chmod g+s /shared             # symbolic

# Now any file created in /shared gets group 'devs', regardless of creator's primary group
touch /shared/newfile
ls -la /shared/newfile
# -rw-rw-r-- 1 ubuntu devs newfile     ← group is 'devs', not ubuntu's primary group
```

Полезно для общих каталогов проектов, в которых разработчикам нужно работать с файлами друг друга.

**sticky bit (`t` в позиции бита выполнения для остальных):**
```bash
# Classic example: /tmp is world-writable but sticky
ls -ld /tmp
# drwxrwxrwt 20 root root /tmp
#          ^--- 't' means sticky + execute; 'T' means sticky but NOT executable

# In a sticky directory, you can only delete files you own
# (even if you have write permission on the directory)
chmod 1777 /tmp          # standard /tmp permissions
chmod o+t /shared-dir    # symbolic
```

Sticky bit не позволяет пользователям удалять чужие файлы в общих каталогах.

**Поиск файлов со специальными битами:**
```bash
# Find all setuid files (potential security concern — audit these)
find / -perm -4000 -type f 2>/dev/null

# Find all setgid files
find / -perm -2000 -type f 2>/dev/null

# Find world-writable files (excluding /proc, /sys)
find / -perm -o+w -not \( -path /proc -prune -o -path /sys -prune \) 2>/dev/null
```

### umask — права по умолчанию для новых файлов

`umask` определяет, какие биты прав будут **убраны** у новых файлов и каталогов. Это маска: биты, установленные в umask, отключаются.

```bash
# Check current umask
umask         # e.g., 0022
umask -S      # symbolic: u=rwx,g=rx,o=rx

# Default umask is 022:
# New file max:       666 (files can't start executable)
# minus umask:       -022
# Result:             644 → owner rw, group r, others r

# New directory max:  777
# minus umask:       -022
# Result:             755 → owner rwx, group rx, others rx
```

```bash
# Change umask for current session
umask 027     # files: 640, dirs: 750 (group can read, others get nothing)
umask 077     # files: 600, dirs: 700 (only owner)
```

Чтобы сделать настройку постоянной, добавьте `umask 027` в `/etc/profile` (для всей системы) или `~/.bashrc` (для конкретного пользователя).

**Почему это важно:** если пользователь CI/CD создаёт логи с `umask 022`, их смогут читать все. Если приложение создаёт конфигурации с `umask 000`, любой пользователь сможет их изменять. Явно задавайте umask для сервисных аккаунтов.

### ACL — списки контроля доступа

Стандартные права Unix предусматривают одного владельца, одну группу и категорию «все остальные». ACL расширяют эту модель и позволяют назначать права дополнительным пользователям и группам без смены владельца.

```bash
# Check if ACL support is available
mount | grep acl
# Or check filesystem mount options: defaults,acl

# View ACLs on a file
getfacl /var/www/html/
# file: var/www/html/
# owner: root
# group: www-data
# user::rwx
# group::r-x
# other::r-x

# Grant a specific user read+write access
setfacl -m u:appuser:rw /var/www/html/config.json

# Grant a specific group execute on a directory
setfacl -m g:deploy:rx /var/www/html/

# Set default ACL on a directory (inherited by new files/subdirs)
setfacl -d -m u:appuser:rw /var/www/html/

# Remove a specific ACL entry
setfacl -x u:appuser /var/www/html/config.json

# Remove all ACLs, revert to standard permissions
setfacl -b /var/www/html/config.json
```

Если для файла настроен ACL, `ls -la` показывает знак `+` после строки прав:
```
-rw-rw-r--+ 1 root www-data config.json
#         ^--- + means ACL is set
```

### Атрибуты файлов — chattr и lsattr

Помимо прав доступа, файловые системы Linux (ext4, xfs) поддерживают атрибуты файлов, определяющие, как ядро может работать с файлом:

```bash
# View attributes
lsattr /etc/resolv.conf
# ----i--------e-- /etc/resolv.conf
#     ^--- 'i' means immutable

# Make a file immutable (even root can't modify or delete it)
chattr +i /etc/resolv.conf

# Remove immutable attribute
chattr -i /etc/resolv.conf

# Append-only (useful for log files — can grow but not be truncated)
chattr +a /var/log/audit/audit.log

# Useful attributes:
# i  immutable — no writes, no deletion, no rename, no hard links
# a  append-only — only append writes allowed
# e  extent format — informational, set automatically
```

`chattr +i` используют инструменты усиления безопасности для защиты критически важных файлов конфигурации, например `/etc/passwd` и `/etc/resolv.conf`. Это один из немногих механизмов, который защищает файл даже от `rm -rf`, запущенного от root.

### Повышение привилегий — sudo и su

```bash
# Run a single command as root
sudo apt update

# Open a root shell (prefer -i over -s for a login shell)
sudo -i

# Run as another user
sudo -u www-data /usr/bin/php artisan migrate

# Check what sudo privileges you have
sudo -l

# Switch to root (requires root password, or don't use on cloud VMs)
su -

# Switch to another user
su - www-data
```

Файл `/etc/sudoers` определяет, кто и какие команды может выполнять от имени других пользователей. Всегда редактируйте его через `visudo`: перед сохранением команда проверяет синтаксис.
```
# /etc/sudoers
# Format: who  where=(as_whom) commands
ubuntu  ALL=(ALL:ALL) NOPASSWD: /usr/bin/systemctl restart nginx
deploy  ALL=(ALL) NOPASSWD: /usr/local/bin/deploy.sh
```

`NOPASSWD:` часто используют для сервисных аккаунтов CI/CD, которым нужно перезапускать службы без интерактивного ввода пароля.

### Поиск файлов по правам доступа

```bash
# Files world-writable
find /etc -perm -o+w 2>/dev/null

# Files with exact permissions 777
find /var/www -perm 777

# Files where group has write (regardless of other bits)
find /home -perm -g+w 2>/dev/null

# Find all SUID binaries (audit these — common attack vector)
find / -perm -4000 -type f 2>/dev/null | sort

# Files NOT owned by any current user (orphaned — clean these up)
find / -nouser 2>/dev/null

# Files modified in the last 24 hours
find /etc -mtime -1 -type f

# Find SSH authorized_keys files (check for unauthorized entries)
find /home -name authorized_keys 2>/dev/null -exec ls -la {} \;
```

## Примеры

### Настройка веб-сервера (nginx и приложение)

```bash
# Типовая схема прав доступа веб-сервера
chown -R www-data:www-data /var/www/myapp      # nginx process owns files
find /var/www/myapp -type d -exec chmod 755 {} \;  # directories: traverse+list
find /var/www/myapp -type f -exec chmod 644 {} \;  # files: read-only for group/others

# Приложение записывает данные в отдельный каталог (загрузки, кэш)
mkdir -p /var/www/myapp/storage/uploads
chown -R www-data:www-data /var/www/myapp/storage
chmod 775 /var/www/myapp/storage/uploads   # www-data can write here

# Файлы конфигурации с секретами — доступ только владельцу
chmod 600 /var/www/myapp/.env
chown www-data:www-data /var/www/myapp/.env
```

### Права для развёртывания через CI/CD

```bash
#!/usr/bin/env bash
# Развёртывание выполняется пользователем deploy, nginx работает от www-data
# Оба пользователя должны читать файлы, но записывать может только deploy

# Общая группа для пользователей deploy и www-data
usermod -a -G www-data deploy

# Назначить группу и setgid, чтобы новые файлы наследовали группу
chown -R deploy:www-data /var/www/myapp
chmod -R 2750 /var/www/myapp    # setgid + owner rwx, group rx, others none

# Проверить настройки
ls -la /var/www/myapp
stat /var/www/myapp
```

### Требования к правам SSH-ключей

SSH строго проверяет права приватных ключей и отказывается использовать ключи с чрезмерно широкими разрешениями:

```bash
# Правильные права каталога SSH и ключей
chmod 700 ~/.ssh                  # only owner can enter
chmod 600 ~/.ssh/id_ed25519       # private key: owner read+write only
chmod 644 ~/.ssh/id_ed25519.pub   # public key: world-readable is fine
chmod 600 ~/.ssh/authorized_keys  # authorized_keys: owner only
chmod 644 ~/.ssh/known_hosts      # known_hosts: readable is ok
chmod 600 ~/.ssh/config           # config may contain sensitive paths

# Исправить права, если после клонирования репозитория они оказались неверными
find ~/.ssh -type f -exec chmod 600 {} \;
chmod 700 ~/.ssh
```

### Скрипт аудита безопасности

```bash
#!/usr/bin/env bash
# Быстрый аудит прав доступа — регулярно запускайте на production-серверах

echo "=== World-writable files (excluding /proc /sys /dev) ==="
find / -perm -o+w -type f \
    \( -path /proc -o -path /sys -o -path /dev \) -prune \
    -o -print 2>/dev/null | head -30

echo ""
echo "=== SUID binaries ==="
find / -perm -4000 -type f 2>/dev/null | sort

echo ""
echo "=== Files with no owner ==="
find / -nouser -type f 2>/dev/null | head -20

echo ""
echo "=== /tmp contents with permissions ==="
ls -la /tmp/ | head -20
```

## Практические задания

1. Создайте каталог `/tmp/shared` и настройте его так, чтобы: (а) владельцем группы была `staff`; (б) все новые файлы наследовали группу `staff` (используйте setgid); (в) любой пользователь мог создавать файлы, но удалять их мог только владелец файла (sticky bit). Проверьте результат: создайте файлы от двух разных пользователей и попробуйте удалить чужой файл.

2. Веб-приложению на Python нужно читать секрет из `/etc/myapp/secret.key`. Приложение работает от пользователя `appuser` (не root и не участник привилегированных групп). С помощью `setfacl` предоставьте `appuser` только право чтения файла, не меняя владельца и группу. Проверьте результат командами `getfacl` и `sudo -u appuser cat /etc/myapp/secret.key`.

3. Напишите Bash-скрипт `audit-permissions.sh`, который сканирует `/var/www` и `/etc` на наличие файлов, доступных для записи всем пользователям, выводит их права и владельца и завершается с кодом 1, если такие файлы найдены (скрипт должен подходить для контрольного этапа CI). Проверьте его, создав файл с правом записи для всех и убедившись, что скрипт его обнаруживает.

4. Найдите все бинарные файлы с SUID и SGID с помощью `find / -perm -4000 -o -perm -2000`. Для каждого в одном предложении объясните, ПОЧЕМУ ему нужен повышенный бит привилегий (используйте `man <binary>` или изучите документацию). Отметьте файлы, которые выглядят подозрительно или избыточно.

---

### Быстрая проверка

1. Выведите биты прав доступа файла `/etc/passwd`.

   ```bash
   ls -l /etc/passwd | awk '{print $1}'
   ```

   ```expected_output
   -rw-r--r--
   ```

Подсказка: вспомните команду, которая выводит подробные метаданные файла, включая права доступа, в длинном формате.
Подсказка: используйте `ls` с флагом `-l`, затем выделите первое поле — строку с правами доступа.

2. Выведите биты прав доступа каталога `/tmp` (ожидается sticky bit).

   ```bash
   ls -ld /tmp | awk '{print $1}'
   ```

   ```expected_output
   drwxrwxrwt
   ```

Подсказка: вспомните команду Linux, которая показывает метаданные файла или каталога, включая биты прав.
Подсказка: используйте `ls -ld /tmp`, чтобы вывести сам каталог `/tmp` вместе со строкой прав доступа.
