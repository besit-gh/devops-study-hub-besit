---
title: HTTP и HTTPS
module: networking
duration_min: 15
difficulty: beginner
tags: [networking, http, https, tls, ssl, headers, status-codes, curl]
exercises: 4
---

## Обзор

HTTP (HyperText Transfer Protocol) — протокол прикладного уровня, на котором основано большинство взаимодействий между сервисами современной инфраструктуры. DevOps-инженер сталкивается с HTTP в health checks, конфигурациях балансировщиков и reverse proxy, webhook-вызовах CI/CD, readiness probes контейнеров и интеграциях API. Базовых знаний хватает для простых настроек, но глубокое понимание позволяет диагностировать ночные инциденты, когда ошибка 502 распространяется по кластеру.

HTTP намеренно устроен просто: это stateless-протокол «запрос — ответ», в котором клиент отправляет структурированное сообщение, а сервер возвращает ответ. Отсутствие состояния упрощает масштабирование, но создаёт и источник ошибок: каждый запрос должен содержать необходимый контекст — учётные данные, тип содержимого и состояние сессии. Поэтому неправильно настроенные заголовки часто становятся причиной production-инцидентов. HTTPS добавляет поверх HTTP TLS для шифрования, аутентификации и проверки целостности. Поскольку современные сервисы обычно требуют HTTPS, понимание сертификатов TLS — практическая необходимость.

В DevOps знание HTTP напрямую связано с настройкой nginx, Caddy и HAProxy, ресурсами Ingress и Service в Kubernetes, сбором метрик Prometheus, health checks контейнеров, правилами API gateway и конвейерами наблюдаемости. Основные инструменты урока — `curl` и `openssl` — доступны почти на каждом сервере и должны быть среди первых средств диагностики, когда нарушается взаимодействие двух сервисов.

---

## Основные понятия

### Структура HTTP-запроса

Каждый HTTP-запрос имеет определённую текстовую структуру. Понимание этой структуры позволяет формировать запросы вручную, читать сырые журналы и находить некорректные запросы без графического интерфейса.

```
POST /api/v1/deployments HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGci...
Content-Type: application/json
Accept: application/json
X-Request-ID: 7f3d8c2a-1234-5678-abcd-ef0123456789
Content-Length: 47

{"service": "payments", "version": "v2.3.1"}
```

Четыре части:
1. **Строка запроса** — метод, путь и версия протокола
2. **Заголовки** — по одному на строку, пары ключ-значение через двоеточие
3. **Пустая строка** — обязательный разделитель; без неё разбор может завершиться ошибкой
4. **Тело** — обычно используется с POST, PUT и PATCH; должно соответствовать `Content-Type`

**Заголовок Host обязателен в HTTP/1.1.** Один сервер может обслуживать несколько виртуальных хостов на одном IP. Без `Host` сервер не понимает, к какому сайту обращается клиент. Отсутствующий или неверный `Host` часто вызывает неожиданные ответы 400 или 404 при диагностике прокси.

HTTP-ответы имеют похожую структуру, но первая строка содержит статус:

```
HTTP/1.1 201 Created
Content-Type: application/json; charset=utf-8
Location: /api/v1/deployments/9912
X-Request-ID: 7f3d8c2a-1234-5678-abcd-ef0123456789
Content-Length: 82

{"id": 9912, "service": "payments", "version": "v2.3.1", "status": "queued"}
```

**HTTP/1.1, HTTP/2 и HTTP/3:** в HTTP/2 меняется формат передачи (бинарные кадры, сжатие заголовков, мультиплексирование потоков через одно TCP-соединение), но семантика методов, статусов и заголовков остаётся прежней. HTTP/3 использует QUIC поверх UDP вместо TCP, дополнительно снижая блокировку очереди. На практике HTTP/2 почти всегда требует TLS, а мультиплексирование позволяет обслуживать много запросов через одно соединение, что влияет на настройку пулов соединений в прокси.

---

### Методы HTTP

| Метод | Назначение | Идемпотентный | Безопасный | Тело |
|---------|---------------------------------------|------------|------|------|
| GET | Получить ресурс | Да | Да | Нет |
| POST | Создать ресурс или запустить действие | Нет | Нет | Да |
| PUT | Полностью заменить ресурс | Да | Нет | Да |
| PATCH | Частично изменить ресурс | Нет | Нет | Да |
| DELETE | Удалить ресурс | Да | Нет | Нет |
| HEAD | Как GET, но без тела ответа | Да | Да | Нет |
| OPTIONS | Узнать, какие методы принимает сервер | Да | Да | Нет |

**Идемпотентность** означает, что N вызовов метода дают тот же результат, что и один вызов. **Безопасный метод** не изменяет состояние сервера.

