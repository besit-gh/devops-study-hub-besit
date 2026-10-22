const MODULE_TITLES_RU = {
  ansible: 'Ansible',
  aws: 'AWS — облако Amazon',
  bash: 'Bash и shell-скрипты',
  cicd: 'CI/CD и автоматизация поставки',
  devsecops: 'DevSecOps',
  docker: 'Docker и контейнеры',
  elasticsearch: 'Elasticsearch',
  gcp: 'Google Cloud Platform',
  git: 'Git и контроль версий',
  grafana: 'Grafana',
  helm: 'Helm',
  kibana: 'Kibana',
  kubernetes: 'Kubernetes',
  linux: 'Linux',
  logstash: 'Logstash',
  monitoring: 'Мониторинг и наблюдаемость',
  networking: 'Компьютерные сети',
  opsgenie: 'Opsgenie',
  postman: 'Postman и тестирование API',
  prometheus: 'Prometheus',
  python: 'Python для DevOps',
  terraform: 'Terraform и инфраструктура как код',
  zabbix: 'Zabbix',
}

export const GROUP_TITLES_RU = {
  Foundations: 'Основы',
  'Containers & Infra': 'Контейнеры и инфраструктура',
  'CI/CD & Cloud': 'CI/CD и облака',
  'Security & APIs': 'Безопасность и API',
  Observability: 'Наблюдаемость',
}

export function localizeModuleTitle(slug, fallback = '') {
  return MODULE_TITLES_RU[slug] || fallback
}

export function localizeGroupTitle(group) {
  return GROUP_TITLES_RU[group] || group
}


const LESSON_TITLES_RU = {
  'File System & Permissions': 'Файловая система и права доступа',
  'SSH & Key Management': 'SSH и управление ключами',
  'systemd & Service Management': 'systemd и управление службами',
  'Package Managers (apt/yum)': 'Менеджеры пакетов (apt/yum)',
  'Networking Commands': 'Сетевые команды Linux',
  'Cron Jobs': 'Задания cron',
  'Script Writing Basics': 'Основы написания скриптов Bash',
  'Pipes & Redirects': 'Конвейеры и перенаправление потоков',
  'Error Handling': 'Обработка ошибок в Bash',
  'Branching Strategies': 'Стратегии ветвления Git',
  'Images & Containers': 'Образы и контейнеры Docker',
  'Docker Compose': 'Docker Compose',
  'PR Workflows': 'Рабочий процесс Pull Request',
  'HTTP & HTTPS': 'HTTP и HTTPS',
  'HCL Fundamentals': 'Основы HCL',
  'Pods & Deployments': 'Pod и Deployment',
  'GitHub Actions': 'GitHub Actions',
  'Multi-stage Builds': 'Многоэтапная сборка Docker',
  'Playbooks & Inventory': 'Playbook и inventory Ansible',
  'PromQL': 'Язык запросов PromQL',
  'RBAC': 'RBAC — управление доступом',
  'State Management': 'Управление состоянием Terraform',
  'Pipeline Best Practices': 'Лучшие практики CI/CD-пайплайнов',
  'Rebase vs Merge': 'Rebase и merge: сравнение',
  'Registry Management': 'Управление реестром контейнеров',
  'Modules & Workspaces': 'Модули и рабочие пространства Terraform',
  'Services & Ingress': 'Service и Ingress в Kubernetes',
  'Intro & Metrics Model': 'Введение в Prometheus и модель метрик',
  'Roles': 'Роли Ansible',
  'Scripting Fundamentals': 'Основы скриптов на Python',
  'TCP/IP Fundamentals': 'Основы TCP/IP',
  'Writing CLI Tools': 'Создание CLI-инструментов на Python',
  'YAML & JSON Parsing': 'Разбор YAML и JSON на Python',
  'kubectl Mastery': 'Уверенная работа с kubectl',
  'Image Optimization': 'Оптимизация Docker-образов',
  'Jenkins Pipelines': 'Пайплайны Jenkins',
  'Observability Pillars': 'Основы наблюдаемости: три столпа',
  'Alerting & Notifications': 'Оповещения и уведомления Grafana',
  'Secrets Management': 'Управление секретами',
  'EC2, S3, and IAM': 'EC2, S3 и IAM',
  'VPC and Route 53': 'VPC и Route 53',
  'Subprocess & Automation': 'Subprocess и автоматизация',
  'Dashboards & Visualizations': 'Дашборды и визуализация Grafana',
  'Alerting and Dashboards': 'Оповещения и дашборды',
  'Ansible vs Terraform': 'Ansible и Terraform: сравнение',
  'Persistent Volumes': 'Постоянные тома Kubernetes',
  'Container Security': 'Безопасность контейнеров',
  'OpenTelemetry': 'OpenTelemetry',
  'awk & sed': 'Обработка текста с awk и sed',
  'Regex': 'Регулярные выражения',
  'Git Hooks': 'Git hooks — хуки Git',
  'AWS Lambda': 'AWS Lambda',
  'Compute Engine and Cloud Storage': 'Compute Engine и Cloud Storage',
  'DNS': 'DNS — система доменных имён',
  'Subnets & CIDR': 'Подсети и CIDR',
}

