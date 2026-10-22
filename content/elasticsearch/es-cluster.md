---
title: Управление кластером Elasticsearch
module: elasticsearch
duration_min: 20
difficulty: intermediate
tags: [elasticsearch, cluster-health, cat-api, snapshots, aliases, reindex]
exercises: 3
---

## Обзор
Эксплуатация Elasticsearch в production требует умения интерпретировать состояние кластера, диагностировать проблемы shards, безопасно перенаправлять данные и выполнять reindex или snapshot/restore без простоя. Именно с такими задачами сталкиваются DevOps- и SRE-инженеры, когда статус Kibana становится жёлтым или красным посреди ночи. Эти темы часто встречаются и на собеседованиях по Elastic.

## Основные понятия

### Состояние кластера

```bash
GET /_cluster/health
```

```json
{
  "cluster_name": "prod-logs",
  "status": "yellow",
  "timed_out": false,
  "number_of_nodes": 3,
  "number_of_data_nodes": 3,
  "active_primary_shards": 15,
  "active_shards": 15,
  "relocating_shards": 0,
  "initializing_shards": 0,
  "unassigned_shards": 5,
  "number_of_pending_tasks": 0
}
```

| Статус | Значение |
|--------|---------|
| `green` | Все первичные и реплики назначены |
| `yellow` | Все первичные шарды назначены; одна или несколько реплик не назначены |
| `red` | Один или несколько первичных шардов не назначены — есть риск частичной потери данных |

Статус **yellow** в одноузловом кластере — нормальное явление: разместить реплику негде. В многоузловом кластере yellow означает потерю высокой доступности. Red означает, что часть данных сейчас недоступна.

Ожидание определённого статуса (полезно в скриптах):
```bash
GET /_cluster/health?wait_for_status=green&timeout=60s
```

### Cat API

API `_cat` возвращают удобный для чтения табличный вывод. Флаг `?v` добавляет заголовки столбцов; `?h=col1,col2` выбирает нужные столбцы; `?s=col` сортирует по столбцу.

```bash
# Cluster-level summary
GET /_cat/health?v

# All nodes with heap and disk stats
GET /_cat/nodes?v&h=name,heap.percent,ram.percent,cpu,load_1m,node.role,master

# All indices sorted by store size (descending)
GET /_cat/indices?v&h=index,health,pri,rep,docs.count,store.size&s=store.size:desc

# Shard distribution — which shard lives on which node
GET /_cat/shards?v&h=index,shard,prirep,state,unassigned.reason,node

# Pending cluster tasks (useful during rolling restarts)
GET /_cat/pending_tasks?v
```

Столбец `unassigned.reason` в `_cat/shards` крайне важен для диагностики. Распространённые значения:

| Причина | Значение |
|--------|---------|
| `NODE_LEFT` | Узел, на котором находился шард, покинул кластер |
| `ALLOCATION_FAILED` | Попытка назначить шард завершилась неудачей (проверьте журналы) |
| `INDEX_CREATED` | Индекс только создан — ожидается узел со свободным местом |
| `CLUSTER_RECOVERED` | Идёт восстановление после перезапуска |

### Назначение шардов

**Проверить причину неназначения:**
```bash
GET /_cluster/allocation/explain
{
  "index": "logs-app-2024",
  "shard": 0,
  "primary": false
}
```

Эту команду стоит запускать первой, если назначение шардов зависло. Ответ точно укажет причину: превышен порог заполнения диска, не совпадают атрибуты узлов, действует фильтр размещения и т. д.

**Ручное перенаправление шарда:**
```bash
POST /_cluster/reroute
{
  "commands": [
    {
      "move": {
        "index": "logs-app-2024",
        "shard": 0,
        "from_node": "data-node-1",
        "to_node": "data-node-2"
      }
    }
  ]
}
```

**Временно отключить назначение шардов** (полезно перед обслуживанием узла):
```bash
PUT /_cluster/settings
{
  "persistent": {
    "cluster.routing.allocation.enable": "primaries"
  }
}
# Re-enable after maintenance
PUT /_cluster/settings
{
  "persistent": {
    "cluster.routing.allocation.enable": null
  }
}
```

Пороговые значения заполнения диска (по умолчанию):
- Low: 85% — прекратить назначение новых шардов на этот узел
- High: 90% — начать перенос шардов с этого узла
- Flood stage: 95% — индекс становится доступным только для чтения

### API переиндексации

Reindex копирует документы из исходного индекса в целевой. Применяется для изменения mapping (тип поля нельзя поменять на месте), количества шардов и миграции данных.

```bash
POST /_reindex
{
  "source": {
    "index": "logs-app-old",
    "query": {
      "range": { "@timestamp": { "gte": "2024-01-01" } }
    }
  },
  "dest": {
    "index": "logs-app-new",
    "op_type": "create"
  }
}
```

`op_type: create` предотвращает перезапись существующих документов. Для больших операций запускайте переиндексацию асинхронно:

```bash
POST /_reindex?wait_for_completion=false
# Returns a task ID
GET /_tasks/<task_id>
# Cancel if needed
POST /_tasks/<task_id>/_cancel
```

### Псевдонимы индексов

Alias — виртуальное имя индекса, которое может указывать на один или несколько реальных индексов. Это стандартный способ переиндексации и переключения индексов без простоя.

```bash
# Create an alias pointing to a new index
POST /_aliases
{
  "actions": [
    { "add":    { "index": "logs-app-v2", "alias": "logs-app" } },
    { "remove": { "index": "logs-app-v1", "alias": "logs-app" } }
  ]
}
```