**Зачем DevOps-инженеру идемпотентность:** от неё зависят автоматизация инфраструктуры и повторные попытки. Повторный PUT приводит ресурс к одному и тому же состоянию, а повторный POST может создать дубликаты. Учитывайте это при проектировании API и проверяйте `Retry-After`, чтобы понять, когда можно повторить запрос после 429 или 503.

**HEAD используют недостаточно часто.** Он подходит для health checks и проверки кэша: можно получить статус и заголовки ответа (включая `Content-Length` и `Last-Modified`) без скачивания тела. Это удобно, чтобы проверить наличие большого артефакта в объектном хранилище перед загрузкой.

```bash
# Check if an artifact exists without downloading it
curl -I https://artifacts.example.com/releases/app-v2.3.1.tar.gz
# HTTP/2 200
# Content-Length: 48291034
# Last-Modified: Tue, 14 Jan 2025 09:22:11 GMT
```

**OPTIONS и предварительная проверка CORS:** браузеры отправляют OPTIONS перед междоменным POST или PUT, чтобы узнать разрешённые методы и заголовки. Если API gateway или reverse proxy неправильно передаёт OPTIONS, браузер показывает CORS-ошибку, хотя сам API работает. При диагностике CORS проверьте заголовки `Access-Control-Allow-Origin` и `Access-Control-Allow-Methods` в ответе OPTIONS.

---

### Коды состояния HTTP

| Диапазон | Категория | Распространённые коды и значения |
|-------|--------------|--------------------------|
| 2xx | Успех | 200 OK, 201 Created, 202 Accepted, 204 No Content |
| 3xx | Перенаправление | 301 Moved Permanently, 302 Found, 304 Not Modified |
| 4xx | Ошибка клиента | 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity, 429 Too Many Requests |
| 5xx | Ошибка сервера | 500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout |

**Коды, которые чаще всего приходится диагностировать в production:**

| Код | Что он означает на практике | Где искать причину |
|------|------------------------|---------------|
| 400 | Некорректный запрос — неверное тело или отсутствует обязательное поле | Журналы приложения, тело запроса |
| 401 | Нет учётных данных или они недействительны | Журналы сервиса аутентификации, срок действия токена |
| 403 | Учётные данные верны, но прав недостаточно | Конфигурация IAM/RBAC, политика service mesh |
| 404 | На сервере нет такого пути | Зарегистрирован ли маршрут? Работает ли сервис? |
| 409 | Конфликт — ресурс уже существует или состояние не совпадает | Idempotency key, ограничения базы данных |
| 422 | Запрос синтаксически корректен, но недопустим по смыслу | Логика валидации приложения |
| 429 | Превышен лимит запросов — проверьте `Retry-After` | Конфигурация API gateway, логика повторных попыток клиента |
| 502 | Прокси не смог подключиться к backend или получил некорректный ответ | Журналы ошибок прокси, состояние backend |
| 503 | Backend сообщает о недоступности | Журналы backend, endpoint проверки состояния |
| 504 | Соединение с backend установлено, но ответ не пришёл вовремя | Тайм-аут прокси, медленный запрос |

**Различие между 502 и 504 критично.** 502 означает, что шлюз получил некорректный ответ или не получил его вовсе (отказ соединения, падение backend, неправильный HTTP). 504 означает, что соединение установлено, но backend не ответил в пределах тайм-аута. 502 указывает на остановленный процесс или неверный ответ, а 504 — на медленную работу или взаимную блокировку. В nginx проверьте `error.log`: там часто указана системная причина (`Connection refused`, `no live upstreams`).

**304 Not Modified** экономит трафик. Если у клиента есть кэшированная копия с `ETag` или `Last-Modified`, он отправляет `If-None-Match` или `If-Modified-Since`. Если ресурс не изменился, сервер возвращает 304 без тела, и клиент использует кэш. Неверные настройки CDN или заголовков кэширования, мешающие ответам 304, вызывают лишнюю передачу данных и замедляют загрузку страниц.

**201 и 202:** возвращайте 201, если ресурс уже создан и его URL известен (добавьте заголовок `Location`). Возвращайте 202, если работа поставлена в очередь или выполняется асинхронно и ресурс ещё не готов. Webhook CI/CD и API постановки заданий обычно возвращают 202.

---

### Основные HTTP-заголовки

Заголовки передают метаданные, управляющие кэшированием, аутентификацией, согласованием содержимого, маршрутизацией и наблюдаемостью. Понимание их назначения помогает настраивать прокси и диагностировать проблемы без догадок.

**Заголовки запроса:**

| Header | Purpose | Example |
|--------|---------|---------|
| `Host` | Target virtual host | `api.example.com` |
| `Authorization` | Credentials | `Bearer eyJ...` or `Basic dXNlcjpwYXNz` |
| `Content-Type` | Body format | `application/json` |
| `Accept` | Acceptable response formats | `application/json, */*;q=0.5` |
| `X-Request-ID` | Distributed tracing correlation | `7f3d8c2a-...` |
| `If-None-Match` | Cache validation via ETag | `"abc123"` |
| `X-Forwarded-For` | Original client IP behind a proxy | `203.0.113.42` |
| `User-Agent` | Identifies the client software | `curl/7.88.1` |

