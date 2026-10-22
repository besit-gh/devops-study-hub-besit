---
title: Роли Ansible
module: ansible
duration_min: 20
difficulty: intermediate
tags: [ansible, roles, galaxy, reusability, defaults, handlers, templates]
exercises: 4
---

## Обзор
Роли — механизм упаковки и повторного использования конфигурации Ansible. Вместо одного огромного playbook конфигурацию разбивают на независимые роли: `nginx`, `postgres`, `common` и другие. У каждой роли стандартная структура каталогов, которую Ansible распознаёт автоматически. Роли можно публиковать через Ansible Galaxy или хранить приватно внутри организации.

## Основные понятия

### Структура каталогов роли
```
roles/
  nginx/
    tasks/
      main.yml       # точка входа — задачи загружаются автоматически
    handlers/
      main.yml       # обработчики загружаются автоматически
    templates/
      nginx.conf.j2  # шаблоны Jinja2
    files/
      mime.types     # статические файлы (используются модулем copy)
    vars/
      main.yml       # переменные роли (высокий приоритет, их сложнее переопределить)
    defaults/
      main.yml       # значения по умолчанию (низкий приоритет, вызывающая конфигурация легко их переопределяет)
    meta/
      main.yml       # зависимости и метаданные роли
    README.md        # documentation
```

Обязателен только каталог `tasks/`; остальные каталоги необязательны.

### tasks/main.yml
```yaml
# roles/nginx/tasks/main.yml
---
- name: Установить nginx
  ansible.builtin.package:
    name: nginx
    state: present

- name: Создать каталог журналов
  ansible.builtin.file:
    path: "{{ nginx_log_dir }}"
    state: directory
    owner: www-data
    mode: "0755"

- name: Развернуть конфигурацию nginx
  ansible.builtin.template:
    src: nginx.conf.j2              # Ansible ищет файл в roles/nginx/templates/
    dest: /etc/nginx/nginx.conf
    validate: nginx -t -c %s       # проверить конфигурацию перед установкой
  notify: Перезагрузить nginx

- name: Запустить nginx и включить автозапуск
  ansible.builtin.service:
    name: nginx
    state: started
    enabled: true
```

### defaults/main.yml
```yaml
# roles/nginx/defaults/main.yml
nginx_worker_processes: auto
nginx_worker_connections: 1024
nginx_log_dir: /var/log/nginx
nginx_user: www-data
nginx_port: 80
nginx_server_name: "_"             # обработка запросов для любого имени хоста
nginx_extra_params: {}
```

Значения по умолчанию имеют самый низкий приоритет, поэтому вызывающий playbook легко может их переопределить.

### handlers/main.yml
```yaml
# roles/nginx/handlers/main.yml
---
- name: Перезагрузить nginx
  ansible.builtin.service:
    name: nginx
    state: reloaded

- name: Перезапустить nginx
  ansible.builtin.service:
    name: nginx
    state: restarted
```

### templates/nginx.conf.j2
```jinja2
user {{ nginx_user }};
worker_processes {{ nginx_worker_processes }};

events {
    worker_connections {{ nginx_worker_connections }};
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    access_log /var/log/nginx/access.log;
    error_log  /var/log/nginx/error.log;

    server {
        listen {{ nginx_port }};
        server_name {{ nginx_server_name }};

        {% for param, value in nginx_extra_params.items() %}
        {{ param }} {{ value }};
        {% endfor %}
    }
}
```

### meta/main.yml — зависимости
```yaml
# roles/nginx/meta/main.yml
galaxy_info:
  author: developer
  description: Роль для настройки веб-сервера Nginx
  license: MIT
  min_ansible_version: "2.14"
  platforms:
    - name: Ubuntu
      versions: [22.04, 20.04]
    - name: EL
      versions: [8, 9]

dependencies:
  - role: common        # выполняется перед этой ролью
  - role: geerlingguy.git   # from Galaxy
```

### Использование ролей в playbook
```yaml
---
- name: Настроить веб-уровень
  hosts: webservers
  become: true
  roles:
    - role: common
    - role: nginx
      vars:
        nginx_port: 8080              # переопределить значения по умолчанию для этого play
        nginx_server_name: api.example.com
    - role: certbot
      when: ansible_facts.os_family == "Debian"
```

Альтернатива с `import_role` / `include_role` (поддерживает условия и циклы):
```yaml
tasks:
  - name: Применить роль nginx
    ansible.builtin.import_role:
      name: nginx
    vars:
      nginx_port: 8080

  - name: Применить роль приложения только на основном узле
    ansible.builtin.include_role:
      name: myapp
    when: inventory_hostname == groups['webservers'][0]
```

