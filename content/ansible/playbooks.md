---
title: Playbook и inventory Ansible
module: ansible
duration_min: 20
difficulty: beginner
tags: [ansible, playbooks, inventory, tasks, modules, idempotent]
exercises: 4
---

## Обзор
Ansible автоматизирует управление конфигурацией и развёртывание приложений сразу на множестве серверов через SSH, без установки агента на управляемых узлах. **Playbook** описывает, что нужно сделать, а **inventory** — на каких узлах это выполнить. Все операции запускаются с управляющего узла — например, ноутбука или CI-сервера, — который передаёт изменения по SSH. В уроке разбираются основы обоих компонентов.

## Основные понятия

### Основные принципы
- **Без агентов** — на управляемых узлах нужны только SSH и Python
- **Идемпотентность** — повторный запуск playbook приводит к тому же результату без нежелательных побочных эффектов
- **Декларативность** — вы описываете желаемое состояние, а Ansible определяет, что нужно изменить
- **Модель push** — управляющий узел подключается к управляемым (в отличие от модели pull в Puppet/Chef)

### Inventory — список узлов
Inventory сообщает Ansible, какими узлами нужно управлять:

```ini
# inventory.ini (формат INI)
[webservers]
web01.example.com
web02.example.com
192.168.1.10

[databases]
db01.example.com ansible_user=ubuntu ansible_port=22

[production:children]  # group of groups
webservers
databases

[all:vars]  # variables for all hosts
ansible_user=deploy
ansible_python_interpreter=/usr/bin/python3
```

```yaml
# inventory.yaml (формат YAML — более гибкий)
all:
  vars:
    ansible_user: deploy
    ansible_python_interpreter: /usr/bin/python3

  children:
    webservers:
      hosts:
        web01.example.com:
          http_port: 80
        web02.example.com:
          http_port: 8080
    databases:
      hosts:
        db01.example.com:
```

```bash
# Проверить inventory
ansible -i inventory.ini all --list-hosts
ansible -i inventory.ini webservers --list-hosts

# Проверить доступность всех узлов с помощью ping
ansible -i inventory.ini all -m ping

# Выполнить ad-hoc-команду
ansible -i inventory.ini webservers -m shell -a "uptime"
ansible -i inventory.ini all -m shell -a "df -h" -b   # -b: become (sudo)
```

### Структура playbook
```yaml
# deploy.yml
---
- name: Deploy web application        # play name
  hosts: webservers                   # target hosts/group
  become: true                        # use sudo for all tasks
  vars:
    app_version: "1.2.3"
    app_dir: /opt/myapp

  tasks:
    - name: Ensure nginx is installed
      ansible.builtin.package:
        name: nginx
        state: present                # present = installed, absent = removed

    - name: Ensure nginx is started and enabled
      ansible.builtin.service:
        name: nginx
        state: started
        enabled: true

    - name: Copy application config
      ansible.builtin.template:
        src: templates/nginx.conf.j2
        dest: /etc/nginx/sites-enabled/myapp.conf
        owner: root
        group: root
        mode: "0644"
      notify: Reload nginx             # triggers handler

  handlers:
    - name: Reload nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded
```

```bash
# Запустить playbook
ansible-playbook -i inventory.ini deploy.yml

# Пробный запуск (показать предполагаемые изменения)
ansible-playbook -i inventory.ini deploy.yml --check

# Ограничить выполнение выбранными узлами
ansible-playbook -i inventory.ini deploy.yml --limit web01.example.com

# Подробный вывод
ansible-playbook -i inventory.ini deploy.yml -v    # -vvv for maximum verbosity
```

### Основные модули
```yaml
tasks:
  # Управление пакетами
  - name: Install packages
    ansible.builtin.package:         # auto-detects apt/yum/dnf
      name: [nginx, curl, git]
      state: present

  - name: Install specific apt packages
    ansible.builtin.apt:
      name: nginx=1.24.0*
      update_cache: true             # apt-get update first

  # Операции с файлами
  - name: Create directory
    ansible.builtin.file:
      path: /opt/myapp
      state: directory               # file, directory, absent, link
      owner: myapp
      group: myapp
      mode: "0755"

  - name: Copy file
    ansible.builtin.copy:
      src: files/app.conf            # relative to playbook
      dest: /etc/myapp/app.conf
      mode: "0644"

  - name: Render template
    ansible.builtin.template:
      src: templates/config.j2       # Jinja2 template
      dest: /etc/myapp/config.conf

  # Команды
  - name: Run a command
    ansible.builtin.command:
      cmd: /opt/myapp/bin/migrate
      creates: /opt/myapp/.migrated  # skip if this file exists (idempotency)

  - name: Run a shell command (supports pipes, redirection)
    ansible.builtin.shell:
      cmd: "ps aux | grep nginx | grep -v grep"

  # Пользователи
  - name: Create user
    ansible.builtin.user:
      name: myapp
      shell: /bin/bash
      groups: [myapp, docker]
      create_home: true

  # Git
  - name: Clone/update repo
    ansible.builtin.git:
      repo: https://github.com/org/myapp.git
      dest: /opt/myapp
      version: v1.2.3
      force: true
```