**Response headers:**

| Header | Purpose | Example |
|--------|---------|---------|
| `Content-Type` | Body format + encoding | `application/json; charset=utf-8` |
| `Cache-Control` | Caching directives | `max-age=3600, public` |
| `ETag` | Resource version fingerprint | `"d41d8cd9"` |
| `Location` | Redirect target or created resource URL | `/api/v1/users/42` |
| `Retry-After` | Seconds or date before retrying | `60` |
| `Set-Cookie` | Create a client-side cookie | `session=abc; HttpOnly; Secure` |
| `Strict-Transport-Security` | Enforce HTTPS | `max-age=31536000; includeSubDomains` |
| `X-Content-Type-Options` | Prevent MIME sniffing | `nosniff` |

**Кодирование `Authorization: Basic` — не шифрование.** Значение представляет собой `base64(username:password)` и легко декодируется обратно. Basic-аутентификация по обычному HTTP раскрывает учётные данные при передаче. Используйте её только через HTTPS.

```bash
# Decode a Basic auth header to verify what's being sent
echo "dXNlcjpteXNlY3JldA==" | base64 -d
# user:mysecret
```

**`X-Forwarded-For` можно подделать.** Клиент может указать в заголовке любое значение. Если приложение использует его для контроля доступа по IP или ограничения частоты запросов, настройте балансировщик так, чтобы он перезаписывал заголовок, а не дополнял его. Иначе злоумышленник сможет указать доверенный IP и обойти ограничения. В nginx используйте `real_ip_module`, принимая значение только от доверенного вышестоящего узла.

**Корреляционные заголовки (`X-Request-ID`, `X-Trace-ID`) незаменимы при распределённой диагностике.** Создавайте их на входе (в API-шлюзе или первом сервисе), передавайте во все последующие вызовы и записывайте в журналы каждого сервиса. Когда пользователь сообщает об ошибке, по одному идентификатору можно восстановить всю цепочку вызовов.

**Директивы `Cache-Control`, которые нужно знать:**

| Directive | Meaning |
|-----------|---------|
| `no-store` | Never cache — contains sensitive data |
| `no-cache` | Can cache, but must revalidate with the server before serving |
| `max-age=N` | Cache is valid for N seconds |
| `private` | Only the client browser can cache — not a shared CDN |
| `public` | Any cache (CDN, proxy) can store this response |
| `s-maxage=N` | Override `max-age` for shared caches (CDNs) specifically |

**`Strict-Transport-Security` (HSTS) работает по принципу одностороннего переключателя.** Получив заголовок HSTS, браузер отказывается подключаться к домену по обычному HTTP в течение `max-age`. Если позже потребуется вернуться к HTTP (например, из-за неправильной настройки сертификата), браузеры, уже получившие HSTS, не подключатся до истечения `max-age`. Не задавайте срок в год, пока не убедитесь, что HTTPS работает стабильно.

---

### HTTPS и TLS

HTTPS — это HTTP, передаваемый через защищённый канал TLS (Transport Layer Security). TLS обеспечивает три свойства:

1. **Конфиденциальность** — трафик зашифрован, наблюдатель в сети видит только шифротекст.
2. **Аутентификация** — сервер предъявляет сертификат, подтверждающий его подлинность.
3. **Целостность** — код аутентификации сообщения (MAC) позволяет обнаружить изменение данных при передаче.

**Упрощённое рукопожатие TLS 1.3:**

```
Client → Server: ClientHello
                 - Max TLS version supported: TLS 1.3
                 - Supported cipher suites: TLS_AES_256_GCM_SHA384, ...
                 - Key share (Diffie-Hellman public value)

Server → Client: ServerHello
                 - Selected cipher suite
                 - Server's key share
                 - Certificate (signed by a CA)
                 - CertificateVerify (proves server owns the private key)
                 - Finished (MAC of the entire handshake)

Client → Server: Finished
Both sides:      Derive symmetric session keys from the DH exchange
                 Encrypted application data flows
```

В TLS 1.3 рукопожатие завершается за **один обмен туда-обратно** (1-RTT), тогда как в TLS 1.2 требовалось два. Это снижает задержку соединения, что особенно важно для сервисов с множеством коротких HTTPS-вызовов. В TLS 1.3 также удалены слабые наборы шифров (RC4, 3DES) и обмен ключами RSA; прямая секретность стала обязательной.

**Цепочка доверия сертификатов:**

```
Root CA          (pre-installed in your OS/browser trust store)
  └── Intermediate CA   (issued by Root CA, used to sign end-entity certs)
        └── example.com certificate   (presented by your server)
```

