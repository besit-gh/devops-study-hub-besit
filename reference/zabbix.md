# Zabbix — краткая справка

## zabbix_agentd

| Command | Description |
|---------|-------------|
| `zabbix_agentd -t system.cpu.load` | Локально проверить метрику |
| `zabbix_agentd -t vfs.fs.size[/,used]` | Проверить метрику файловой системы |
| `zabbix_agentd --print` | Вывести поддерживаемые элементы данных |
| `systemctl status zabbix-agent2` | Состояние службы агента |
| `systemctl restart zabbix-agent2` | Перезапустить агент |
| `zabbix_agentd -c /etc/zabbix/zabbix_agentd.conf --foreground` | Запустить в foreground (отладка) |

## zabbix_get (от сервера к агенту)

| Command | Description |
|---------|-------------|
| `zabbix_get -s host -k system.cpu.load` | Получить метрику от агента |
| `zabbix_get -s host -p 10050 -k agent.ping` | Проверить связность |
| `zabbix_get -s host -k vm.memory.size[available]` | Доступная память |
| `zabbix_get -s host -k net.if.in[eth0]` | Входящий трафик сетевого интерфейса |

## zabbix_sender

| Command | Description |
|---------|-------------|
| `zabbix_sender -z server -s "Hostname" -k key -o value` | Отправить одно значение |
| `zabbix_sender -z server -i data.txt` | Отправить данные из файла |
| `zabbix_sender -z server -s "Host" -k key -o val --real-time` | Отправить в реальном времени |

Data file format (one item per line):
```
Hostname key value
Hostname key value timestamp
```

## Zabbix API (curl)

```bash
ZABBIX="http://zabbix/api_jsonrpc.php"

# Login and get token
curl -X POST "$ZABBIX" -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "method": "user.login",
  "params": {"user": "Admin", "password": "zabbix"},
  "id": 1
}'

# Get hosts (replace TOKEN)
curl -X POST "$ZABBIX" -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "method": "host.get",
  "params": {"output": ["hostid", "host", "status"]},
  "auth": "TOKEN", "id": 2
}'

# Get active problems
curl -X POST "$ZABBIX" -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "method": "problem.get",
  "params": {"recent": true, "sortfield": "eventid", "sortorder": "DESC"},
  "auth": "TOKEN", "id": 3
}'
```

## Key Built-in Item Keys

| Key | Description |
|-----|-------------|
| `system.cpu.load[,avg1]` | 1-min CPU load average |
| `vm.memory.size[available]` | Available memory (bytes) |
| `vfs.fs.size[/,pfree]` | Disk free percent |
| `net.if.in[eth0]` | Network RX bytes/sec |
| `net.if.out[eth0]` | Network TX bytes/sec |
| `proc.num[nginx]` | Running nginx processes |
| `agent.ping` | Agent reachability (1=OK) |
| `system.uptime` | System uptime (seconds) |
| `log[/var/log/app.log,ERROR]` | Log monitoring |
| `web.page.get[url]` | HTTP page content |
