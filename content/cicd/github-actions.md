---
title: GitHub Actions
module: cicd
duration_min: 30
difficulty: intermediate
tags: [cicd, github-actions, workflows, runners, secrets, matrix, caching]
exercises: 4
---

## Обзор
GitHub Actions — встроенная в GitHub платформа CI/CD. Workflow-файлы хранятся в `.github/workflows/` и запускаются при push, pull request, по расписанию или вручную. Каждая job получает отдельный runner, а шаги внутри одной job используют общие файловую систему и окружение. Понимания модели job/step, кэширования и работы с секретами достаточно, чтобы строить production-пайплайны.

## Основные понятия

### Структура workflow
```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'        # every Monday at 06:00 UTC
  workflow_dispatch:             # allow manual trigger from the UI

jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        run: pytest --tb=short
```

### Исполнители (runner)
```yaml
# GitHub-hosted (бесплатный лимит для публичных репозиториев — 2000 минут в месяц)
runs-on: ubuntu-24.04
runs-on: ubuntu-22.04
runs-on: macos-14
runs-on: windows-2022

# Self-hosted (собственная машина, зарегистрированная как runner)
runs-on: self-hosted
runs-on: [self-hosted, linux, x64, gpu]
```

Self-hosted runner даёт контроль над оборудованием, программным обеспечением и сетевым доступом. Это полезно для работы с закрытой инфраструктурой или при необходимости специального оборудования.

### Секреты и переменные окружения
```yaml
jobs:
  deploy:
    runs-on: ubuntu-24.04
    env:
      APP_ENV: production         # workflow-level env var

    steps:
      - name: Deploy
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
        run: |
          aws s3 sync ./dist s3://my-bucket
```

Секреты настраиваются в **Settings → Secrets and variables → Actions**. В журналах их значения маскируются; из соображений безопасности секреты не передаются workflow, запущенным из форков.

### Кэширование
```yaml
- name: Cache pip packages
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-

- name: Cache Node modules
  uses: actions/cache@v4
  with:
    path: ~/.npm
    key: ${{ runner.os }}-node-${{ hashFiles('package-lock.json') }}
```

Ключ кэша включает хеш lock-файла — при изменении зависимостей кэш автоматически обновляется.

### Артефакты
```yaml
- name: Build
  run: npm run build

- name: Upload build artifact
  uses: actions/upload-artifact@v4
  with:
    name: dist
    path: dist/
    retention-days: 7

# В следующем задании: скачать артефакт
- uses: actions/download-artifact@v4
  with:
    name: dist
    path: ./dist
```

### Матричные сборки
```yaml
jobs:
  test:
    runs-on: ubuntu-24.04
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
        os: [ubuntu-24.04, macos-14]
      fail-fast: false   # don't cancel other matrix jobs on first failure
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
```

### Зависимости заданий
```yaml
jobs:
  test:
    runs-on: ubuntu-24.04
    steps: [...]

  build:
    needs: test          # only runs if 'test' passes
    runs-on: ubuntu-24.04
    steps: [...]

  deploy:
    needs: [test, build]   # waits for both
    runs-on: ubuntu-24.04
    steps: [...]
```

### Окружения и подтверждения
```yaml
jobs:
  deploy-prod:
    runs-on: ubuntu-24.04
    environment:
      name: production
      url: https://myapp.com   # shown in the GitHub UI
    steps:
      - run: ./deploy.sh
```

Настройте окружение `production` в **Settings → Environments**, чтобы перед запуском задания требовалось ручное подтверждение от выбранных проверяющих.

### Повторно используемые workflow
```yaml
# .github/workflows/reusable-test.yml
on:
  workflow_call:
    inputs:
      python-version:
        required: true
        type: string
    secrets:
      CODECOV_TOKEN:
        required: true

jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ inputs.python-version }}
```

```yaml
# Вызов из другого workflow:
jobs:
  run-tests:
    uses: ./.github/workflows/reusable-test.yml
    with:
      python-version: '3.12'
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

### Условные шаги
```yaml
- name: Deploy to prod
  if: github.ref == 'refs/heads/main' && github.event_name == 'push'
  run: ./deploy.sh

- name: Notify on failure
  if: failure()
  run: ./notify-slack.sh "Pipeline failed"

- name: Always clean up
  if: always()
  run: docker compose down
```

## Примеры

### Полный CI/CD-конвейер
```yaml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}

      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest --tb=short --cov=src --cov-report=xml
      - run: ruff check .

  build:
    needs: test
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: |
          docker build -t myapp:${{ github.sha }} .

      - name: Push to ECR
        if: github.ref == 'refs/heads/main'
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          aws ecr get-login-password --region us-east-1 \
            | docker login --username AWS --password-stdin ${{ secrets.ECR_REGISTRY }}
          docker tag myapp:${{ github.sha }} ${{ secrets.ECR_REGISTRY }}/myapp:${{ github.sha }}
          docker push ${{ secrets.ECR_REGISTRY }}/myapp:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-24.04
    environment: production
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to EKS
        env:
          KUBECONFIG_DATA: ${{ secrets.KUBECONFIG_BASE64 }}
        run: |
          echo "$KUBECONFIG_DATA" | base64 -d > ~/.kube/config
          kubectl set image deployment/myapp app=${{ secrets.ECR_REGISTRY }}/myapp:${{ github.sha }}
          kubectl rollout status deployment/myapp
```

## Практические задания

1. Напишите workflow, запускающийся при push в `main` и при создании pull request. Он должен запускать `pytest` для Python 3.11 и 3.12 в матрице. Используйте `actions/cache` для кэширования pip-пакетов с ключом на основе хеша `requirements.txt`.
2. Добавьте задание сборки и отправки Docker-образа, запускающееся только при push в `main`, но не при pull request. Отправляйте образ в GitHub Container Registry (`ghcr.io`), используя `GITHUB_TOKEN` для аутентификации. В качестве тега используйте SHA коммита.
3. Создайте задание развёртывания с ограничением `environment: production`, требующим ручного подтверждения. Оно должно запускаться только после успешного завершения тестов и сборки и только в ветке `main`.
4. Создайте повторно используемый workflow, принимающий `python-version` на вход и запускающий линтер и тесты. Вызовите его из основного workflow для двух версий Python.


---

### Быстрая проверка

5. Посчитайте задания в примере workflow. Выполните: `printf 'jobs:\n  build:\n    runs-on: ubuntu-latest\n  test:\n    runs-on: ubuntu-latest\n  deploy:\n    runs-on: ubuntu-latest\n' | awk '/^  [a-z]/ && !/^    /{c++} END{print c}'`

```expected_output
3
```

Подсказка: используйте сопоставление с шаблоном, чтобы находить строки с именами заданий верхнего уровня и увеличивать счётчик для каждой.
Подсказка: используйте `awk` с регулярным выражением `/^  [a-z]/` для строк с именами заданий, исключите более глубокий отступ через `&& !/^    /`, увеличивайте `c++` и выводите результат в блоке `END`.

6. Посчитайте шаги в задании workflow. Выполните: `printf 'steps:\n  - uses: actions/checkout@v4\n  - run: npm ci\n  - run: npm test\n  - run: npm run build\n' | grep -c '  - '`

```expected_output
4
```

Подсказка: отфильтруйте строки по шаблону и поручите shell автоматически подсчитать совпадения.
Подсказка: используйте `grep -c`, чтобы посчитать в переданном потоке строки с префиксом шага `  - `.
