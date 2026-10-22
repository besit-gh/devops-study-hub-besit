---
title: Плейбуки и inventory Ansible
module: ansible
duration_min: 20
difficulty: beginner
tags: [ansible, playbooks, inventory, tasks, modules, idempotent]
exercises: 4
---

## Обзор

Ansible автоматизирует управление конфигурацией и развёртывание приложений сразу на множестве серверов через SSH, без установки агента на управляемых узлах. **Плейбук (playbook)** описывает, что нужно сделать, а **inventory** — на каких узлах это выполнить. Все операции запускаются с управляющего узла — например, ноутбука или CI-сервера, — который передаёт изменения по SSH. В уроке разбираются основы обоих компонентов.

## Основные понятия

### Основные принципы
- **Без агентов** — на управляемых узлах нужны только SSH и Python
- **Идемпотентность** — повторный запуск плейбука приводит к тому же результату без нежелательных побочных эффектов
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

[production:children]  # группа групп
webservers
databases

[all:vars]  # переменные для всех узлов
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

# Выполнить разовую команду
ansible -i inventory.ini webservers -m shell -a "uptime"
ansible -i inventory.ini all -m shell -a "df -h" -b   # -b: повысить привилегии (sudo)
```

### Структура плейбука

```yaml
# deploy.yml
---
- name: Развернуть веб-приложение
  hosts: webservers                   # целевые узлы или группа
  become: true                        # использовать sudo для всех задач
  vars:
    app_version: "1.2.3"
    app_dir: /opt/myapp

  tasks:
    - name: Убедиться, что nginx установлен
      ansible.builtin.package:
        name: nginx
        state: present                # present = установлен, absent = удалён

    - name: Убедиться, что nginx запущен и включён в автозапуск
      ansible.builtin.service:
        name: nginx
        state: started
        enabled: true

    - name: Скопировать конфигурацию приложения
      ansible.builtin.template:
        src: templates/nginx.conf.j2
        dest: /etc/nginx/sites-enabled/myapp.conf
        owner: root
        group: root
        mode: "0644"
      notify: Перезагрузить nginx     # запускает обработчик

  handlers:
    - name: Перезагрузить nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded
```

```bash
# Запустить плейбук
ansible-playbook -i inventory.ini deploy.yml

# Пробный запуск: показать предполагаемые изменения
ansible-playbook -i inventory.ini deploy.yml --check

# Ограничить выполнение выбранными узлами
ansible-playbook -i inventory.ini deploy.yml --limit web01.example.com

# Подробный вывод
ansible-playbook -i inventory.ini deploy.yml -v    # -vvv — максимальная подробность
```

### Основные модули

```yaml
tasks:
  # Управление пакетами
  - name: Установить пакеты
    ansible.builtin.package:         # автоматически выбирает apt/yum/dnf
      name: [nginx, curl, git]
      state: present

  - name: Установить определённые пакеты apt
    ansible.builtin.apt:
      name: nginx=1.24.0*
      update_cache: true             # сначала выполнить apt-get update

  # Операции с файлами
  - name: Создать каталог
    ansible.builtin.file:
      path: /opt/myapp
      state: directory               # file, directory, absent, link
      owner: myapp
      group: myapp
      mode: "0755"

  - name: Скопировать файл
    ansible.builtin.copy:
      src: files/app.conf            # путь относительно плейбука
      dest: /etc/myapp/app.conf
      mode: "0644"

  - name: Создать файл из шаблона
    ansible.builtin.template:
      src: templates/config.j2       # шаблон Jinja2
      dest: /etc/myapp/config.conf

  # Команды
  - name: Выполнить команду
    ansible.builtin.command:
      cmd: /opt/myapp/bin/migrate
      creates: /opt/myapp/.migrated  # пропустить задачу, если файл существует (идемпотентность)

  - name: Выполнить команду оболочки (поддерживает конвейеры и перенаправления)
    ansible.builtin.shell:
      cmd: "ps aux | grep nginx | grep -v grep"

  # Пользователи
  - name: Создать пользователя
    ansible.builtin.user:
      name: myapp
      shell: /bin/bash
      groups: [myapp, docker]
      create_home: true

  # Git
  - name: Клонировать или обновить репозиторий
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
  - name: Собрать факты о системе
    ansible.builtin.setup:    # запускается автоматически в начале play

  - name: Вывести информацию об ОС
    ansible.builtin.debug:
      msg: "ОС: {{ ansible_facts.distribution }} {{ ansible_facts.distribution_version }}"

  - name: Задача только для систем Debian
    ansible.builtin.apt:
      name: nginx
      state: present
    when: ansible_facts.os_family == "Debian"
