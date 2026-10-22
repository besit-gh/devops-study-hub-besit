---
title: Многоэтапная сборка Docker
module: docker
duration_min: 15
difficulty: intermediate
tags: [docker, multi-stage, dockerfile, optimization, build]
exercises: 4
---

## Обзор

Многоэтапная сборка решает одну из давних проблем контейнеризации: инструменты, необходимые для *сборки* ПО, почти никогда не нужны для его *запуска*. До появления multi-stage builds команды использовали отдельные Dockerfile для CI и production либо собирали приложение вне Docker и копировали артефакты внутрь. Оба подхода ухудшали воспроизводимость. Многоэтапная сборка объединяет установку зависимостей, компиляцию, тестирование и упаковку в одном Dockerfile, чётко разделяя этапы сборки и выполнения.

Основной принцип — **перенос артефактов**: каждый этап создаёт результат, а следующие этапы забирают только нужные файлы через `COPY --from`. Промежуточные слои — компиляторы, тестовые фреймворки, исходные архивы и объектные файлы — автоматически исключаются из финального образа. Это важно не только для размера, но и для безопасности: production-образ без shell, менеджера пакетов и исходного кода имеет значительно меньшую поверхность атаки.

В DevOps многоэтапная сборка находится на пересечении CI/CD и безопасности контейнеров. Один вызов `docker build` может включать установку зависимостей, компиляцию, тесты и упаковку. Флаг `--target` позволяет CI остановиться на нужном этапе: например, выполнить тесты в одной job, а затем отправить production-образ в registry — без отдельных Dockerfile. Вместе с кэшированием слоёв и аргументами сборки это делает процесс быстрым и проверяемым.

---

## Основные понятия

### Какую проблему решает многоэтапная сборка

Без многоэтапной сборки простой Dockerfile включает в финальный образ всё, что использовалось в процессе сборки.

```dockerfile
# Single-stage: everything ends up in the image
FROM node:20
WORKDIR /app
COPY package*.json ./
RUN npm ci                  # installs devDependencies too
COPY . .
RUN npm run build
# Image contains: Node.js runtime, npm, ALL node_modules (including dev),
# source code, TypeScript compiler, test runners, build output
# Typical size: 1.0–1.4 GB
```

Многоэтапная сборка разделяет задачи по отдельным блокам `FROM`. Между этапами переносятся только файлы, явно указанные в `COPY --from`.

```dockerfile
# Stage 1: build — has everything the compiler needs
FROM node:20 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: production — starts from scratch, takes only the output
FROM nginx:1.25-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# Image contains: nginx + static files only
# Typical size: 20–30 MB
```

**Промежуточные этапы не попадают в финальный образ.** Docker собирает их по порядку, использует как источник для `COPY --from`, а затем исключает их слои из финального результата. Это не сжатие: эти слои просто не записываются в выходной образ.

---

### Синтаксис и ссылки на этапы

```dockerfile
# Name a stage with AS <name> — names are lowercase by convention
FROM golang:1.24-alpine AS builder

# Reference a previous stage by name
COPY --from=builder /app/binary /binary

# Reference a previous stage by zero-based index (fragile — avoid)
COPY --from=0 /app/binary /binary

# Reference an external image directly — no prior stage needed
# Docker pulls the image just to copy files from it
COPY --from=alpine:3.19 /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
```

| Тип ссылки | Пример | Когда использовать |
|---|---|---|
| Именованный этап | `--from=builder` | Предпочтительный вариант: понятный и устойчивый к рефакторингу |
| Индекс | `--from=0` | Лучше избегать: перестановка этапов может незаметно сломать сборку |
| Внешний образ | `--from=alpine:3.19` | Копирование известных файлов (сертификатов, бинарников) без объявления этапа |

**Имена этапов действуют в пределах одного Dockerfile.** В двух разных Dockerfile может быть этап `builder` — конфликтов не будет. Имена должны быть допустимыми идентификаторами (буквы, цифры и дефисы; по принятому соглашению без подчёркиваний).

**Несколько инструкций `FROM` могут ссылаться на один базовый образ под разными именами.** Это обычная практика: например, этапы `test` и `builder` могут начинаться с общего этапа `deps`, используя один кэшированный слой зависимостей.

