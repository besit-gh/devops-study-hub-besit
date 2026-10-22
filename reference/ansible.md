# Ansible — краткая справка

## Основные команды

| Command | Description |
|---------|-------------|
| `ansible all -m ping` | Проверить доступность всех узлов |
| `ansible all -m ping -i inventory` | Использовать указанный inventory |
| `ansible-playbook play.yml` | Запустить playbook |
| `ansible-playbook play.yml -i inventory` | Явно указать inventory |
| `ansible-playbook play.yml --check` | Пробный запуск (режим проверки) |
| `ansible-playbook play.yml --diff` | Показать различия файлов |
| `ansible-playbook play.yml -t tag` | Запустить задачи с указанными тегами |
| `ansible-playbook play.yml --skip-tags tag` | Пропустить теги |
| `ansible-playbook play.yml -l host` | Ограничить выполнение выбранными узлами |
| `ansible-playbook play.yml -v` | Подробный вывод (для ещё большей детализации используйте -vvv) |

## Разовые команды

| Command | Description |
|---------|-------------|
| `ansible host -m command -a "cmd"` | Выполнить команду без shell |
| `ansible host -m shell -a "cmd \| pipe"` | Выполнить shell-команду |
| `ansible host -m copy -a "src=f dest=/path"` | Скопировать файл |
| `ansible host -m file -a "path=/dir state=directory"` | Создать каталог |
| `ansible host -m service -a "name=nginx state=started"` | Управлять службой |
| `ansible host -m yum -a "name=pkg state=present"` | Установить пакет |
| `ansible host -m apt -a "name=pkg state=present"` | Установка (Debian) |
| `ansible host -m user -a "name=u state=present"` | Создать пользователя |
| `ansible host -a "df -h" -b` | Выполнить с sudo (become) |
| `ansible host -m setup` | Собрать сведения об узлах |

## Inventory — список узлов

| Pattern | Description |
|---------|-------------|
| `ansible-inventory --list` | Show inventory as JSON |
| `ansible-inventory --graph` | Show inventory tree |
| `[web]` | Inventory group header |
| `web[1:3]` | Range: web1, web2, web3 |
| `ansible_host=1.2.3.4` | Override connection host |
| `ansible_user=ubuntu` | Override SSH user |
| `ansible_ssh_private_key_file=~/.ssh/key` | Override key |
| `[all:vars]` | Variables for all hosts |

## Vault

| Command | Description |
|---------|-------------|
| `ansible-vault create file` | Create encrypted file |
| `ansible-vault edit file` | Edit encrypted file |
| `ansible-vault encrypt file` | Encrypt existing file |
| `ansible-vault decrypt file` | Decrypt file |
| `ansible-vault view file` | View without decrypting to disk |
| `ansible-playbook play.yml --ask-vault-pass` | Prompt for vault password |
| `ansible-playbook play.yml --vault-password-file=.vault` | Use password file |

## Common Modules

| Module | Key args | Description |
|--------|----------|-------------|
| `copy` | `src`, `dest`, `mode` | Copy local file to remote |
| `template` | `src`, `dest` | Jinja2 template |
| `file` | `path`, `state`, `mode` | Manage files/dirs |
| `lineinfile` | `path`, `line`, `regexp` | Manage lines in file |
| `service` | `name`, `state`, `enabled` | Manage services |
| `package` | `name`, `state` | OS-agnostic package install |
| `command` | `cmd` | Выполнить команду без shell |
| `shell` | `cmd` | Run in shell |
| `stat` | `path` | Get file info |
| `debug` | `msg`, `var` | Print debug message |
| `assert` | `that`, `fail_msg` | Validate condition |
| `include_tasks` | `file` | Include task file dynamically |
| `block` | — | Group tasks with shared attrs |

## Task Patterns

| Pattern | Description |
|---------|-------------|
| `when: ansible_os_family == "Debian"` | Conditional |
| `loop: "{{ list_var }}"` | Loop over list |
| `register: result` | Store task output |
| `result.rc == 0` | Check return code |
| `ignore_errors: true` | Continue on failure |
| `become: true` | Privilege escalation |
| `notify: handler_name` | Trigger handler |
| `tags: [install, config]` | Tag a task |
| `delegate_to: localhost` | Run on different host |