Сервер должен передавать полную цепочку (свой сертификат и промежуточные сертификаты). Если передаётся только конечный сертификат, клиенты без промежуточного сертификата в кэше не смогут проверить цепочку — даже если сам сертификат действителен. Это одна из самых распространённых ошибок настройки TLS в production.

**Типичные проблемы с сертификатами и соответствующие ошибки curl:**

```bash
# Expired certificate
# curl: (60) SSL certificate problem: certificate has expired
# Fix: renew the certificate. Use monitoring to alert before expiry.

# Hostname mismatch — cert is for a different domain
# curl: (60) SSL: no alternative certificate subject name matches
#       target host name 'api.example.com'
# Fix: cert must include the hostname in Subject or Subject Alternative Names (SAN).
# Wildcard certs (*.example.com) cover exactly one subdomain level —
# *.example.com covers api.example.com but NOT deep.api.example.com.

# Self-signed or unknown CA
# curl: (60) SSL certificate problem: self-signed certificate in certificate chain
# Fix in prod: use a real CA (Let's Encrypt, internal PKI).
# Fix for internal tooling: trust the CA explicitly:
curl --cacert /etc/ssl/certs/internal-ca.crt https://internal.example.com/

# Never bypass verification in production — this disables authentication entirely.
# -k / --insecure makes the encrypted tunnel meaningless because you accept any cert,
# including an attacker's. Only use it for local development throwaway testing.
curl -k https://localhost:8443/
```

**Проверьте действующий сертификат с помощью openssl:**

```bash
# See expiry, subject, and issuer
openssl s_client -connect api.example.com:443 -servername api.example.com \
  </dev/null 2>/dev/null \
  | openssl x509 -noout -dates -subject -issuer

# notBefore=Jan 14 00:00:00 2025 GMT
# notAfter=Apr 14 23:59:59 2025 GMT
# subject=CN=api.example.com
# issuer=C=US, O=Let's Encrypt, CN=R11

# See Subject Alternative Names (every hostname the cert is valid for)
openssl s_client -connect api.example.com:443 -servername api.example.com \
  </dev/null 2>/dev/null \
  | openssl x509 -noout -ext subjectAltName
# subjectAltName: DNS:api.example.com, DNS:www.example.com

# Verify the full chain; check each depth level for errors
openssl s_client -connect api.example.com:443 -servername api.example.com \
  </dev/null 2>&1 | grep -E "depth|Verify|error"
# depth=2 C=US, O=Internet Security Research Group, CN=ISRG Root X1
# depth=1 C=US, O=Let's Encrypt, CN=R11
# depth=0 CN=api.example.com
# Verify return code: 0 (ok)

# Check how many days until expiry (paste into monitoring scripts)
expiry=$(openssl s_client -connect api.example.com:443 -servername api.example.com \
  </dev/null 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
openssl x509 -checkend $((30*86400)) -noout <<< \
  "$(openssl s_client -connect api.example.com:443 -servername api.example.com \
     </dev/null 2>/dev/null | openssl x509)"
# exit code 1 = expires within 30 days; 0 = still valid
```

**SNI (Server Name Indication)** объясняет, зачем нужен параметр `-servername`. Если на сервере размещено несколько HTTPS-виртуальных хостов (один IP и много доменов), сервер должен выбрать сертификат ещё до завершения TLS-рукопожатия — до получения заголовка `Host`. SNI передаёт имя хоста в сообщении ClientHello. Без него сервер отправляет сертификат по умолчанию, который часто не подходит. Всегда указывайте `-servername` при использовании `openssl s_client`.

**Взаимный TLS (mTLS):** обычный TLS аутентифицирует только сервер. При mTLS сертификаты предъявляют обе стороны: клиент подтверждает свою личность серверу. Это распространено в service mesh (Istio, Linkerd), где у каждого Pod есть сертификат, а сервисы проверяют друг друга без токенов уровня приложения. Ошибки `400 No required SSL certificate was sent` или `SSL_ERROR_HANDSHAKE_FAILURE_ALERT` часто означают, что сервер требует не настроенный у клиента сертификат.

---

### Диагностика HTTP с помощью curl

`curl` — универсальный инструмент диагностики HTTP. Он доступен почти везде, поддерживает автоматизацию через скрипты и позволяет изучать каждый уровень протокола.

