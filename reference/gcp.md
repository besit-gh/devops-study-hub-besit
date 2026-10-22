# GCP — краткая справка

## Настройка gcloud

| Command | Description |
|---------|-------------|
| `gcloud init` | Инициализировать SDK и войти в аккаунт |
| `gcloud auth login` | Пройти аутентификацию |
| `gcloud auth application-default login` | Аутентификация для кода приложения |
| `gcloud config list` | Показать активную конфигурацию |
| `gcloud config set project PROJECT_ID` | Задать проект по умолчанию |
| `gcloud config set compute/zone us-central1-a` | Задать зону по умолчанию |
| `gcloud config configurations list` | Список именованных конфигураций |
| `gcloud info` | Сведения об окружении SDK |

## Compute Engine

| Command | Description |
|---------|-------------|
| `gcloud compute instances list` | Список виртуальных машин |
| `gcloud compute instances create name --zone=z --machine-type=e2-micro` | Создать виртуальную машину |
| `gcloud compute instances start name --zone=z` | Запустить экземпляр |
| `gcloud compute instances stop name --zone=z` | Остановить экземпляр |
| `gcloud compute instances delete name --zone=z` | Удалить экземпляр |
| `gcloud compute ssh name --zone=z` | Подключиться к экземпляру по SSH |
| `gcloud compute scp file name:~/dest --zone=z` | Скопировать файл на экземпляр |
| `gcloud compute firewall-rules list` | Список правил межсетевого экрана |

## GKE

| Command | Description |
|---------|-------------|
| `gcloud container clusters list` | List GKE clusters |
| `gcloud container clusters create name --zone=z --num-nodes=3` | Create cluster |
| `gcloud container clusters get-credentials name --zone=z` | Configure kubectl |
| `gcloud container clusters delete name --zone=z` | Delete cluster |
| `gcloud container images list` | List images in Container Registry |

## Cloud Storage

| Command | Description |
|---------|-------------|
| `gsutil ls` | List buckets |
| `gsutil ls gs://bucket/` | List bucket contents |
| `gsutil cp file gs://bucket/path` | Upload file |
| `gsutil cp gs://bucket/path file` | Download file |
| `gsutil rsync -r dir/ gs://bucket/` | Sync directory |
| `gsutil rm gs://bucket/path` | Delete object |
| `gsutil mb gs://bucket-name` | Create bucket |
| `gsutil du -sh gs://bucket/` | Bucket size |

## IAM

| Command | Description |
|---------|-------------|
| `gcloud iam service-accounts list` | List service accounts |
| `gcloud iam service-accounts create name` | Create service account |
| `gcloud projects add-iam-policy-binding PROJECT --member=... --role=...` | Bind role |
| `gcloud iam service-accounts keys create key.json --iam-account=SA_EMAIL` | Create SA key |

## Cloud Functions & Run

| Command | Description |
|---------|-------------|
| `gcloud functions list` | List Cloud Functions |
| `gcloud functions deploy name --runtime=python39 --trigger-http` | Deploy function |
| `gcloud functions logs read name` | Function logs |
| `gcloud run services list` | List Cloud Run services |
| `gcloud run deploy svc --image=img --platform=managed` | Deploy Cloud Run service |

## Logging

| Command | Description |
|---------|-------------|
| `gcloud logging read "resource.type=gce_instance"` | Read logs with filter |
| `gcloud logging read "severity=ERROR" --limit=50` | Recent errors |
| `gcloud logging tail "resource.type=cloud_run_revision"` | Follow logs |