### Ansible Galaxy
Galaxy — публичный каталог ролей и коллекций сообщества:

```bash
# Найти роль
ansible-galaxy search nginx

# Установить роль
ansible-galaxy role install geerlingguy.nginx
ansible-galaxy role install geerlingguy.nginx --version 3.2.0

# Установить роли из requirements.yml
ansible-galaxy install -r requirements.yml

# Показать установленные роли
ansible-galaxy role list
```

```yaml
# requirements.yml
roles:
  - name: geerlingguy.nginx
    version: "3.2.0"
  - name: geerlingguy.postgresql
    version: "3.4.0"

collections:
  - name: community.postgresql
    version: "3.4.0"
  - name: amazon.aws
    version: "7.0.0"
```

### Коллекции
Коллекции объединяют роли, модули и плагины в пространстве имён:
```bash
ansible-galaxy collection install community.postgresql
ansible-galaxy collection install amazon.aws
ansible-galaxy collection install -r requirements.yml
```

После установки указывайте полные имена модулей с пространством имён коллекции:
```yaml
- name: Create database
  community.postgresql.postgresql_db:
    name: myapp
    state: present
```

### Тестирование ролей с Molecule
Molecule — стандартный фреймворк для тестирования ролей Ansible:

```bash
pip install molecule molecule-docker
cd roles/nginx
molecule init scenario           # создать структуру каталогов molecule/default/
molecule test                    # проверка стиля → создание → применение роли → проверка → удаление
molecule converge                # создать окружение и применить роль (без удаления)
molecule verify                  # выполнить только тесты
molecule destroy                 # очистить окружение
```

```yaml
# molecule/default/verify.yml
---
- name: Проверить роль nginx
  hosts: all
  tasks:
    - name: Проверить, что nginx запущен
      ansible.builtin.service_facts:

    - name: Убедиться, что nginx активен
      ansible.builtin.assert:
        that:
          - "'nginx' in services"
          - "services.nginx.state == 'running'"

    - name: Проверить порт 80 nginx
      ansible.builtin.wait_for:
        port: 80
        timeout: 5
```

## Примеры

### Общая роль (применяется ко всем узлам)
```yaml
# roles/common/tasks/main.yml
---
- name: Установить общие пакеты
  ansible.builtin.package:
    name:
      - curl
      - htop
      - vim
      - unzip
      - python3-pip
    state: present

- name: Настроить часовой пояс
  community.general.timezone:
    name: "{{ common_timezone }}"

- name: Настроить параметры sysctl
  ansible.posix.sysctl:
    name: "{{ item.key }}"
    value: "{{ item.value }}"
    state: present
    reload: true
  loop: "{{ common_sysctl_params | dict2items }}"
```

## Практические задания

1. Создайте роль `nginx` командой `ansible-galaxy role init nginx`. Реализуйте задачи установки nginx, развёртывания конфигурации из шаблона и управления службой. Подключите роль в playbook.
2. Определите настраиваемые переменные (`nginx_port`, `nginx_worker_processes`) в `defaults/main.yml`. Переопределите их из playbook для одной группы узлов, а для другой оставьте значения по умолчанию.
3. Добавьте в `meta/main.yml` зависимость от собственной роли `common`. Убедитесь, что Ansible запускает `common` перед `nginx`, даже если порядок не указан в playbook.
4. Напишите тест Molecule для роли nginx, проверяющий установку пакета, работу службы и прослушивание порта 80. Выполните `molecule test` и убедитесь, что тест проходит.


---

### Быстрая проверка

5. Посчитайте стандартные подкаталоги роли. Выполните: `printf 'tasks\nhandlers\ndefaults\nvars\nfiles\ntemplates\nmeta\n' | wc -l`

```expected_output
7
```

Подсказка: сформируйте список элементов и посчитайте количество строк стандартными инструментами Unix.
Подсказка: используйте `printf`, чтобы вывести имена подкаталогов по одному в строке, разделяя их через `\n`, а затем передайте вывод в `wc -l`.

6. Извлеките имя файла точки входа роли из пути. Выполните: `echo "roles/nginx/tasks/main.yml" | awk -F/ '{print $NF}'`

```expected_output
main.yml
```

Подсказка: `awk` может разделить строку на поля по заданному разделителю, а затем обратиться к последнему полю.
Подсказка: задайте `/` разделителем полей через `awk -F/` и используйте `$NF`, чтобы вывести последнее поле.
