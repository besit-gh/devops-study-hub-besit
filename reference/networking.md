# Сети — краткая справка

## Проверка связности

| Command | Description |
|---------|-------------|
| `ping -c 4 host` | Проверка ICMP echo (4 пакета) |
| `traceroute host` | Проследить маршрут пакетов |
| `tracepath host` | Аналог traceroute, права root не нужны |
| `mtr host` | Интерактивная комбинация traceroute и ping |
| `nc -zv host port` | Проверить доступность TCP-порта |
| `nc -zvw3 host port` | Тайм-аут 3 секунды |
| `telnet host port` | Ручная проверка TCP-подключения |
| `curl -I url` | Только HTTP-заголовки ответа |
| `curl -v url` | Подробный HTTP-вывод (TLS и заголовки) |

## DNS

| Command | Description |
|---------|-------------|
| `nslookup domain` | Базовый DNS-запрос |
| `dig domain` | Подробный DNS-запрос |
| `dig domain A` | Запрос A-записей |
| `dig domain MX` | Запрос MX-записей |
| `dig @8.8.8.8 domain` | Запрос к определённому DNS-резолверу |
| `dig +short domain` | Только IP-адрес |
| `dig -x 1.2.3.4` | Обратный DNS-запрос |
| `host domain` | Простой прямой и обратный DNS-запрос |
| `resolvectl query domain` | Запрос через systemd-resolved |

## Порты и сокеты

| Command | Description |
|---------|-------------|
| `ss -tlnp` | Слушающие TCP-сокеты и PID |
| `ss -ulnp` | Слушающие UDP-сокеты |
| `ss -s` | Сводка по сокетам |
| `netstat -tlnp` | Устаревший способ просмотра слушающих TCP-сокетов |
| `lsof -i :port` | Какой процесс использует порт |
| `lsof -i tcp:8080` | Конкретный TCP-порт |
| `fuser port/tcp` | PID процесса, использующего порт |

## Интерфейсы и маршрутизация

| Command | Description |
|---------|-------------|
| `ip addr` | Показать интерфейсы и IP-адреса |
| `ip link` | Показать состояние интерфейсов |
| `ip route` | Показать таблицу маршрутизации |
| `ip route add 10.0.0.0/8 via gw` | Добавить статический маршрут |
| `ip neigh` | Таблица ARP/соседей |
| `ifconfig` | Устаревшая настройка интерфейса |
| `route -n` | Устаревшая таблица маршрутизации |
| `ethtool eth0` | Аппаратные сведения об интерфейсе |

## Примеры curl

| Command | Description |
|---------|-------------|
| `curl -X POST -d '{"k":"v"}' -H "Content-Type: application/json" url` | Отправить JSON методом POST |
| `curl -u user:pass url` | Базовая аутентификация |
| `curl -H "Authorization: Bearer TOKEN" url` | Токен Bearer |
| `curl -o file url` | Скачать в файл |
| `curl -L url` | Следовать перенаправлениям |
| `curl -k url` | Пропустить проверку TLS |
| `curl -w "%{http_code}" -o /dev/null -s url` | Только HTTP-код ответа |
| `curl --max-time 5 url` | Задать тайм-аут |
| `curl -x proxy:port url` | Использовать прокси |

## Межсетевой экран (iptables / nftables)

| Command | Description |
|---------|-------------|
| `iptables -L -n` | Показать правила |
| `iptables -A INPUT -p tcp --dport 22 -j ACCEPT` | Разрешить SSH |
| `iptables -A INPUT -j DROP` | Запретить всё остальное по умолчанию |
| `iptables-save > rules.v4` | Сохранить правила |
| `ufw status` | Состояние межсетевого экрана Ubuntu |
| `ufw allow 22/tcp` | Разрешить порт |
| `ufw enable` | Включить межсетевой экран |

## Захват сетевых пакетов

| Command | Description |
|---------|-------------|
| `tcpdump -i eth0` | Захватывать пакеты на интерфейсе |
| `tcpdump -i eth0 port 80` | Фильтровать по порту |
| `tcpdump -i eth0 host 1.2.3.4` | Фильтровать по узлу |
| `tcpdump -i eth0 -w file.pcap` | Записать в файл |
| `tcpdump -r file.pcap` | Прочитать из файла |
