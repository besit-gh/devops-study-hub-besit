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
      main.yml       # entry point — tasks auto-loaded
    handlers/
      main.yml       # handlers auto-loaded
    templates/
      nginx.conf.j2  # Jinja2 templates
    files/
      mime.types     # static files (used with copy module)
    vars/
      main.yml       # role variables (high precedence, not easily overridden)
    defaults/
      main.yml       # default values (low precedence, easily overridden by caller)
    meta/
      main.yml       # role dependencies, metadata
    README.md        # documentation
```

Обязателен только каталог `tasks/`; остальные каталоги необязательны.

### tasks/main.yml
```yaml
# roles/nginx/tasks/main.yml
---
- name: Install nginx
  ansible.builtin.package:
    name: nginx
    state: present

- name: Create log directory
  ansible.builtin.file:
    path: "{{ nginx_log_dir }}"
    state: directory
    owner: www-data
    mode: "0755"

- name: Deploy nginx configuration
  ansible.builtin.template:
    src: nginx.conf.j2              # Ansible looks in roles/nginx/templates/
    dest: /etc/nginx/nginx.conf
    validate: nginx -t -c %s       # validate before installing
  notify: Reload nginx

- name: Start and enable nginx
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
nginx_server_name: "_"             # catch-all
nginx_extra_params: {}
```

Значения по умолчанию имеют самый низкий приоритет, поэтому вызывающий playbook легко может их переопределить.

### handlers/main.yml
```yaml
# roles/nginx/handlers/main.yml
---
- name: Reload nginx
  ansible.builtin.service:
    name: nginx
    state: reloaded

- name: Restart nginx
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
  description: Nginx web server role
  license: MIT
  min_ansible_version: "2.14"
  platforms:
    - name: Ubuntu
      versions: [22.04, 20.04]
    - name: EL
      versions: [8, 9]

dependencies:
  - role: common        # runs before this role
  - role: geerlingguy.git   # from Galaxy
```

### Использование ролей в playbook
```yaml
---
- name: Configure web tier
  hosts: webservers
  become: true
  roles:
    - role: common
    - role: nginx
      vars:
        nginx_port: 8080              # override defaults for this play
        nginx_server_name: api.example.com
    - role: certbot
      when: ansible_facts.os_family == "Debian"
```

Альтернатива с `import_role` / `include_role` (поддерживает условия и циклы):
```yaml
tasks:
  - name: Apply nginx role
    ansible.builtin.import_role:
      name: nginx
    vars:
      nginx_port: 8080

  - name: Apply app role on primary only
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
molecule init scenario           # creates molecule/default/ structure
molecule test                    # lint → create → converge → verify → destroy
molecule converge                # create + apply role (without destroying)
molecule verify                  # run tests only
molecule destroy                 # clean up
```

```yaml
# molecule/default/verify.yml
---
- name: Verify nginx role
  hosts: all
  tasks:
    - name: Check nginx is running
      ansible.builtin.service_facts:

    - name: Assert nginx is active
      ansible.builtin.assert:
        that:
          - "'nginx' in services"
          - "services.nginx.state == 'running'"

    - name: Check nginx port 80
      ansible.builtin.wait_for:
        port: 80
        timeout: 5
```

## Примеры

### Общая роль (применяется ко всем узлам)
```yaml
# roles/common/tasks/main.yml
---
- name: Install common packages
  ansible.builtin.package:
    name:
      - curl
      - htop
      - vim
      - unzip
      - python3-pip
    state: present

- name: Set timezone
  community.general.timezone:
    name: "{{ common_timezone }}"

- name: Configure sysctl
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