---

### Аргументы сборки между этапами

Значения `ARG` не передаются автоматически между этапами. Каждый этап, которому нужен аргумент, должен объявить его повторно.

```dockerfile
# Declare at the top: available before the first FROM (e.g., to pin base image versions)
ARG BUILD_VERSION=dev

FROM node:20-alpine AS builder
# Re-declare to pull the value into this stage's scope
ARG BUILD_VERSION
RUN echo "Building version: $BUILD_VERSION" \
    && echo "$BUILD_VERSION" > /app/version.txt

FROM node:20-alpine AS runner
# Re-declare again — each stage is isolated
ARG BUILD_VERSION
ENV APP_VERSION=$BUILD_VERSION
COPY --from=builder /app/version.txt ./version.txt
```

```bash
# Pass the argument at build time
docker build --build-arg BUILD_VERSION=1.4.2 -t myapp:1.4.2 .
```

**ARG и ENV между этапами:** значения `ARG` существуют только во время сборки и отсутствуют в запущенном контейнере. Значения `ENV` доступны и во время выполнения. Если значение нужно на обоих этапах, присвойте его `ENV` внутри этапа: `ENV APP_VERSION=$BUILD_VERSION`.

**Безопасность:** значения `ARG`, включая секреты вроде API-ключей, видны в `docker history`. Никогда не передавайте секреты через `ARG`; используйте secret mounts Docker BuildKit (`--mount=type=secret`).

```bash
# Correct pattern for secrets with BuildKit
# In Dockerfile:
# RUN --mount=type=secret,id=npmrc,target=/root/.npmrc npm ci
docker build --secret id=npmrc,src=$HOME/.npmrc -t myapp .
```

---

### Выбор конкретного этапа

Флаг `--target` останавливает сборку на указанном этапе и сохраняет его образ. Все предыдущие этапы собираются как обычно, последующие пропускаются.

```bash
# Build only the 'builder' stage — useful for caching dependency layers in CI
docker build --target builder -t myapp:deps .

# Build the 'test' stage — runs tests, fails the build if they fail
docker build --target test -t myapp:test .

# Build the final production image
docker build --target production -t myapp:latest .
```

Этот подход удобно соответствует этапам CI-конвейера:

```yaml
# GitLab CI — test and build as separate jobs sharing the registry cache
stages:
  - test
  - build

run-tests:
  stage: test
  script:
    - docker build --target test -t $CI_REGISTRY_IMAGE:test-$CI_COMMIT_SHA .

build-image:
  stage: build
  script:
    - docker build --target production -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
  needs: [run-tests]
```

**Без `--target` Docker собирает все этапы, но выдаёт только финальный образ.** Промежуточные этапы кэшируются, поэтому последующие сборки повторно используют их слои. Именно поэтому сборка `--target test`, а затем `--target production` выполняется быстро: общие слои уже в кэше.

---

### Шаблон этапа тестирования

Если включить тесты в Dockerfile, они выполняются в том же окружении, что и сборка. При провале тестов образ не создаётся.

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS test
# Install dev/test deps on top of base — not in production
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
RUN pytest --tb=short -q   # RUN fails the layer if pytest exits non-zero

FROM base AS production
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# In CI — fail fast if tests fail
docker build --target test .

# If the above succeeds, build the production image
docker build --target production -t myapp:latest .
```

**Если `RUN pytest` завершается с ошибкой, вся команда `docker build` возвращает ненулевой код.** CI фиксирует провал сборки и останавливает конвейер. Production-образ не получает тег и не отправляется в registry. Это ожидаемое поведение, а не ошибка, которую нужно обходить.

**Этап тестирования использует общие слои с production через этап `base`.** `pip install -r requirements.txt` выполняется один раз и кэшируется. Только dev-зависимости и запуск тестов относятся исключительно к тестовому этапу. Это ускоряет CI и исключает дублирование работы.

---

### Стратегия кэширования слоёв

В многоэтапной сборке кэш слоёв работает так же, как в одноэтапной: слой становится недействительным, если изменяется его инструкция или любая предыдущая. В многоэтапных сборках особенно важно правильно организовать кэш, поскольку слоёв больше и выше риск случайно сбросить кэш.

```dockerfile
FROM golang:1.24-alpine AS builder
WORKDIR /app