### Переменные и факты
```yaml
vars:
  app_port: 8080

# Доступ к переменным inventory: {{ hostvars['web01']['http_port'] }}
# Доступ к фактам: {{ ansible_facts['os_family'] }} → "Debian" или "RedHat"

tasks:
  - name: Gather facts
    ansible.builtin.setup:    # runs automatically at play start

  - name: Print OS
    ansible.builtin.debug:
      msg: "OS: {{ ansible_facts.distribution }} {{ ansible_facts.distribution_version }}"

  - name: Task only for Debian systems
    ansible.builtin.apt:
      name: nginx
      state: present
    when: ansible_facts.os_family == "Debian"
```

### Handlers
Handlers запускаются только после уведомления и только один раз в конце play:
```yaml
tasks:
  - name: Update nginx config
    ansible.builtin.template:
      src: nginx.conf.j2
      dest: /etc/nginx/nginx.conf
    notify: Reload nginx    # fires the handler IF this task changed

  - name: Update another nginx file
    ansible.builtin.copy:
      src: mime.types
      dest: /etc/nginx/mime.types
    notify: Reload nginx    # same handler, still only fires once

handlers:
  - name: Reload nginx
    ansible.builtin.service:
      name: nginx
      state: reloaded
```

## Примеры

### Playbook для настройки nginx
```yaml
---
- name: Configure nginx web server
  hosts: webservers
  become: true

  vars:
    server_name: "{{ inventory_hostname }}"
    document_root: /var/www/html

  tasks:
    - name: Install nginx
      ansible.builtin.package:
        name: nginx
        state: present

    - name: Create document root
      ansible.builtin.file:
        path: "{{ document_root }}"
        state: directory
        owner: www-data
        group: www-data
        mode: "0755"

    - name: Deploy site config
      ansible.builtin.template:
        src: templates/site.conf.j2
        dest: /etc/nginx/sites-available/mysite.conf
      notify: Reload nginx

    - name: Enable site
      ansible.builtin.file:
        src: /etc/nginx/sites-available/mysite.conf
        dest: /etc/nginx/sites-enabled/mysite.conf
        state: link
      notify: Reload nginx

    - name: Ensure nginx is running
      ansible.builtin.service:
        name: nginx
        state: started
        enabled: true

  handlers:
    - name: Reload nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded
```

## Практические задания

1. Создайте inventory-файл с двумя группами (`webservers` и `databases`), указав хотя бы один узел в каждой. Выполните `ansible -i inventory.ini all -m ping`, чтобы проверить соединение. Затем запустите ad-hoc-команду `uptime` для одной из групп.
2. Напишите playbook, который устанавливает `nginx` на узлах группы `webservers`, обеспечивает запуск службы и её автозапуск, а также создаёт простой файл `index.html`. Сначала используйте режим `--check`, чтобы просмотреть предполагаемые изменения.
3. Добавьте задачу `template`, создающую конфигурацию nginx из шаблона Jinja2 и использующую переменную inventory для `server_name`. Используйте handler для перезагрузки nginx при изменении конфигурации.
4. Добавьте условную задачу установки `htop` в системах на базе Debian и RedHat (пакет одинаковый, менеджеры пакетов разные), используя условие `when: ansible_facts.os_family`.


---

### Быстрая проверка

5. Посчитайте задачи в примере Ansible play. Выполните: `printf '- name: Install nginx\n  apt:\n- name: Start nginx\n  service:\n- name: Copy config\n  template:\n' | grep -c '^- name:'`

```expected_output
3
```

Подсказка: найдите заданный шаблон в текстовом выводе и посчитайте число его вхождений.
Подсказка: используйте `grep -c`, чтобы посчитать строки, соответствующие шаблону `^- name:`, в выводе `printf`, переданном через конвейер.

6. Извлеките значение целевых узлов из play. Выполните: `printf '---\n- name: Deploy\n  hosts: webservers\n  become: true\n' | awk '/hosts:/{print $2}'`

```expected_output
webservers
```

Подсказка: найдите строку по ключевому слову и выведите нужное поле.
Подсказка: используйте `awk` с шаблоном `/hosts:/` и `print $2`, чтобы извлечь второе поле из найденной строки.