Alias поддерживает **фильтры**, позволяющие предоставлять разным пользователям или приложениям ограниченное представление данных:
```bash
POST /_aliases
{
  "actions": [{
    "add": {
      "index": "logs-app-2024",
      "alias": "logs-errors",
      "filter": { "term": { "level": "ERROR" } }
    }
  }]
}
```

**Write alias** определяет, в какой индекс попадают новые документы при записи через alias. Для одного alias только один индекс может иметь `"is_write_index": true`.

### Снимки и восстановление

Snapshot — основной механизм резервного копирования. Снимки инкрементальные: записываются только сегменты, изменившиеся после предыдущего snapshot.

**Зарегистрировать репозиторий** (пример с S3):
```bash
PUT /_snapshot/s3-backup
{
  "type": "s3",
  "settings": {
    "bucket": "my-es-backups",
    "region": "us-east-1",
    "base_path": "prod-cluster"
  }
}
```

**Создать snapshot:**
```bash
PUT /_snapshot/s3-backup/snapshot-2024-03-15
{
  "indices": "logs-*",
  "ignore_unavailable": true,
  "include_global_state": false
}
```

**Отслеживать ход выполнения:**
```bash
GET /_snapshot/s3-backup/snapshot-2024-03-15/_status
```

**Восстановить:**
```bash
POST /_snapshot/s3-backup/snapshot-2024-03-15/_restore
{
  "indices": "logs-app-2024",
  "rename_pattern": "logs-(.+)",
  "rename_replacement": "restored-logs-$1",
  "index_settings": {
    "index.number_of_replicas": 0
  }
}
```

Для ускорения первоначально восстановите реплики с количеством `0`, а после завершения восстановления увеличьте его.

### Последовательные обновления

Elasticsearch поддерживает обновление без простоя между версиями в рамках одной основной версии. Порядок действий:

1. Отключите назначение шардов: `cluster.routing.allocation.enable: none`
2. Остановите один узел и обновите бинарный файл Elasticsearch.
3. Запустите узел и дождитесь его возвращения в кластер: `GET /_cat/nodes`
4. Повторно включите назначение: `cluster.routing.allocation.enable: null`
5. Дождитесь статуса green: `GET /_cluster/health?wait_for_status=green`
6. Повторите действия для следующего узла.

Для перехода между основными версиями (например, 7 → 8) изучите документацию о несовместимых изменениях. Может потребоваться полный перезапуск кластера или промежуточное обновление.

### Настройки кластера

У настроек есть два уровня сохранения:

| Уровень | Ключ | Сохраняется после перезапуска |
|-------|-----|-----------------|
| Временный | `transient` | Нет |
| Постоянный | `persistent` | Да |

Постоянные настройки имеют приоритет над `elasticsearch.yml`. Временные теряются при полном перезапуске кластера. Используйте временные настройки для оперативных изменений (пороги диска, назначение шардов), а постоянные — для долгосрочной политики.

```bash
# Temporarily raise flood watermark during disk pressure
PUT /_cluster/settings
{
  "transient": {
    "cluster.routing.allocation.disk.watermark.flood_stage": "97%"
  }
}
```

## Примеры

### Инструкция по диагностике жёлтого кластера

1. Выполните `GET /_cluster/health`: подтвердите статус yellow и проверьте `unassigned_shards`.
2. Выполните `GET /_cat/shards?v&h=index,shard,prirep,state,unassigned.reason,node`, чтобы найти неназначенные шарды.
3. Выполните `GET /_cluster/allocation/explain`, чтобы получить точную причину от Elasticsearch.
4. Типичные способы решения:
   - **Порог диска**: освободите место или временно увеличьте порог.
   - **NODE_LEFT**: дождитесь возвращения узла или принудительно назначьте реплику в другом месте.
   - **Одноузловой кластер**: установите `number_of_replicas: 0` для небольших индексов разработки и тестирования.

## Практические задания

1. Simulate a yellow cluster on a local Docker setup (two Elasticsearch nodes, one replica per index). Stop one container. Run `_cat/shards` and `_cluster/allocation/explain` and document every field in the explain output. Bring the node back and observe the recovery sequence using `_cat/recovery?v`.

2. Create an index `products-v1` with 2 shards and index 100 documents. Change the mapping by adding a new `sku` (keyword) field — without reindex. Then add a `price_float` field that should have been `float` but was indexed as `keyword`. Perform a reindex to `products-v2` with the corrected mapping. Flip the alias `products` from `products-v1` to `products-v2` atomically with a single `_aliases` call. Verify the old index is no longer the write target.

3. Set up an S3-compatible snapshot repository using MinIO in Docker (or a real S3 bucket). Take a snapshot of all indices, delete one index, then restore only that index using `rename_replacement` to restore it under a different name. Verify document counts match before and after using `_cat/indices`.


---

### Быстрая проверка

4. Calculate the minimum master-eligible nodes for quorum in a 5-node cluster. Run: `python3 -c "nodes=5; print(nodes // 2 + 1)"`

```expected_output
3
```

Подсказка: вспомните математический расчёт кворума в распределённом кластере, предотвращающий split-brain.
Подсказка: используйте целочисленное деление Python `//` по формуле `(total_nodes // 2 + 1)`, чтобы найти минимальное число узлов, имеющих право быть master.

5. Count green-status clusters in a health summary. Run: `printf 'cluster_1: green\ncluster_2: yellow\ncluster_3: green\ncluster_4: green\n' | awk '{count[$2]++} END{print count["green"]}'`

```expected_output
3
```

Подсказка: с помощью `awk` можно создать таблицу частот, храня счётчики в ассоциативном массиве, где ключом служит значение поля.
Подсказка: в `awk` используйте `{count[$2]++}` для подсчёта каждого статуса, затем обратитесь к нужному ключу в блоке `END` через `count["green"]`.
