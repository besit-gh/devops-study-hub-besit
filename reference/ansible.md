# Ansible — краткая справка

## Основные команды

| Команда | Описание |
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

| Команда | Описание |
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

| Шаблон | Описание |
|---------|-------------|
| `ansible-inventory --list` | Показать inventory в формате JSON |
| `ansible-inventory --graph` | Показать дерево inventory |
| `[web]` | Заголовок группы inventory |
| `web[1:3]` | Диапазон: web1, web2, web3 |
| `ansible_host=1.2.3.4` | Переопределить узел подключения |
| `ansible_user=ubuntu` | Переопределить пользователя SSH |
| `ansible_ssh_private_key_file=~/.ssh/key` | Переопределить ключ |
| `[all:vars]` | Переменные для всех узлов |

## Vault

| Команда | Описание |
|---------|-------------|
| `ansible-vault create file` | Создать зашифрованный файл |
| `ansible-vault edit file` | Редактировать зашифрованный файл |
| `ansible-vault encrypt file` | Зашифровать существующий файл |
| `ansible-vault decrypt file` | Расшифровать файл |
| `ansible-vault view file` | Просмотреть без сохранения расшифрованной версии на диск |
| `ansible-playbook play.yml --ask-vault-pass` | Запросить пароль Vault |
| `ansible-playbook play.yml --vault-password-file=.vault` | Использовать файл с паролем |

## Common Modules

| Module | Key args | Описание |
|--------|----------|-------------|
| `copy` | `src`, `dest`, `mode` | Скопировать локальный файл на удалённый узел |
| `template` | `src`, `dest` | Шаблон Jinja2 |
| `file` | `path`, `state`, `mode` | Управлять файлами и каталогами |
| `lineinfile` | `path`, `line`, `regexp` | Управлять строками в файле |
| `service` | `name`, `state`, `enabled` | Управлять службами |
| `package` | `name`, `state` | Установка пакетов независимо от ОС |
| `command` | `cmd` | Выполнить команду без shell |
| `shell` | `cmd` | Выполнить в shell |
| `stat` | `path` | Получить сведения о файле |
| `debug` | `msg`, `var` | Вывести отладочное сообщение |
| `assert` | `that`, `fail_msg` | Проверить условие |
| `include_tasks` | `file` | Динамически подключить файл задач |
| `block` | — | Сгруппировать задачи с общими атрибутами |

## Task Шаблонs

| Шаблон | Описание |
|---------|-------------|
| `when: ansible_os_family == "Debian"` | Условие |
| `loop: "{{ list_var }}"` | Перебрать элементы списка |
| `register: result` | Сохранить результат задачи |
| `result.rc == 0` | Проверить код возврата |
| `ignore_errors: true` | Продолжить при ошибке |
| `become: true` | Повышение привилегий |
| `notify: handler_name` | Запустить handler |
| `tags: [install, config]` | Назначить тег задаче |
| `delegate_to: localhost` | Выполнить на другом узле |