# Copy dependency manifests FIRST — these change rarely
# Docker caches the `go mod download` layer until go.mod/go.sum change
COPY go.mod go.sum ./
RUN go mod download

# Copy source AFTER — this layer invalidates on every code change,
# but the dependency layer above stays cached
COPY . .
RUN CGO_ENABLED=0 go build -o server ./cmd/server
```

**Типичная ошибка, сбрасывающая кэш:** `COPY . .` перед установкой зависимостей. Изменение любого исходного файла делает слой установки зависимостей недействительным и заставляет повторно выполнять `npm ci` или `go mod download` при каждой сборке.

| Что изменилось | Какие слои пересобираются |
|---|---|
| Только исходный код | `COPY . .` и все последующие слои |
| `go.sum` / `package-lock.json` | Установка зависимостей и все последующие слои |
| Обновился базовый образ | Все слои этого этапа |
| Изменилась любая инструкция | Этот слой и все последующие |
| Ничего не изменилось | Полное попадание в кэш — почти мгновенная сборка |

**Cache mounts BuildKit** сохраняют каталог между сборками, не добавляя его в слой образа. Это идеально подходит для кэша менеджеров пакетов:

```dockerfile
# --mount=type=cache persists /root/.cache across builds
# The cache is never written into the image layer
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt
```

---

### Выбор базового образа финального этапа

Выбор базового образа финального этапа определяет поверхность атаки, размер образа и эксплуатационные характеристики контейнера.

| Базовый образ | Примерный размер | Shell | Менеджер пакетов | Применение |
|---|---|---|---|---|
| `scratch` | 0 MB | No | No | Fully static Go/Rust binaries |
| `alpine:3.x` | ~7 MB | sh (busybox) | apk | Small images that still need a shell |
| `debian:bookworm-slim` | ~75 MB | bash | apt | Apps needing glibc or common libs |
| `ubuntu:24.04` | ~80 MB | bash | apt | Familiarity, large ecosystem |
| `gcr.io/distroless/base` | ~20 MB | No | No | Non-Go apps without a shell |
| `gcr.io/distroless/java21` | ~220 MB | No | No | Java apps, minimal JRE, no shell |
| Language `-slim` variants | Varies | bash | apt (limited) | Python/Ruby/Node with minimal OS |

**Особенность `scratch`:** бинарный файл в `scratch` должен быть полностью статически слинкован. Зависимость от динамической библиотеки (включая glibc) приведёт к ошибке выполнения `no such file or directory`, которая неочевидно указывает на отсутствие разделяемой библиотеки. Для Go задайте `CGO_ENABLED=0`. Для Rust используйте target `musl`. Для языков, использующих glibc (C, C++, Rust по умолчанию), выберите `distroless/base` или `alpine`.

**Особенность `alpine`:** Alpine использует libc `musl`, а не `glibc`. Большинство бинарников Go и Rust работают нормально, но C-расширения Python и некоторые нативные модули Node.js могут вести себя иначе или требовать пересборки. Если загадочная ошибка возникает только в Alpine, проверьте несовместимость musl/glibc. Возможное решение — перейти на `debian-slim` или `distroless`.

**Distroless-образы** не содержат shell, менеджера пакетов и coreutils — только runtime языка и его зависимости. Это существенно уменьшает поверхность атаки, но ограничивает отладку через `docker exec`. В таких случаях используйте sidecar-контейнер для диагностики или `docker debug` (Docker Desktop 4.27+).

---

### Обработка сигналов и PID 1

Важная эксплуатационная деталь: процесс, запущенный через `CMD` или `ENTRYPOINT` в exec-форме, становится PID 1 контейнера и напрямую получает сигналы (например, SIGTERM для корректного завершения). При shell-форме PID 1 становится shell, который может не передавать сигналы приложению.

```dockerfile
# Shell form — sh becomes PID 1, your app is a child process
# SIGTERM goes to sh, not your app; graceful shutdown may not work
CMD uvicorn main:app --host 0.0.0.0 --port 8000

