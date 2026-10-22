---
title: Пайплайны Jenkins
module: cicd
duration_min: 25
difficulty: intermediate
tags: [cicd, jenkins, pipeline, jenkinsfile, declarative, groovy, credentials]
exercises: 4
---

## Обзор
Jenkins — один из наиболее распространённых open-source серверов CI/CD. Пайплайны описываются в `Jenkinsfile` на основе DSL языка Groovy и хранятся в репозитории. Декларативный синтаксис pipeline, появившийся в Jenkins 2.x, стал современным стандартом: он структурирован, читаем и переносим. Для большинства корпоративных сценариев достаточно понимать Jenkinsfile, агентов, учётные данные и shared libraries.

## Основные понятия

### Структура декларативного pipeline
```groovy
// Jenkinsfile
pipeline {
    agent any   // run on any available agent

    environment {
        APP_NAME = 'myapp'
        ECR_REPO = '123456789.dkr.ecr.us-east-1.amazonaws.com/myapp'
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Test') {
            steps {
                sh 'pip install -r requirements.txt'
                sh 'pytest --tb=short --junitxml=test-results.xml'
            }
            post {
                always {
                    junit 'test-results.xml'
                }
            }
        }

        stage('Build') {
            steps {
                sh 'docker build -t ${APP_NAME}:${BUILD_NUMBER} .'
            }
        }

        stage('Deploy') {
            when {
                branch 'main'
            }
            steps {
                sh './deploy.sh ${BUILD_NUMBER}'
            }
        }
    }

    post {
        success {
            echo 'Pipeline succeeded'
        }
        failure {
            mail to: 'team@example.com',
                 subject: "Build ${BUILD_NUMBER} failed",
                 body: "Check ${BUILD_URL}"
        }
        always {
            cleanWs()   // clean workspace after every run
        }
    }
}
```

### Агенты
```groovy
// Any available agent
agent any

// No default agent — each stage declares its own
agent none

// Specific label (run on agents tagged 'docker')
agent { label 'docker' }

// Docker agent (runs the stage inside a container)
agent {
    docker {
        image 'python:3.12-slim'
        args '-v /var/run/docker.sock:/var/run/docker.sock'
    }
}

// Kubernetes pod template
agent {
    kubernetes {
        yaml '''
apiVersion: v1
kind: Pod
spec:
  containers:
    - name: python
      image: python:3.12-slim
      command: [cat]
      tty: true
'''
    }
}
```

### Учётные данные
```groovy
// Bind credentials to environment variables
withCredentials([
    usernamePassword(
        credentialsId: 'aws-ecr-creds',
        usernameVariable: 'AWS_ACCESS_KEY_ID',
        passwordVariable: 'AWS_SECRET_ACCESS_KEY'
    )
]) {
    sh 'aws ecr get-login-password | docker login ...'
}

// SSH key
withCredentials([sshUserPrivateKey(
    credentialsId: 'deploy-key',
    keyFileVariable: 'SSH_KEY'
)]) {
    sh 'ssh -i $SSH_KEY user@server ./deploy.sh'
}

// Secret text (e.g. API token)
withCredentials([string(credentialsId: 'slack-token', variable: 'SLACK_TOKEN')]) {
    sh 'curl -H "Authorization: Bearer $SLACK_TOKEN" ...'
}
```

Учётные данные хранятся в **Manage Jenkins → Credentials**, а не в Jenkinsfile.

### Параллельные этапы
```groovy
stage('Test and Lint') {
    parallel {
        stage('Unit Tests') {
            steps {
                sh 'pytest tests/unit'
            }
        }
        stage('Integration Tests') {
            steps {
                sh 'pytest tests/integration'
            }
        }
        stage('Lint') {
            steps {
                sh 'ruff check . && mypy src/'
            }
        }
    }
}
```

### Условное выполнение
```groovy
stage('Deploy to Prod') {
    when {
        allOf {
            branch 'main'
            not { changeRequest() }    // not a PR
        }
    }
    steps {
        input message: 'Deploy to production?', ok: 'Deploy'
        sh './deploy-prod.sh'
    }
}
```

Шаг `input` приостанавливает конвейер для ручного подтверждения: сборка ждёт, пока кто-нибудь не нажмёт в интерфейсе «Deploy» или «Abort».

