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
  workflow_dispatch:          # Manual trigger
  schedule:
    - cron: '0 2 * * *'      # Nightly at 2am UTC

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

| Pattern | Description |
|---------|-------------|
| `${{ secrets.MY_SECRET }}` | Reference secret |
| `${{ vars.MY_VAR }}` | Reference variable |
| `${{ github.ref_name }}` | Current branch/tag name |
| `${{ github.sha }}` | Current commit SHA |
| `needs: [job1, job2]` | Wait for other jobs |
| `if: github.ref == 'refs/heads/main'` | Condition on step/job |
| `continue-on-error: true` | Don't fail job on step failure |
| `timeout-minutes: 10` | Job timeout |
| `strategy.matrix` | Parallel matrix builds |
| `environment: production` | Require deployment approval |
| `concurrency: ci-${{ github.ref }}` | Cancel older runs |

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
| `java -jar jenkins-cli.jar -s URL build JOB` | Trigger build |
| `java -jar jenkins-cli.jar -s URL list-jobs` | List jobs |
| `java -jar jenkins-cli.jar -s URL console JOB` | View console output |
| `java -jar jenkins-cli.jar -s URL get-job JOB` | Export job XML |
| `jenkins-jobs update jobs/` | Apply JJB configs |

## ArgoCD CLI

| Command | Description |
|---------|-------------|
| `argocd login host` | Login to ArgoCD |
| `argocd app list` | List applications |
| `argocd app get name` | Application status |
| `argocd app sync name` | Sync app to git state |
| `argocd app diff name` | Show drift from desired state |
| `argocd app rollback name REVISION` | Roll back to revision |
| `argocd app history name` | Rollout history |