# Exec form — your app is PID 1, receives SIGTERM directly
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**В финальном этапе многоэтапной сборки всегда используйте exec-форму (`["cmd", "arg"]`).** Это особенно важно в Kubernetes: при завершении pod отправляется SIGTERM, после чего система ждёт `terminationGracePeriodSeconds` перед SIGKILL.

---

## Примеры

### Пример 1. REST API на Go в образе `scratch`

Полный пример HTTP-сервера на Go, выполняющего исходящие HTTPS-запросы. Финальный образ занимает около 8 МБ.

```dockerfile
# syntax=docker/dockerfile:1

FROM golang:1.24-alpine AS builder
WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .

# CGO_ENABLED=0: static binary, no C dependencies
# -ldflags="-s -w": strip debug symbols (~30% smaller binary)
# -trimpath: remove local build paths from binary (reproducibility + security)
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -trimpath -o /server ./cmd/server

# ---- Test stage ----
FROM builder AS test
RUN go test ./... -v

# ---- Final stage ----
FROM scratch AS production
# CA certificates — required for TLS verification in outbound HTTPS calls
# scratch has no filesystem at all, so we pull certs from Alpine
COPY --from=alpine:3.19 /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
# /etc/passwd — needed if your app calls os/user or reads the current user
COPY --from=alpine:3.19 /etc/passwd /etc/passwd
COPY --from=builder /server /server
EXPOSE 8080
ENTRYPOINT ["/server"]
```

```bash
# Run tests first — build fails here if any test fails
docker build --target test .

# Build the production image
docker build --target production -t goapi:latest .

# Verify size
docker images goapi
# REPOSITORY   TAG       IMAGE ID       CREATED         SIZE
# goapi        latest    a3f9b2c1d4e7   3 seconds ago   8.12MB

# Run and verify
docker run -d -p 8080:8080 --name goapi goapi:latest
curl -s http://localhost:8080/healthz

# Confirm there is no shell — expected behavior for scratch images
docker exec goapi sh 2>&1
# OCI runtime exec failed: exec: "sh": executable file not found in $PATH

# Clean up
docker stop goapi && docker rm goapi
```

---

### Пример 2. Spring Boot на Java и Maven

Отделяет кэширование зависимостей Maven от компиляции исходников. Значительно сокращает время пересборки CI при изменении только исходного кода.

```dockerfile
# syntax=docker/dockerfile:1

FROM maven:3.9-eclipse-temurin-21 AS deps
WORKDIR /app
# Copy only the POM first — `mvn dependency:go-offline` downloads all deps
# This layer is reused as long as pom.xml doesn't change
COPY pom.xml .
RUN mvn dependency:go-offline -q

FROM deps AS builder
# Source copy invalidates only compile layers, not the dep download layer
COPY src ./src
RUN mvn package -DskipTests -q

FROM deps AS test
COPY src ./src
# Full test suite — fails the build if any test fails
RUN mvn test -q

FROM eclipse-temurin:21-jre-alpine AS production
WORKDIR /app
# Copy only the fat jar — no Maven, no JDK, no source code
COPY --from=builder /app/target/*.jar app.jar
EXPOSE 8080
# Exec form for correct signal handling
# UseContainerSupport: JVM reads cgroup memory limits (not host memory)
# MaxRAMPercentage: use 75% of container memory limit for heap
ENTRYPOINT ["java", \
  "-XX:+UseContainerSupport", \
  "-XX:MaxRAMPercentage=75.0", \
  "-jar", "app.jar"]
```

```bash
# Run tests
docker build --target test -t myapp:test .

# Build production image
docker build --target production -t myapp:latest .

# Verify JRE only — no JDK, no Maven
docker run --rm myapp:latest java -version    # JRE present
docker run --rm myapp:latest mvn -version 2>&1 | grep -i "not found"
# sh: mvn: not found

# Size comparison
docker images myapp
# myapp   latest   ...   ~130 MB   (vs ~660 MB for full Maven image)
```

| Stage | Base image | Purpose |
|---|---|---|
| `deps` | `maven:3.9-eclipse-temurin-21` | Cached dependency download layer |
| `builder` | inherits `deps` | Compile source into fat jar |
| `test` | inherits `deps` | Run full test suite |
| `production` | `eclipse-temurin:21-jre-alpine` | Runtime only (~130 MB) |

---

