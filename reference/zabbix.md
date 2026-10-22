# Zabbix — краткая справка

## zabbix_agentd

| Команда | Описание |
|---------|-------------|
| `zabbix_agentd -t system.cpu.load` | Локально проверить метрику |
| `zabbix_agentd -t vfs.fs.size[/,used]` | Проверить метрику файловой системы |
| `zabbix_agentd --print` | Вывести поддерживаемые элементы данных |
| `systemctl status zabbix-agent2` | Состояние службы агента |
| `systemctl restart zabbix-agent2` | Перезапустить агент |
| `zabbix_agentd -c /etc/zabbix/zabbix_agentd.conf --foreground` | Запустить в foreground (отладка) |

## zabbix_get (от сервера к агенту)

| Команда | Описание |
|---------|-------------|
| `zabbix_get -s host -k system.cpu.load` | Получить метрику от агента |
| `zabbix_get -s host -p 10050 -k agent.ping` | Проверить связность |
| `zabbix_get -s host -k vm.memory.size[available]` | Доступная память |
| `zabbix_get -s host -k net.if.in[eth0]` | Входящий трафик сетевого интерфейса |

## zabbix_sender

| Команда | Описание |
|---------|-------------|
| `zabbix_sender -z server -s "Hostname" -k key -o value` | Отправить одно значение |
| `zabbix_sender -z server -i data.txt` | Отправить данные из файла |
| `zabbix_sender -z server -s "Host" -k key -o val --real-time` | Отправить в реальном времени |

Формат файла данных (один элемент на строку):
```
Hostname key value
Hostname key value timestamp
```

## Zabbix API (curl)

```bash
ZABBIX="http://zabbix/api_jsonrpc.php"

# Войти и получить токен
curl -X POST "$ZABBIX" -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "method": "user.login",
  "params": {"user": "Admin", "password": "zabbix"},
  "id": 1
}'

# Получить узлы (замените TOKEN)
curl -X POST "$ZABBIX" -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "method": "host.get",
  "params": {"output": ["hostid", "host", "status"]},
  "auth": "TOKEN", "id": 2
}'

# Получить активные проблемы
curl -X POST "$ZABBIX" -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "method": "problem.get",
  "params": {"recent": true, "sortfield": "eventid", "sortorder": "DESC"},
  "auth": "TOKEN", "id": 3
}'
```

## Key Built-in Item Keys

| Key | Описание |
|-----|-------------|
| `system.cpu.load[,avg1]` | Средняя нагрузка CPU за 1 минуту |
| `vm.memory.size[available]` | Доступная память (байты) |
| `vfs.fs.size[/,pfree]` | Процент свободного места на диске |
| `net.if.in[eth0]` | Входящий сетевой трафик, байт/с |
| `net.if.out[eth0]` | Исходящий сетевой трафик, байт/с |
| `proc.num[nginx]` | Количество работающих процессов nginx |
| `agent.ping` | Доступность агента (1 = OK) |
| `system.uptime` | Время работы системы (секунды) |
| `log[/var/log/app.log,ERROR]` | Мониторинг журналов |
| `web.page.get[url]` | Содержимое HTTP-страницы |