```bash
# Verbose output: shows TLS handshake, request headers, response headers, body.
# Lines with > are sent by the client; lines with < are received from the server.
curl -v https://api.example.com/health

# HEAD request — response headers only, no body download
curl -I https://api.example.com/health

# Show response headers prepended to body (-s silences progress meter)
curl -si https://api.example.com/health

# POST with JSON body; always set Content-Type explicitly
curl -X POST https://api.example.com/users \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"name": "Alice", "role": "admin"}'

# POST with a file as the body (useful for large payloads)
curl -X POST https://api.example.com/configs \
     -H "Content-Type: application/json" \
     -d @config.json

# Follow redirects — critical for 301/302 chains (e.g., HTTP → HTTPS redirect)
curl -L https://api.example.com/old-path

# Set a connect and total timeout; always do this in automation scripts.
# Without timeouts, a hung connection blocks your pipeline indefinitely.
curl --connect-timeout 5 --max-time 30 https://api.example.com/health

# Trust a private CA certificate (internal services with self-managed PKI)
curl --cacert /etc/ssl/certs/internal-ca.crt https://internal.svc/health

# Detailed timing breakdown — paste this template into scripts to profile latency
curl -o /dev/null -s -w \
  "dns_resolution: %{time_namelookup}s\n\
tcp_connect:    %{time_connect}s\n\
tls_handshake:  %{time_appconnect}s\n\
ttfb:           %{time_starttransfer}s\n\
total:          %{time_total}s\n\
http_code:      %{http_code}\n" \
  https://api.example.com/health

# Output example:
# dns_resolution: 0.003s
# tcp_connect:    0.018s
# tls_handshake:  0.045s
# ttfb:           0.112s
# total:          0.114s
# http_code:      200

# Override DNS — test a new backend without changing real DNS
# Useful when verifying a deployment before a DNS cutover
curl --resolve api.example.com:443:192.168.1.50 https://api.example.com/health

# Send a custom Host header — simulate a virtual host on a proxy
curl -H "Host: api.example.com" http://10.0.0.1/health

# Write response body to a file and print headers to stdout
curl -D - -o response.json https://api.example.com/data

# Only output the HTTP status code (useful in scripts)
curl -o /dev/null -s -w "%{http_code}" https://api.example.com/health
```

**`time_appconnect` показывает затраты времени на TLS.** Разница между `time_appconnect` и `time_connect` — это время самого TLS-рукопожатия. Если оно велико (более 100 мс), проверьте согласование шифров, длину цепочки сертификатов и настройку OCSP stapling. Если велико уже `time_connect`, проблема связана с сетью или TCP, а не с TLS.

**Коды завершения важны в скриптах.** По умолчанию `curl` возвращает код 0 даже при ответах 4xx/5xx: с точки зрения curl, корректный HTTP-ответ означает успех. Используйте `--fail` (или `-f`), чтобы при HTTP-ошибках возвращался код 22. Параметр `--fail-with-body` (curl ≥ 7.76) возвращает ненулевой код при ошибке, но сохраняет тело ответа в выводе — это полезно для чтения сообщений API.

```bash
# Will exit 0 even if the server returns 500 — wrong for health checks
curl https://api.example.com/health

# Will exit 22 on 4xx/5xx — correct for CI scripts and health checks
curl --fail https://api.example.com/health

# Exit non-zero on error AND print the error response body
curl --fail-with-body https://api.example.com/health
```

---

### Типовые схемы настройки HTTP в Nginx

Как DevOps-инженер, вы настраиваете поведение HTTP на уровне обратного прокси, а не только используете его со стороны клиента. Ниже приведены наиболее распространённые схемы.

```nginx
server {
    listen 80;
    server_name api.example.com;

    # Redirect all HTTP to HTTPS — use 301 for permanent, 302 for temporary
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate     /etc/ssl/certs/api.example.com.crt;  # includes full chain
    ssl_certificate_key /etc/ssl/private/api.example.com.key;

    # Modern TLS: disable TLS 1.0 and 1.1 (deprecated, insecure)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers   ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;  # Let clients pick in TLS 1.3

    # HSTS: tell browsers to only connect via HTTPS for 1 year
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Security headers
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;

    location /api/ {
        proxy_pass         http://backend:8080;

        # Pass the real client IP to the backend
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   Host $host;

        # Propagate the correlation ID; generate one if the client didn't send it
        proxy_set_header   X-Request-ID $request_id;

        # Timeouts: tune these for your backend's expected response times
        proxy_connect_timeout 5s;
        proxy_send_timeout    60s;
        proxy_read_timeout    60s;
    }

    # Health check endpoint — doesn't proxy, answered by nginx directly
    location /healthz {
        return 200 "ok\n";
        add_header Content-Type text/plain;
    }
}
```

**`proxy_set_header Host $host` необходим.** Без него nginx передаёт внутренний адрес backend-сервера в заголовке `Host`, из-за чего маршрутизация виртуальных хостов на backend перестаёт работать. Это частая причина неожиданных ответов 404 при настройке нового прокси.