```

### Обработчики (handlers)

Обработчики запускаются только после уведомления и только один раз в конце play:

```yaml
tasks:
  - name: Обновить конфигурацию nginx
    ansible.builtin.template:
      src: nginx.conf.j2
      dest: /etc/nginx/nginx.conf
    notify: Перезагрузить nginx    # запускает обработчик, только если задача внесла изменения

  - name: Обновить ещё один файл nginx
    ansible.builtin.copy:
      src: mime.types
      dest: /etc/nginx/mime.types
    notify: Перезагрузить nginx    # тот же обработчик запустится всё равно только один раз

handlers:
  - name: Перезагрузить nginx
    ansible.builtin.service:
      name: nginx
      state: reloaded
```

## Примеры

### Плейбук для настройки nginx

```yaml
---
- name: Настроить веб-сервер nginx
  hosts: webservers
  become: true

  vars:
    server_name: "{{ inventory_hostname }}"
    document_root: /var/www/html

  tasks:
    - name: Установить nginx
      ansible.builtin.package:
        name: nginx
        state: present

    - name: Создать корневой каталог сайта
      ansible.builtin.file:
        path: "{{ document_root }}"
        state: directory
        owner: www-data
        group: www-data
        mode: "0755"

    - name: Развернуть конфигурацию сайта
      ansible.builtin.template:
        src: templates/site.conf.j2
        dest: /etc/nginx/sites-available/mysite.conf
      notify: Перезагрузить nginx

    - name: Включить сайт
      ansible.builtin.file:
        src: /etc/nginx/sites-available/mysite.conf
        dest: /etc/nginx/sites-enabled/mysite.conf
        state: link
      notify: Перезагрузить nginx

    - name: Убедиться, что nginx запущен
      ansible.builtin.service:
        name: nginx
        state: started
        enabled: true

  handlers:
    - name: Перезагрузить nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded
```

## Практические задания

1. Создайте inventory-файл с двумя группами (`webservers` и `databases`), указав хотя бы один узел в каждой. Выполните `ansible -i inventory.ini all -m ping`, чтобы проверить соединение. Затем запустите разовую команду `uptime` для одной из групп.
2. Напишите плейбук, который устанавливает `nginx` на узлах группы `webservers`, обеспечивает запуск службы и её автозапуск, а также создаёт простой файл `index.html`. Сначала используйте режим `--check`, чтобы просмотреть предполагаемые изменения.
3. Добавьте задачу `template`, создающую конфигурацию nginx из шаблона Jinja2 и использующую переменную inventory для `server_name`. Используйте обработчик для перезагрузки nginx при изменении конфигурации.
4. Добавьте условную задачу установки `htop` в системах на базе Debian и RedHat (пакет одинаковый, менеджеры пакетов разные), используя условие `when: ansible_facts.os_family`.

---

### Быстрая проверка

5. Посчитайте задачи в примере Ansible play. Выполните: `printf '- name: Install nginx\\n  apt:\\n- name: Start nginx\\n  service:\\n- name: Copy config\\n  template:\\n' | grep -c '^- name:'`

```expected_output
3
```

Подсказка: найдите заданный шаблон в текстовом выводе и посчитайте число его вхождений.
Подсказка: используйте `grep -c`, чтобы посчитать строки, соответствующие шаблону `^- name:`, в выводе `printf`, переданном через конвейер.

6. Извлеките значение целевых узлов из play. Выполните: `printf '---\\n- name: Deploy\\n  hosts: webservers\\n  become: true\\n' | awk '/hosts:/{print $2}'`

```expected_output
webservers
```

Подсказка: найдите строку по ключевому слову и выведите нужное поле.
Подсказка: используйте `awk` с шаблоном `/hosts:/` и `print $2`, чтобы извлечь второе поле из найденной строки.
