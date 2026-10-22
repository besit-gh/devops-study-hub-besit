# DevSecOps — краткая справка

## Поиск секретов

| Tool / Command | Description |
|----------------|-------------|
| `gitleaks detect --source .` | Просканировать репозиторий на секреты |
| `gitleaks detect --no-git -s dir/` | Просканировать каталог вне Git-репозитория |
| `git log --all --full-history -- '*.env'` | Найти удалённые env-файлы в истории |
| `trufflehog git file://./repo` | Просканировать историю Git на секреты |
| `detect-secrets scan > .secrets.baseline` | Создать базовый список секретов |
| `detect-secrets audit .secrets.baseline` | Проверить базовый список |

## SAST (статический анализ)

| Tool / Command | Description |
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

| Command | Description |
|---------|-------------|
| `docker scout cves image:tag` | Поиск CVE с помощью Docker Scout |
| `trivy image image:tag` | Scan image for CVEs |
| `trivy fs .` | Scan filesystem / repo |
| `grype image:tag` | Another image CVE scanner |
| `docker run --read-only image` | Read-only root filesystem |
| `docker run --cap-drop ALL image` | Drop all capabilities |
| `docker run --no-new-privileges image` | Prevent privilege escalation |
| `docker run -u 1000:1000 image` | Run as non-root user |

## TLS / Certificates

| Command | Description |
|---------|-------------|
| `openssl req -x509 -nodes -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365` | Self-signed cert |
| `openssl x509 -in cert.pem -text -noout` | Inspect certificate |
| `openssl s_client -connect host:443` | Test TLS handshake |
| `openssl verify -CAfile ca.pem cert.pem` | Verify cert against CA |
| `certbot certonly --standalone -d example.com` | Let's Encrypt cert |
| `certbot renew` | Renew Let's Encrypt certs |

## Secrets Management

| Tool / Command | Description |
|----------------|-------------|
| `vault login -method=aws` | Authenticate to Vault |
| `vault kv get secret/myapp` | Read a secret |
| `vault kv put secret/myapp key=val` | Write a secret |
| `vault kv list secret/` | List secrets |
| `vault token lookup` | Inspect current token |
| `aws secretsmanager get-secret-value --secret-id name` | AWS Secrets Manager |
| `aws ssm get-parameter --name /path/key --with-decryption` | AWS SSM Parameter Store |

## OWASP / Dependency Scanning

| Command | Description |
|---------|-------------|
| `dependency-check --project name --scan dir/` | CVE scan for dependencies |
| `npm audit` | Node.js dependency audit |
| `npm audit fix` | Auto-fix low-risk issues |
| `pip-audit` | Python dependency audit |
| `safety check -r requirements.txt` | Python safety check |
| `snyk test` | Snyk dependency scan |
| `snyk container test image:tag` | Snyk container scan |