**`proxy_read_timeout` и тайм-аут приложения:** `proxy_read_timeout` задаёт, сколько nginx ждёт ответа от backend. Если запрос к базе данных на backend занимает 30 секунд, задайте значение не меньше 35 секунд. Если первым сработает тайм-аут backend, он вернёт 500 или закроет соединение, а nginx вернёт 502. Если первым истечёт тайм-аут nginx, клиент получит 504. Понимание того, какой тайм-аут сработал, помогает найти нужный уровень настройки.

---

### Проверки состояния в Kubernetes

Kubernetes использует HTTP-проверки для определения состояния контейнеров. Понимание типов проб помогает предотвратить сбои при развёртывании.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-service
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        image: api:v2.3.1
        ports:
        - containerPort: 8080
        livenessProbe:
          # If this fails, Kubernetes restarts the container.
          # Use for detecting deadlocks or unrecoverable errors.
          # Don't check dependencies here — if the DB is down, you don't
          # want to restart all pods and cause a thundering herd on recovery.
          httpGet:
            path: /healthz/live
            port: 8080
          initialDelaySeconds: 10   # Give the app time to start
          periodSeconds: 15
          failureThreshold: 3       # 3 consecutive failures → restart
          timeoutSeconds: 5

        readinessProbe:
          # If this fails, Kubernetes removes the pod from Service endpoints.
          # Traffic stops routing to it, but the pod is NOT restarted.
          # Use for checking dependencies (DB connections, cache warm-up).
          # This is what prevents a new deployment from receiving traffic
          # before it's actually ready.
          httpGet:
            path: /healthz/ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
          failureThreshold: 2
          timeoutSeconds: 3

        startupProbe:
          # Kubernetes won't run liveness/readiness until this passes.
          # Use for slow-starting apps (JVM warm-up, large model loading).
          # failureThreshold * periodSeconds = max startup time allowed (300s here).
          httpGet:
            path: /healthz/startup
            port: 8080
          failureThreshold: 30
          periodSeconds: 10
```

**Путаница между Liveness и Readiness — одна из самых частых ошибок конфигурации.** Если добавить проверку зависимостей в liveness-пробу и зависимый сервис начнёт нестабильно работать, Kubernetes перезапустит все исправные Pod и усугубит сбой. Liveness отвечает на вопрос «процесс жив и не завис?». Readiness — «готов ли Pod прямо сейчас принимать трафик?».

---

## Примеры

### Пример 1. Диагностика 502 Bad Gateway в конфигурации прокси

**Сценарий:** перед API развернули новый обратный прокси nginx, и пользователи получают ошибки 502. Найдите и устраните причину.

```bash
# Step 1: Confirm the 502 and get the full response headers
curl -si https://api.example.com/health
# HTTP/2 502
# server: nginx/1.24.0
# content-type: text/html
# (nginx error page body)

# Step 2: Check if the backend is reachable at all from the proxy server
# SSH into the proxy and test the backend directly (bypassing nginx)
curl -si http://backend-service:8080/health
# curl: (7) Failed to connect to backend-service port 8080: Connection refused

# Connection refused = process is not running or wrong port.
# If we got a response here, the problem is in the nginx config, not the backend.

# Step 3: Verify nginx config syntax
nginx -t
# nginx: [emerg] unknown directive "proxy_pss" in /etc/nginx/conf.d/api.conf:12
# Fix the typo. Reload nginx.

# Step 4: After fixing the config, reload nginx without downtime
nginx -s reload

# Step 5: Verify the fix
curl -si https://api.example.com/health
# HTTP/2 200
# content-type: application/json
# x-request-id: 3f9c1a2b-...
# {"status": "ok"}

# Step 6: Verify the X-Forwarded-For header reaches the backend correctly
curl -si https://api.example.com/headers   # an endpoint that echoes request headers
# Confirm "X-Forwarded-For" contains your real IP, not the proxy's internal IP
```

---

### Пример 2. Диагностика истечения TLS-сертификата до возникновения сбоя

**Сценарий:** создайте shell-скрипт, который проверяет срок действия сертификатов списка сервисов и возвращает ненулевой код, если срок любого сертификата истекает в течение 30 дней. Запускайте его в CI по расписанию.

```bash
#!/usr/bin/env bash
# cert-check.sh — check TLS certificate expiry for a list of hostnames
# Exit code 1 if any cert expires within WARN_DAYS days.

set -euo pipefail

WARN_DAYS=30
WARN_SECONDS=$((WARN_DAYS * 86400))
FAILED=0

HOSTS=(
  "api.example.com:443"
  "auth.example.com:443"
  "grafana.internal.example.com:443"
)