### Общие библиотеки
Общие библиотеки позволяют вынести повторно используемую логику в библиотеку Groovy, хранящуюся в отдельном репозитории.

```groovy
// In your Jenkinsfile:
@Library('my-shared-lib@main') _   // load the library

pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                // call a function from the shared library
                buildAndPushDocker(image: 'myapp', tag: env.BUILD_NUMBER)
            }
        }
    }
}
```

```groovy
// vars/buildAndPushDocker.groovy (in the shared library repo):
def call(Map args) {
    sh "docker build -t ${args.image}:${args.tag} ."
    sh "docker push ${args.image}:${args.tag}"
}
```

### Многоветочный pipeline
Задание Multibranch Pipeline сканирует репозиторий и автоматически создаёт pipeline для каждой ветки. При push новой ветки Jenkins создаёт для неё задание; при удалении ветки — удаляет и задание.

Настройте задание в интерфейсе: **New Item → Multibranch Pipeline**, затем укажите репозиторий. Jenkins будет использовать `Jenkinsfile` из каждой ветки.

### Переменные окружения
```groovy
// Built-in Jenkins variables
env.BUILD_NUMBER       // "42"
env.BUILD_URL          // full URL to this build
env.JOB_NAME           // "myapp/main"
env.GIT_COMMIT         // git SHA
env.GIT_BRANCH         // "origin/main"
env.WORKSPACE          // path to the build workspace
```

## Примеры

### Сборка Docker-образа и отправка в ECR
```groovy
pipeline {
    agent any

    environment {
        AWS_REGION    = 'us-east-1'
        ECR_REGISTRY  = '123456789.dkr.ecr.us-east-1.amazonaws.com'
        IMAGE_NAME    = 'myapp'
        IMAGE_TAG     = "${BUILD_NUMBER}-${GIT_COMMIT[0..7]}"
    }

    stages {
        stage('Build & Test') {
            agent {
                docker { image 'python:3.12-slim' }
            }
            steps {
                sh 'pip install -r requirements.txt'
                sh 'pytest --tb=short'
            }
        }

        stage('Docker Build') {
            steps {
                sh "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} ."
            }
        }

        stage('Push to ECR') {
            when { branch 'main' }
            steps {
                withCredentials([[
                    $class: 'AmazonWebServicesCredentialsBinding',
                    credentialsId: 'aws-credentials'
                ]]) {
                    sh """
                        aws ecr get-login-password --region ${AWS_REGION} \
                          | docker login --username AWS --password-stdin ${ECR_REGISTRY}
                        docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
                        docker push ${ECR_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
                    """
                }
            }
        }
    }
}
```

## Практические задания

1. Напишите декларативный Jenkinsfile, который получает исходный код, запускает `pytest` в Docker-агенте `python:3.12-slim`, публикует результаты JUnit и отправляет письмо при сбое в блоке `post`.
2. Добавьте параллельные этапы для одновременного запуска модульных тестов и линтера. Проверьте параллельное выполнение на временной шкале интерфейса Blue Ocean.
3. Настройте этап `Deploy to Prod`, который запускается только в ветке `main` и требует ручного подтверждения через `input`. Используйте `withCredentials`, чтобы передать SSH-ключ для развёртывания.
4. Создайте функцию общей библиотеки `notifySlack(message)`, отправляющую POST-запрос в Slack webhook. Вызовите её из блока `post { failure { ... } }` в Jenkinsfile.


---

### Быстрая проверка

5. Посчитайте этапы pipeline в примере Jenkinsfile. Выполните: `printf 'stage("Build") {}\nstage("Test") {}\nstage("Deploy") {}\n' | grep -c 'stage('`

```expected_output
3
```

Подсказка: найдите заданный шаблон в тексте и попросите инструмент сразу вывести число совпавших строк.
Подсказка: используйте `grep -c`, чтобы посчитать в переданном потоке вхождения шаблона `stage(`.

6. Посчитайте блоки условий `post` в Jenkinsfile. Выполните: `printf 'post {\n  always {}\n  success {}\n  failure {}\n}\n' | grep -c '  [a-z]* {}'`

```expected_output
3
```

Подсказка: `grep` может не только находить совпадения, но и подсчитывать число подходящих строк.
Подсказка: используйте `grep -c` с регулярным выражением вроде `'  [a-z]* {}'`, чтобы посчитать строки с синтаксисом блока условия и отступом.
