---
title: Docker Compose — запуск многоконтейнерных приложений
module: docker
duration_min: 20
difficulty: intermediate
tags: [docker, compose, multi-container, networking, volumes, services]
exercises: 4
---

## Обзор
Docker Compose описывает и запускает приложения из нескольких контейнеров с помощью одного YAML-файла. Вместо запоминания множества команд `docker run` вы декларативно описываете весь стек — приложение, базу данных, кэш и reverse proxy — и запускаете его одной командой. Это стандартный инструмент для локальной разработки и несложных production-развёртываний.

## Основные понятия

### Структура compose.yaml
```yaml
# compose.yaml (ранее docker-compose.yml; допустимы оба имени)
services:
  web:
    image: nginx:1.25
    ports:
      - "8080:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - app

  app:
    build: .                  # собрать образ по Dockerfile в текущем каталоге
    environment:
      - DB_HOST=db
      - DB_PORT=5432
      - DB_PASSWORD=${DB_PASSWORD}   # из файла .env или переменной окружения оболочки
    depends_on:
      db:
        condition: service_healthy  # дождаться успешной проверки состояния
        restart: true               # перезапустить приложение, если перезапустилась БД (Compose 2.17+)

  db:
    image: postgres:17
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data   # именованный том
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U myuser"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:   # именованный томs persist across container restarts
```

### Основные команды
```bash
# Запустить все сервисы в фоне
docker compose up -d

# Сначала пересобрать образы и запустить сервисы
docker compose up -d --build

# Остановить сервисы (контейнеры останутся, данные сохранятся)
docker compose stop

# Остановить и удалить контейнеры (данные в именованных томах сохранятся)
docker compose down

# Остановить и удалить контейнеры И именованные тома (данные будут удалены)
docker compose down -v

# Показать запущенные сервисы
docker compose ps

# Следить за журналами всех сервисов
docker compose logs -f

# Следить за журналом одного сервиса
docker compose logs -f app

# Выполнить разовую команду внутри сервиса
docker compose exec app bash
docker compose exec db psql -U myuser myapp

# Перезапустить один сервис
docker compose restart app

# Загрузить последние версии образов
docker compose pull

# Масштабировать сервис (запустить несколько реплик)
docker compose up -d --scale app=3
```

### Сетевое взаимодействие
Compose создаёт сеть по умолчанию с именем `<project>_default`. Все сервисы в этой сети могут обращаться друг к другу по **имени сервиса**:

```python
# В коде приложения подключайтесь к базе данных по имени сервиса:
import psycopg2
conn = psycopg2.connect(host="db", port=5432, dbname="myapp")
```

IP-адреса указывать не нужно: Compose автоматически обеспечивает DNS-разрешение имён внутри своей сети.

Пользовательские сети для изоляции сервисов:
```yaml
services:
  web:
    networks: [frontend, backend]
  app:
    networks: [backend]
  db:
    networks: [backend]

networks:
  frontend:
  backend:
    internal: true   # без доступа в интернет
```

### Тома
```yaml
services:
  app:
    volumes:
      # Именованный том (управляется Docker и сохраняется между down/up)
      - app_data:/var/app/data

      # Bind mount (путь на хосте : путь в контейнере)
      - ./src:/app/src

      # Bind mount только для чтения
      - ./config:/etc/app/config:ro

volumes:
  app_data:
    # external: true ← использовать существующий том (Compose его не создаёт)
```

**Bind mount** удобен для разработки: изменения кода на хосте сразу видны в контейнере, пересобирать образ не требуется.

### Переменные окружения
```yaml
# Способ 1: список строк
environment:
  - DB_HOST=db
  - APP_ENV=development

# Способ 2: отображение ключей и значений (нагляднее)
environment:
  DB_HOST: db
  APP_ENV: development

# Способ 3: переменная из окружения оболочки (без значения — взять его из окружения)
environment:
  - SECRET_KEY

# Способ 4: env_file (загрузить переменные из файла)
env_file:
  - .env
  - .env.local   # переопределяет значения из .env
```

Файл `.env` (загружается автоматически, если находится в том же каталоге, что и `compose.yaml`):
```
DB_PASSWORD=supersecret
APP_ENV=development
```

### Профили
```yaml
# Назначить сервисам профили, чтобы запускать их выборочно
services:
  app:
    image: myapp:latest

  db:
    image: postgres:17

  pgadmin:
    image: dpage/pgadmin4
    profiles: [tools]   # запускается только при использовании --profile tools
```

```bash
docker compose up -d                    # запустить только app и db
docker compose up -d --profile tools   # запустить все сервисы, включая pgadmin
```

### Проверки состояния и зависимости
```yaml
db:
  image: postgres:17
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U myuser"]
    interval: 5s
    timeout: 3s
    retries: 5
    start_period: 10s   # период ожидания перед началом проверки состояния

app:
  depends_on:
    db:
      condition: service_healthy   # не запускать, пока БД не будет готова
      restart: true                # перезапустить приложение, если перезапустилась БД (Compose 2.17+)
```

## Примеры

### Полный стек разработки
```yaml
# compose.yaml
services:
  nginx:
    image: nginx:1.25-alpine
    ports: ["80:80"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on: [api]

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    volumes:
      - ./backend:/app   # изменения кода сразу видны в контейнере при разработке
    environment:
      - DATABASE_URL=postgresql://user:${DB_PASS}@db:5432/myapp
      - REDIS_URL=redis://redis:6379
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started

  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: ${DB_PASS}
      POSTGRES_DB: myapp
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user"]
      interval: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

## Практические задания

1. Создайте `compose.yaml`, запускающий приложение FastAPI (сборка из локального Dockerfile) и базу данных PostgreSQL. Приложение должно подключаться к БД по имени сервиса. Запустите стек и убедитесь, что оба контейнера работают.
2. Добавьте в стек сервис Redis. Для Redis укажите в `depends_on` условие `service_started`, а для базы данных — `service_healthy`.
3. Добавьте сервису PostgreSQL проверку состояния с помощью `pg_isready`. Проверьте её, выполнив `docker compose ps` и изучив столбец состояния.
4. Сохраните пароль базы данных в файле `.env` и укажите в `compose.yaml` ссылку `${DB_PASSWORD}`. Убедитесь, что переменная попала в контейнер: `docker compose exec db env | grep POSTGRES_PASSWORD`.

---

### Быстрая проверка

5. Посчитайте определения сервисов в примере Compose YAML. Выполните: `printf 'services:\n  web:\n    image: nginx\n  db:\n    image: postgres\n  cache:\n    image: redis\n' | awk '/^  [a-z]/ && !/^    /{c++} END{print c}'`

```expected_output
3
```

Подсказка: отфильтруйте строки по уровню отступа, чтобы найти имена сервисов верхнего уровня, затем посчитайте совпадения.
Подсказка: используйте `awk` с шаблоном `/^  [a-z]/` и исключите более глубокий отступ через `!/^    /`. Увеличивайте счётчик и выводите его в блоке `END`.

6. Извлеките порт контейнера из строки сопоставления портов. Выполните: `echo "8080:80" | cut -d: -f2`

```expected_output
80
```

Подсказка: разделите строку по разделителю, чтобы извлечь нужное поле.
Подсказка: используйте `cut`, задайте `:` разделителем через `-d`, а второе поле выберите флагом `-f2`.