Object.assign(LESSON_TITLES_RU, {
  'Integrations & Alert Routing': 'Интеграции и маршрутизация оповещений',
  'Collections and Environments': 'Коллекции и окружения Postman',
  'Discover & Search': 'Discover и поиск в Kibana',
  'Architecture & Installation': 'Архитектура и установка Zabbix',
  'Charts, Templates & Values': 'Chart, шаблоны и values Helm',
  'Managing Releases': 'Управление релизами Helm',
  'Exporters & Service Discovery': 'Экспортёры и обнаружение сервисов Prometheus',
  'Triggers & Alerting': 'Триггеры и оповещения Zabbix',
  'Cluster Management': 'Управление кластером Elasticsearch',
  'IAM Best Practices': 'Лучшие практики IAM',
  'SAST and DAST': 'SAST и DAST',
  'boto3 — AWS SDK': 'boto3 — SDK AWS для Python',
  'Data Sources & Plugins': 'Источники данных и плагины Grafana',
  'Performance Tuning': 'Настройка производительности Logstash',
  'Amazon EKS': 'Amazon EKS',
  'Google Kubernetes Engine (GKE)': 'Google Kubernetes Engine (GKE)',
  'Architecture & Data Model': 'Архитектура и модель данных Elasticsearch',
  'Security & Access Control': 'Безопасность и управление доступом Elasticsearch',
  'Dashboards & Visualizations': 'Дашборды и визуализация Kibana',
  'Indexing & Querying': 'Индексация и запросы Elasticsearch',
  'Subnets & CIDR': 'Подсети и CIDR',
  'Alerting & Dashboards': 'Оповещения и дашборды',
  'Ansible vs Terraform': 'Ansible и Terraform: сравнение',
  'OpenTelemetry': 'OpenTelemetry',
  'Container Security': 'Безопасность контейнеров',
  'Secrets Management': 'Управление секретами',
  'Scripting Fundamentals': 'Основы скриптов на Python',
  'TCP/IP Fundamentals': 'Основы TCP/IP',
  'Writing CLI Tools': 'Создание CLI-инструментов на Python',
  'YAML & JSON Parsing': 'Разбор YAML и JSON на Python',
  'kubectl Mastery': 'Уверенная работа с kubectl',
  'Image Optimization': 'Оптимизация Docker-образов',
  'Jenkins Pipelines': 'Пайплайны Jenkins',
  'Compute Engine and Cloud Storage': 'Compute Engine и Cloud Storage',
  'Git Hooks': 'Git hooks — хуки Git',
  'AWS Lambda': 'AWS Lambda',
  'REST API Fundamentals': 'Основы REST API',
  'Python Subprocess & Automation': 'Subprocess и автоматизация Python',
  'SAST/DAST': 'SAST и DAST',
});


Object.assign(LESSON_TITLES_RU, {
  'AWS Cost Management': 'Управление затратами AWS',
  'Cloud Functions': 'Cloud Functions',
  'Writing Custom Charts': 'Создание собственных Helm chart',
  'Alerting & Reporting': 'Оповещения и отчёты Kibana',
  'Inputs, Filters & Outputs': 'Inputs, filters и outputs Logstash',
  'Firewalls & Load Balancers': 'Межсетевые экраны и балансировщики нагрузки',
  'On-Call Schedules & Escalations': 'Графики дежурств и эскалации Opsgenie',
  'Automated API Tests': 'Автоматизированные тесты API',
  'Alertmanager': 'Alertmanager',
  'Agents & Templates': 'Агенты и шаблоны Zabbix',
});

export function localizeLessonTitle(title) {
  return LESSON_TITLES_RU[title] || title
}

export function localizeDifficulty(difficulty) {
  return ({ beginner: 'Начальный', intermediate: 'Средний', advanced: 'Продвинутый' })[difficulty] || difficulty
}