check_cert() {
  local host_port="$1"
  local host="${host_port%%:*}"
  local port="${host_port##*:}"

  # Fetch the certificate; -servername is essential for SNI
  local cert
  cert=$(openssl s_client \
    -connect "$host_port" \
    -servername "$host" \
    </dev/null 2>/dev/null \
    | openssl x509 2>/dev/null)

  if [[ -z "$cert" ]]; then
    echo "ERROR: Could not retrieve certificate for $host_port"
    return 1
  fi

  # Check if cert expires within WARN_SECONDS
  if ! echo "$cert" | openssl x509 -checkend "$WARN_SECONDS" -noout; then
    local expiry
    expiry=$(echo "$cert" | openssl x509 -noout -enddate | cut -d= -f2)
    echo "WARNING: $host certificate expires at: $expiry (within ${WARN_DAYS} days)"
    return 1
  else
    local expiry
    expiry=$(echo "$cert" | openssl x509 -noout -enddate | cut -d= -f2)
    echo "OK: $host valid until $expiry"
    return 0
  fi
}

for host_port in "${HOSTS[@]}"; do
  check_cert "$host_port" || FAILED=1
done

exit "$FAILED"
```

```bash
# Run the script
chmod +x cert-check.sh
./cert-check.sh

# OK: api.example.com valid until Apr 14 23:59:59 2025 GMT
# OK: auth.example.com valid until Mar 02 12:00:00 2025 GMT
# WARNING: grafana.internal.example.com certificate expires at:
#          Feb 01 00:00:00 2025 GMT (within 30 days)

# Verify the exit code for CI pipeline integration
echo "Exit code: $?"
# Exit code: 1  (grafana cert is expiring — pipeline fails, alert fires)
```

---

### Пример 3. Поиск причины медленного вызова API с помощью таймингов curl

**Сценарий:** пользователи жалуются на медленный ответ конкретного API-эндпоинта. Используйте разбивку времени curl, чтобы определить, где возникает задержка: DNS, TCP, TLS или само приложение.

```bash
# curl timing template — measures each phase of the request lifecycle
cat > /tmp/curl-timing.fmt << 'EOF'
    dns_resolution:  %{time_namelookup}s
    tcp_connect:     %{time_connect}s
    tls_handshake:   %{time_appconnect}s
    request_sent:    %{time_pretransfer}s
    ttfb:            %{time_starttransfer}s  <- server processing time starts here
    total:           %{time_total}s
    http_code:       %{http_code}
    bytes_received:  %{size_download} bytes
EOF

# Run 5 times to see variance (spot intermittent slowness)
for i in {1..5}; do
  echo "--- Run $i ---"
  curl -o /dev/null -s -w "@/tmp/curl-timing.fmt" \
    -H "Authorization: Bearer $TOKEN" \
    https://api.example.com/reports/summary
  echo
done

# Example output showing a slow backend (TTFB is the problem):
# --- Run 1 ---
#     dns_resolution:  0.003s
#     tcp_connect:     0.019s
#     tls_handshake:   0.048s
#     request_sent:    0.048s
#     ttfb:            3.241s   <- 3.2 seconds in backend processing
#     total:           3.243s
#     http_code:       200

# --- Run 2 ---
#     dns_resolution:  0.003s
#     tcp_connect:     0.020s
#     tls_handshake:   0.046s
#     ttfb:            0.087s   <- fast this time — intermittent problem
#     total:           0.089s

# Diagnosis: TLS and TCP are consistently fast (~50ms combined).
# TTFB spikes indicate slow queries or lock contention in the backend.
# Next step: check backend APM traces / slow query log for /reports/summary.

# Verify your endpoint handles the Authorization header correctly:
curl -v -o /dev/null -H "Authorization: Bearer $TOKEN" \
  https://api.example.com/reports/summary 2>&1 | grep -E "< HTTP|> Auth"
# > Authorization: Bearer eyJ...
# < HTTP/2 200
```

---

### Пример 4. Проверка эндпоинта Readiness в Kubernetes

**Сценарий:** перед развёртыванием нового сервиса в Kubernetes проверьте корректную работу эндпоинтов состояния, в том числе при отказах.

```bash
# Run the container locally to test health endpoints before pushing
docker run -d --name api-test -p 8080:8080 api:v2.3.1

# 1. Test the liveness endpoint (should always return 200 if process is alive)
curl -si http://localhost:8080/healthz/live
# HTTP/1.1 200 OK
# Content-Type: application/json
# {"status": "alive"}

# 2. Test the readiness endpoint (checks DB connection, cache, etc.)
curl -si http://localhost:8080/healthz/ready
# HTTP/1.1 200 OK
# {"status": "ready", "db": "connected", "cache": "connected"}

# 3. Simulate a dependency failure — stop the DB and recheck readiness
docker stop postgres-dev
curl -si http://localhost:8080/healthz/ready
# HTTP/1.1 503 Service Unavailable          <- correct: 503, not 200
# {"status": "not ready", "db": "unreachable", "cache": "connected"}

# Critical: a 503 readiness probe must return a non-2xx status code.
# If the endpoint returns 200 with {"status": "error"} in the body,
# Kubernetes will think it's healthy — it only checks the HTTP status code.