### Пример 3. Трёхэтапная сборка Node.js (зависимости / сборка / production)

Показывает, как разделить установку production-зависимостей, транспиляцию и создание финального runtime-образа, чтобы в production попадало только необходимое.

```dockerfile
# syntax=docker/dockerfile:1

FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
# --omit=dev: install only production dependencies
# This layer is stable — only changes when production deps change
RUN npm ci --omit=dev

FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
# Full install including devDependencies (TypeScript, bundler, etc.)
RUN npm ci
COPY . .
# Produces /app/dist — compiled and bundled JS output
RUN npm run build

FROM node:20-alpine AS test
WORKDIR /app
# Reuse the full node_modules from builder — no reinstall needed
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY . .
RUN npm test

FROM node:20-alpine AS production
WORKDIR /app
ENV NODE_ENV=production
# Production deps only — no TypeScript, Jest, webpack, or source maps
COPY --from=deps /app/node_modules ./node_modules
# Compiled output only — no .ts source files
COPY --from=builder /app/dist ./dist
COPY package.json .
EXPOSE 3000
# node directly as PID 1 — avoid npm as PID 1 (npm does not forward SIGTERM)
CMD ["node", "dist/server.js"]
```

```bash
# Run the full pipeline
docker build --target test -t myapp:test .
docker build --target production -t myapp:latest .

# Verify no dev dependencies shipped
docker run --rm myapp:latest node -e "require('typescript')" 2>&1
# Error: Cannot find module 'typescript' — correct, TypeScript is not in production

# Check size difference
docker images myapp
# myapp   latest   ...   ~120 MB   (vs ~1.1 GB with all dev deps)

# Run the service
docker run -d -p 3000:3000 --name nodeapp myapp:latest
curl -s http://localhost:3000/healthz
docker stop nodeapp && docker rm nodeapp
```

---

### Пример 4. Статический фронтенд React, обслуживаемый Nginx

Собирает приложение React и отдаёт через Nginx только скомпилированные статические файлы, используя встроенную пользовательскую конфигурацию.

```dockerfile
# syntax=docker/dockerfile:1

FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# VITE_API_URL is a build-time variable baked into the JS bundle
ARG VITE_API_URL=http://localhost:8080
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build   # outputs to /app/dist

FROM node:20-alpine AS test
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY . .
RUN npm run test -- --run   # Vitest: --run exits after one pass

FROM nginx:1.25-alpine AS production
# Remove the default nginx config
RUN rm /etc/nginx/conf.d/default.conf
# Copy custom config — handles SPA routing (try_files fallback to index.html)
COPY nginx.conf /etc/nginx/conf.d/app.conf
# Copy compiled assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
# Nginx default CMD runs as PID 1 in foreground — correct behavior
```

```nginx
# nginx.conf — placed at repo root alongside Dockerfile
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # SPA routing: unknown paths fall back to index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets aggressively — Vite adds content hashes to filenames
    location ~* \.(js|css|png|jpg|svg|ico|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
# Build with a specific API URL
docker build \
  --target test . &&
docker build \
  --build-arg VITE_API_URL=https://api.example.com \
  --target production \
  -t frontend:latest .

# Verify the bundle references the correct API URL
docker run --rm frontend:latest grep -r "api.example.com" /usr/share/nginx/html/assets/

# Run and test SPA routing
docker run -d -p 8080:80 --name frontend frontend:latest
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/some/nested/route
# 200 — nginx returns index.html for all unmatched paths

docker stop frontend && docker rm frontend
```

---

## Практические задания

### Задание 1: оценить эффект многоэтапной сборки

**Цель:** измерить разницу в размере и содержимом одноэтапного и многоэтапного образов реального приложения.

