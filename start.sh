#!/usr/bin/env bash
# Запуск DevOps Study Hub: backend + frontend. Остановка — Ctrl+C.
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PID=""
FRONTEND_PID=""
MONITOR_PID=""

for command in curl npm; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Ошибка: не найдена команда '$command'. Сначала выполните: bash setup.sh"
        exit 1
    fi
done

if [[ ! -x "$PROJECT_DIR/.venv/bin/uvicorn" ]]; then
    echo "Не найдена виртуальная среда Python. Сначала выполните: bash setup.sh"
    exit 1
fi
if [[ ! -d "$PROJECT_DIR/frontend/node_modules" ]]; then
    echo "Зависимости frontend не установлены. Сначала выполните: bash setup.sh"
    exit 1
fi

port_busy() {
    local port="$1"
    if curl --max-time 1 -sS "http://127.0.0.1:$port" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

cleanup() {
    trap - EXIT INT TERM HUP
    echo
    echo "Останавливаю DevOps Study Hub..."
    [[ -n "$MONITOR_PID" ]] && kill "$MONITOR_PID" 2>/dev/null || true
    [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
    [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
    [[ -n "$FRONTEND_PID" ]] && pkill -P "$FRONTEND_PID" 2>/dev/null || true
    [[ -n "$BACKEND_PID" ]] && wait "$BACKEND_PID" 2>/dev/null || true
    [[ -n "$FRONTEND_PID" ]] && wait "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM HUP

if port_busy 8000; then
    echo "Ошибка: порт 8000 уже занят. Остановите предыдущий backend и повторите запуск."
    exit 1
fi
if port_busy 5173; then
    echo "Ошибка: порт 5173 уже занят. Остановите предыдущий frontend и повторите запуск."
    exit 1
fi

echo "Запускаю backend..."
cd "$PROJECT_DIR/backend"
"$PROJECT_DIR/.venv/bin/uvicorn" main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

backend_ready=0
for _ in {1..30}; do
    if curl --max-time 1 -fsS http://127.0.0.1:8000/docs >/dev/null 2>&1; then
        backend_ready=1
        break
    fi
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        break
    fi
    sleep 0.5
done
if [[ "$backend_ready" -ne 1 ]]; then
    echo "Ошибка: backend не запустился. Проверьте зависимости и порт 8000."
    exit 1
fi

echo "Запускаю frontend (доступен из браузера Windows/WSL)..."
cd "$PROJECT_DIR/frontend"
npm run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!

frontend_ready=0
for _ in {1..30}; do
    if curl --max-time 1 -fsS http://127.0.0.1:5173/ >/dev/null 2>&1; then
        frontend_ready=1
        break
    fi
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        break
    fi
    sleep 0.5
done
if [[ "$frontend_ready" -ne 1 ]]; then
    echo "Ошибка: frontend не запустился. Проверьте зависимости и порт 5173."
    exit 1
fi

echo
echo "DevOps Study Hub запущен:"
echo "  Приложение: http://localhost:5173"
echo "  API:        http://localhost:8000/docs"
echo "Ничего больше запускать не нужно. Для остановки нажмите Ctrl+C."

(
    while kill -0 "$BACKEND_PID" 2>/dev/null; do sleep 2; done
    echo
    echo "ВНИМАНИЕ: backend неожиданно остановился. Перезапустите приложение."
) &
MONITOR_PID=$!

wait "$FRONTEND_PID"