# 4. Simulate what Kubernetes does: check exit code from curl --fail
curl --fail -si http://localhost:8080/healthz/ready
echo "Exit: $?"
# Exit: 22  <- non-zero, Kubernetes marks pod NotReady, stops routing traffic

# 5. Test the startup probe path
curl -si http://localhost:8080/healthz/startup
# HTTP/1.1 200 OK
# {"status": "started", "migrations": "complete"}

# 6. Cleanup
docker stop api-test && docker rm api-test
```

---

## Практические задания

### Задание 1. Разберите полный HTTP-обмен

С помощью `curl -v` запишите полный HTTP-обмен с выбранным API (если своего нет, используйте `https://httpbin.org`). По подробному выводу:

1. Определите версию TLS и согласованный набор шифров.
2. Найдите значение заголовка ответа `Content-Type` и объясните смысл параметра `charset`.
3. Определите использованную версию HTTP (HTTP/1.1 или HTTP/2). Если использовался HTTP/2, объясните, почему в подробном выводе меньше заголовков, чем было бы при HTTP/1.1.
4. Повторите запрос к тому же URL и сравните `time_appconnect`. Объясните, почему во втором запросе значение может быть нулевым.

*Hint:* `curl -v --write-out "\ntls: %{ssl_version} %{ssl_cipher}\n" https://httpbin.org/get`

---

### Задание 2. Воспроизведите и исправьте типичную ошибку 4xx

Используйте `https://httpbin.org`, чтобы вызвать с помощью `curl` каждую из следующих ошибок, сохранить ответ и объяснить, какое изменение запроса исправляет ситуацию:

1. Отправьте `POST` на `https://httpbin.org/post` с телом JSON, но **без** заголовка `Content-Type`. Изучите ответ, добавьте правильный заголовок и сравните результат.
2. Отправьте запрос к `https://httpbin.org/basic-auth/admin/secret` без учётных данных и изучите код статуса. Затем передайте корректный заголовок `Authorization: Basic` (вычислите значение base64 самостоятельно, не используйте `curl -u`).
3. Отправьте запрос к `https://httpbin.org/status/429` и изучите заголовки ответа. Напишите фрагмент Bash, который считывает значение `Retry-After` и ждёт указанное время перед повторной попыткой.

---

### Задание 3. Изучите и проверьте цепочку TLS-сертификатов

Выберите любой публичный HTTPS-сайт (или `api.github.com`) и с помощью `openssl s_client` ответьте на вопросы:

1. Сколько сертификатов в цепочке? Укажите каждый из них (subject CN) и его роль (корневой, промежуточный или конечный).
2. Какова точная дата истечения конечного сертификата?
3. Покрывает ли сертификат только указанный хост или дополнительные имена тоже? Перечислите все Subject Alternative Names.
4. Какая версия TLS была согласована? Как заставить `openssl s_client` попытаться использовать только TLS 1.1 и какого результата вы ожидаете?
5. Напишите однострочную команду, возвращающую код `1`, если сертификат истекает в течение следующих 14 дней, и код `0` в противном случае.

---

### Задание 4. Создайте скрипт проверки состояния для CI-конвейера

Напишите скрипт Bash `wait-for-healthy.sh`, который:

1. Принимает URL первым аргументом и необязательный тайм-аут в секундах вторым аргументом (по умолчанию 60 секунд).
2. Проверяет URL каждые 5 секунд с помощью `curl --fail --max-time 5`.
3. Возвращает код `0`, как только эндпоинт отвечает статусом 2xx.
4. Если до истечения общего тайм-аута эндпоинт не стал доступен, возвращает код `1` и выводит понятное сообщение об ошибке.
5. При каждой проверке выводит строку состояния с временной меткой.

Проверьте скрипт на `https://httpbin.org/status/200` (успех сразу) и `https://httpbin.org/status/503` (должен истечь тайм-аут).

---

### Быстрая проверка

1. Декодируйте учётные данные Basic Auth — значение, которое передают в заголовке `Authorization`.

   ```bash
   echo "YWRtaW46c2VjcmV0" | base64 -d
   ```

   ```expected_output
   admin:secret
   ```

Подсказка: учётные данные Basic Auth кодируются в Base64, поэтому понадобится инструмент для обратного декодирования.
Подсказка: используйте `echo '<encoded_string>' | base64 --decode`, чтобы получить исходные учётные данные в открытом виде.

2. Определите класс HTTP-статуса по коду — это полезно при написании универсальных обработчиков ответов.

   ```python
   code = 429; print(f'{code // 100}xx')
   ```

   ```expected_output
   4xx
   ```
Подсказка: классы HTTP-статусов определяются первой цифрой и обозначают категории ответов.
Подсказка: проверьте, равна ли первая цифра кода 4. Такой класс обозначается шаблоном `<цифра>xx`; найдите его название в спецификации HTTP.