1. Выберите знакомый язык (Node.js, Python или Go). Напишите минимальный, но работающий HTTP-сервер с эндпоинтом `/healthz`.
2. Напишите **одноэтапный Dockerfile**, который устанавливает все зависимости, включая dev-зависимости, и запускает сервер. Соберите образ и запишите его размер с помощью `docker images`.
3. Write a **multi-stage Dockerfile** with at least a `builder` stage and a minimal final stage. Build it and record the image size.
4. Use `docker history <image>` on both images to inspect the layer breakdown.
5. Run `docker run --rm <image> sh -c "find / -name '*.ts' 2>/dev/null | head -20"` (or equivalent for your language's source extension) on the production image. Confirm no source files are present.

**Deliverable:** A written comparison of image sizes and a list of what was eliminated from the production image.

---

### Задание 2: встроить тесты в конвейер сборки

**Цель:** использовать этап тестирования, чтобы ошибка тестов блокировала создание образа.

1. Take an existing project or create a new one with at least one unit test.
2. Write a multi-stage Dockerfile with a `test` stage that runs the test suite. Ensure the `RUN` command for tests exits non-zero on failure.
3. Intentionally break a test (introduce a bug in the source code).
4. Run `docker build --target test .` and confirm the build fails with a non-zero exit code.
5. Fix the bug, re-run the test build to confirm it passes, then build `--target production`.
6. **Bonus:** Wire this into a simple shell script that runs both steps sequentially and only tags the production image if the test build succeeds.

**Deliverable:** The Dockerfile and the shell script. Be prepared to explain why `RUN pytest` failing is more reliable than checking test output in a subsequent step.

---

### Задание 3: оптимизировать порядок слоёв при медленной установке зависимостей

**Цель:** показать разницу во времени сборки при удачном и неудачном порядке слоёв с точки зрения кэша.

1. Create a project with a `package.json` (or `requirements.txt`) that has at least 10 dependencies. Include a trivial source file.
2. Write a **cache-hostile Dockerfile** that does `COPY . .` before `RUN npm ci`. Build it twice, change only a comment in your source file, build again. Measure the time for the third build — notice the full `npm ci` re-runs.
3. Rewrite it with **cache-friendly ordering**: copy only the dependency manifest first, install, then copy source. Repeat the same experiment. Measure the third build time.
4. Use `docker build --progress=plain` to see per-layer timing and confirm which layers are `CACHED` in the second approach.

**Deliverable:** The two Dockerfiles and a written explanation of which layers are cached in each scenario and why.

---

### Задание 4: использовать `--target` в имитации CI-конвейера

**Цель:** реализовать локальный CI-конвейер из двух заданий с помощью `--target` и shell-скриптов.

1. Write a multi-stage Dockerfile with at least three stages: `builder`, `test`, and `production`.
2. Write a shell script `ci-test.sh` that:
   - Builds `--target test` and tags it as `myapp:test-$GIT_SHA` (use `$(git rev-parse --short HEAD)` or a fixed string if not in a git repo).
   - Exits non-zero if the build fails.
3. Write a second shell script `ci-publish.sh` that:
   - Calls `ci-test.sh` (or assumes it has already passed).
   - Builds `--target production` and tags it as `myapp:$GIT_SHA`.
   - Runs the production image briefly (`docker run --rm -d`, waits 2 seconds, hits the health endpoint with `curl`, stops the container).
   - Exits non-zero if the health check fails.
4. Run both scripts. Then modify `ci-publish.sh` to skip re-running tests (assume they passed in a prior job) and observe that the shared cache means the production build is near-instant.

**Deliverable:** Both shell scripts. Be prepared to explain how `--target` avoids rebuilding layers that were already built in the test job, and what the implications are for CI cache warming.

---

### Быстрая проверка

5. Extract stage aliases from a multi-stage Dockerfile. Run: `printf 'FROM golang:1.21 AS builder\nFROM gcr.io/distroless/static AS runtime\n' | awk '/AS/{print $NF}'`

```expected_output
builder
runtime
```

Подсказка: отфильтруйте строки с заданным ключевым словом и извлеките из каждой последнее слово.
Подсказка: используйте `awk` с шаблоном `AS` и выведите `$NF`, чтобы получить последнее поле каждой подходящей строки.

6. Count `FROM` instructions in a multi-stage Dockerfile stub. Run: `printf 'FROM node:20 AS deps\nFROM node:20 AS build\nFROM nginx:alpine\n' | grep -c '^FROM'`

```expected_output
3
```
Подсказка: отфильтруйте строки по шаблону и попросите shell автоматически посчитать совпадения.
Подсказка: используйте `grep -c`, чтобы посчитать строки, соответствующие шаблону `^FROM`, в переданном потоке.
