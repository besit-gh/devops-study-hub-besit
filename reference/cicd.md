# CI/CD-пайплайны — краткая справка

## CLI GitHub Actions (gh)

| Command | Description |
|---------|-------------|
| `gh workflow list` | Список workflow |
| `gh workflow run name.yml` | Запустить workflow вручную |
| `gh run list` | Список недавних запусков workflow |
| `gh run view ID` | Просмотреть детали запуска |
| `gh run watch ID` | Следить за текущим запуском |
| `gh run download ID` | Скачать артефакты запуска |
| `gh secret list` | Список секретов репозитория |
| `gh secret set NAME` | Задать секрет (с запросом значения) |
| `gh variable list` | Список переменных Actions |
| `gh cache list` | Список записей кэша runner |
| `gh cache delete KEY` | Удалить запись кэша |

## GitHub Actions — основные шаблоны workflow

```yaml
on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:          # Ручной запуск
  schedule:
    - cron: '0 2 * * *'      # Каждую ночь в 02:00 UTC

jobs:
  build:
    runs-on: ubuntu-latest
    env:
      APP_ENV: production
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip
      - run: pip install -r requirements.txt
      - run: pytest
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
```

## GitHub Actions — распространённые шаблоны

| Шаблон | Description |
|---------|-------------|
| `${{ secrets.MY_SECRET }}` | Обратиться к секрету |
| `${{ vars.MY_VAR }}` | Обратиться к переменной |
| `${{ github.ref_name }}` | Имя текущей ветки или тега |
| `${{ github.sha }}` | SHA текущего коммита |
| `needs: [job1, job2]` | Дождаться завершения других заданий |
| `if: github.ref == 'refs/heads/main'` | Условие для шага или задания |
| `continue-on-error: true` | Не завершать задание с ошибкой при сбое шага |
| `timeout-minutes: 10` | Тайм-аут задания |
| `strategy.matrix` | Параллельная матрица сборок |
| `environment: production` | Требовать подтверждение развёртывания |
| `concurrency: ci-${{ github.ref }}` | Отменять предыдущие запуски |

## Jenkins — Pipeline (Declarative)

```groovy
pipeline {
  agent any
  environment { APP_ENV = 'prod' }
  stages {
    stage('Build') {
      steps { sh 'make build' }
    }
    stage('Test') {
      steps { sh 'make test' }
      post { always { junit 'reports/*.xml' } }
    }
    stage('Deploy') {
      when { branch 'main' }
      steps { sh 'make deploy' }
    }
  }
  post {
    failure { slackSend message: "Build failed: ${env.BUILD_URL}" }
  }
}
```

## Jenkins CLI

| Command | Description |
|---------|-------------|
| `java -jar jenkins-cli.jar -s URL build JOB` | Запустить сборку |
| `java -jar jenkins-cli.jar -s URL list-jobs` | Список заданий |
| `java -jar jenkins-cli.jar -s URL console JOB` | Просмотреть вывод консоли |
| `java -jar jenkins-cli.jar -s URL get-job JOB` | Экспортировать задание в XML |
| `jenkins-jobs update jobs/` | Применить конфигурации JJB |

## ArgoCD CLI

| Command | Description |
|---------|-------------|
| `argocd login host` | Войти в ArgoCD |
| `argocd app list` | Список приложений |
| `argocd app get name` | Состояние приложения |
| `argocd app sync name` | Синхронизировать приложение с состоянием Git |
| `argocd app diff name` | Показать отклонения от желаемого состояния |
| `argocd app rollback name REVISION` | Откатиться к ревизии |
| `argocd app history name` | История развёртываний |
