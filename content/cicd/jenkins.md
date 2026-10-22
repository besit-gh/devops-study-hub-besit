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
    agent any   // запустить на любом доступном агенте

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
            echo 'Конвейер выполнен успешно'
        }
        failure {
            mail to: 'team@example.com',
                 subject: "Сборка ${BUILD_NUMBER} завершилась ошибкой",
                 body: "Проверьте ${BUILD_URL}"
        }
        always {
            cleanWs()   // очищать рабочий каталог после каждого запуска
        }
    }
}
```

### Агенты
```groovy
// Любой доступный агент
agent any

// Агент по умолчанию не задан — каждый этап определяет свой
agent none

// Конкретная метка (запуск на агентах с меткой 'docker')
agent { label 'docker' }

// Docker-агент (выполняет этап внутри контейнера)
agent {
    docker {
        image 'python:3.12-slim'
        args '-v /var/run/docker.sock:/var/run/docker.sock'
    }
}

// Шаблон pod Kubernetes
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
// Передать учётные данные через переменные окружения
withCredentials([
    usernamePassword(
        credentialsId: 'aws-ecr-creds',
        usernameVariable: 'AWS_ACCESS_KEY_ID',
        passwordVariable: 'AWS_SECRET_ACCESS_KEY'
    )
]) {
    sh 'aws ecr get-login-password | docker login ...'
}

// SSH-ключ
withCredentials([sshUserPrivateKey(
    credentialsId: 'deploy-key',
    keyFileVariable: 'SSH_KEY'
)]) {
    sh 'ssh -i $SSH_KEY user@server ./deploy.sh'
}

// Секретный текст, например токен API
withCredentials([string(credentialsId: 'slack-token', variable: 'SLACK_TOKEN')]) {
    sh 'curl -H "Authorization: Bearer $SLACK_TOKEN" ...'
}
```

Учётные данные хранятся в **Manage Jenkins → Credentials**, а не в Jenkinsfile.

### Параллельные этапы
```groovy
stage('Тесты и линтинг') {
    parallel {
        stage('Модульные тесты') {
            steps {
                sh 'pytest tests/unit'
            }
        }
        stage('Интеграционные тесты') {
            steps {
                sh 'pytest tests/integration'
            }
        }
        stage('Проверка стиля') {
            steps {
                sh 'ruff check . && mypy src/'
            }
        }
    }
}
```

### Условное выполнение
```groovy
stage('Развёртывание в production') {
    when {
        allOf {
            branch 'main'
            not { changeRequest() }    // это не pull request
        }
    }
    steps {
        input message: 'Развернуть в production?', ok: 'Развернуть'
        sh './deploy-prod.sh'
    }
}
```

Шаг `input` приостанавливает конвейер для ручного подтверждения: сборка ждёт, пока кто-нибудь не нажмёт в интерфейсе «Deploy» или «Abort».

### Общие библиотеки
Общие библиотеки позволяют вынести повторно используемую логику в библиотеку Groovy, хранящуюся в отдельном репозитории.

```groovy
// В Jenkinsfile проекта:
@Library('my-shared-lib@main') _   // загрузить библиотеку

pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                // вызвать функцию из общей библиотеки
                buildAndPushDocker(image: 'myapp', tag: env.BUILD_NUMBER)
            }
        }
    }
}
```

```groovy
// vars/buildAndPushDocker.groovy (в репозитории общей библиотеки):
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
// Встроенные переменные Jenkins
env.BUILD_NUMBER       // "42"
env.BUILD_URL          // полный URL этой сборки
env.JOB_NAME           // "myapp/main"
env.GIT_COMMIT         // git SHA
env.GIT_BRANCH         // "origin/main"
env.WORKSPACE          // путь к рабочему каталогу сборки
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
        stage('Сборка и тесты') {
            agent {
                docker { image 'python:3.12-slim' }
            }
            steps {
                sh 'pip install -r requirements.txt'
                sh 'pytest --tb=short'
            }
        }

        stage('Сборка Docker-образа') {
            steps {
                sh "docker build -t ${IMAGE_NAME}:${IMAGE_TAG} ."
            }
        }

        stage('Отправка в ECR') {
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
