# DevSecOps — краткая справка

## Поиск секретов

| Инструмент / команда | Описание |
|----------------|-------------|
| `gitleaks detect --source .` | Просканировать репозиторий на секреты |
| `gitleaks detect --no-git -s dir/` | Просканировать каталог вне Git-репозитория |
| `git log --all --full-history -- '*.env'` | Найти удалённые env-файлы в истории |
| `trufflehog git file://./repo` | Просканировать историю Git на секреты |
| `detect-secrets scan > .secrets.baseline` | Создать базовый список секретов |
| `detect-secrets audit .secrets.baseline` | Проверить базовый список |

## SAST (статический анализ)

| Инструмент / команда | Описание |
|----------------|-------------|
| `bandit -r src/` | SAST-анализ Python-кода |
| `bandit -r src/ -f json -o report.json` | Вывод в JSON |
| `semgrep --config auto src/` | SAST-анализ нескольких языков |
| `semgrep --config p/owasp-top-ten src/` | Набор правил OWASP |
| `eslint --ext .js,.jsx src/` | Линтинг JS/JSX |
| `hadolint Dockerfile` | Линтинг Dockerfile |
| `checkov -d .` | Проверка безопасности IaC (Terraform, Kubernetes, Docker) |
| `tfsec .` | Проверка безопасности Terraform |

## Безопасность контейнеров

| Command | Описание |
|---------|-------------|
| `docker scout cves image:tag` | Поиск CVE с помощью Docker Scout |
| `trivy image image:tag` | Просканировать образ на CVE |
| `trivy fs .` | Просканировать файловую систему или репозиторий |
| `grype image:tag` | Ещё один сканер образов на CVE |
| `docker run --read-only image` | Корневая файловая система только для чтения |
| `docker run --cap-drop ALL image` | Убрать все capabilities |
| `docker run --no-new-privileges image` | Запретить повышение привилегий |
| `docker run -u 1000:1000 image` | Запустить от непривилегированного пользователя |

## TLS / Certificates

| Command | Описание |
|---------|-------------|
| `openssl req -x509 -nodes -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365` | Самоподписанный сертификат |
| `openssl x509 -in cert.pem -text -noout` | Просмотреть сведения о сертификате |
| `openssl s_client -connect host:443` | Проверить TLS-рукопожатие |
| `openssl verify -CAfile ca.pem cert.pem` | Проверить сертификат с помощью CA |
| `certbot certonly --standalone -d example.com` | Let's Encrypt cert |
| `certbot renew` | Обновить сертификаты Let's Encrypt |

## Secrets Management

| Инструмент / команда | Описание |
|----------------|-------------|
| `vault login -method=aws` | Аутентифицироваться в Vault |
| `vault kv get secret/myapp` | Прочитать секрет |
| `vault kv put secret/myapp key=val` | Записать секрет |
| `vault kv list secret/` | Список секретов |
| `vault token lookup` | Проверить текущий токен |
| `aws secretsmanager get-secret-value --secret-id name` | AWS Secrets Manager |
| `aws ssm get-parameter --name /path/key --with-decryption` | AWS SSM Parameter Store |

## OWASP / Dependency Scanning

| Command | Описание |
|---------|-------------|
| `dependency-check --project name --scan dir/` | Проверить зависимости на CVE |
| `npm audit` | Аудит зависимостей Node.js |
| `npm audit fix` | Автоматически исправить проблемы с низким риском |
| `pip-audit` | Аудит зависимостей Python |
| `safety check -r requirements.txt` | Проверка безопасности Python-зависимостей |
| `snyk test` | Сканирование зависимостей с помощью Snyk |
| `snyk container test image:tag` | Сканирование контейнера с помощью Snyk |
