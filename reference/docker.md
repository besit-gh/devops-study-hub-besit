# Docker — краткая справка

## Образы

| Команда | Назначение |
|---------|-------------|
| `docker build -t name:tag .` | Собрать образ из Dockerfile |
| `docker build --no-cache -t name .` | Собрать без кэша |
| `docker images` | Список локальных образов |
| `docker rmi image` | Удалить образ |
| `docker image prune` | Удалить неиспользуемые образы без тегов |
| `docker pull image:tag` | Загрузить из реестра |
| `docker push image:tag` | Отправить в реестр |
| `docker tag src dst` | Назначить тег образу |
| `docker save -o file.tar image` | Экспортировать образ в tar |
| `docker load -i file.tar` | Загрузить образ из tar |
| `docker history image` | Показать слои образа |

## Контейнеры

| Команда | Назначение |
|---------|-------------|
| `docker run image` | Запустить контейнер |
| `docker run -d image` | Запустить в фоновом режиме |
| `docker run -p 8080:80 image` | Сопоставить порт хоста и контейнера |
| `docker run -v /host:/container image` | Подключить bind mount |
| `docker run --rm image` | Автоматически удалить после завершения |
| `docker run -e VAR=val image` | Установить переменную окружения |
| `docker run --name myapp image` | Назвать контейнер |
| `docker run -it image bash` | Интерактивная оболочка |
| `docker ps` | Список запущенных контейнеров |
| `docker ps -a` | Список всех контейнеров |
| `docker stop name` | Корректно остановить (SIGTERM) |
| `docker kill name` | Принудительно остановить (SIGKILL) |
| `docker rm name` | Удалить контейнер |
| `docker rm $(docker ps -aq)` | Удалить все остановленные контейнеры |

## Просмотр состояния и отладка

| Команда | Назначение |
|---------|-------------|
| `docker logs name` | Показать журналы контейнера |
| `docker logs -f name` | Следить за журналом |
| `docker logs --tail 100 name` | Последние 100 строк |
| `docker exec -it name bash` | Открыть shell в работающем контейнере |
| `docker inspect name` | Полные метаданные контейнера в JSON |
| `docker stats` | Текущее потребление ресурсов |
| `docker top name` | Процессы внутри контейнера |
| `docker cp src name:/dest` | Скопировать файл в контейнер |
| `docker diff name` | Показать изменения файловой системы |

## Сети и тома

| Команда | Назначение |
|---------|-------------|
| `docker network ls` | Список сетей |
| `docker network create mynet` | Создать сеть |
| `docker run --network mynet image` | Подключить к сети |
| `docker volume ls` | Список томов |
| `docker volume create myvol` | Создать том |
| `docker run -v myvol:/data image` | Подключить именованный том |
| `docker volume prune` | Удалить неиспользуемые тома |

## Docker Compose

| Команда | Назначение |
|---------|-------------|
| `docker compose up` | Запустить службы |
| `docker compose up -d` | Запустить в фоне |
| `docker compose up --build` | Принудительно пересобрать |
| `docker compose down` | Остановить и удалить контейнеры |
| `docker compose down -v` | Также удалить тома |
| `docker compose logs -f svc` | Следить за журналами службы |
| `docker compose exec svc bash` | Открыть shell в службе |
| `docker compose ps` | Показать состояние служб |
| `docker compose restart svc` | Перезапустить службу |
| `docker compose pull` | Загрузить последние версии образов |

## Шаблоны Dockerfile

| Инструкция | Назначение |
|------------|-------------|
| `FROM base:tag` | Базовый образ |
| `RUN cmd` | Выполнить во время сборки |
| `COPY src dest` | Скопировать файлы в образ |
| `WORKDIR /path` | Установить рабочий каталог |
| `ENV VAR=value` | Установить переменную окружения |
| `EXPOSE 8080` | Объявить порт контейнера |
| `CMD ["app"]` | Команда по умолчанию (может быть переопределена) |
| `ENTRYPOINT ["app"]` | Фиксированная точка входа |
| `ARG NAME=default` | Переменная времени сборки |
| `HEALTHCHECK CMD curl ...` | Проверка работоспособности контейнера |
