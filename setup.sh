#!/usr/bin/env bash
# Однократная подготовка DevOps Study Hub для Linux и WSL2.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

for command in python3 node npm git curl; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Не найдена команда '$command'. Установите её и повторите запуск."
        exit 1
    fi
done

python3 - <<'PY'
import sys
if sys.version_info < (3, 12):
    raise SystemExit("Требуется Python 3.12 или новее.")
print(f"Python: {sys.version.split()[0]}")
PY

node -e 'const v=process.versions.node.split(".").map(Number); if (v[0] < 18) { console.error("Требуется Node.js 18 или новее."); process.exit(1); } console.log("Node.js:", process.version)'
npm_version="$(npm --version)"
npm_major="${npm_version%%.*}"
if (( npm_major < 9 )); then
    echo "Требуется npm 9 или новее; установлена версия $npm_version."
    exit 1
fi
echo "npm: $npm_version"

if [[ ! -d .venv ]]; then
    echo "Создаю виртуальную среду Python..."
    python3 -m venv .venv
fi

echo "Устанавливаю зависимости backend..."
.venv/bin/python -m pip install -r backend/requirements.txt

if [[ ! -f backend/.env ]]; then
    cp backend/.env.example backend/.env
    echo "Создан backend/.env из шаблона."
fi

echo "Устанавливаю зависимости frontend..."
cd "$PROJECT_DIR/frontend"
if [[ -f package-lock.json ]]; then
    npm ci --no-audit --no-fund
else
    npm install --no-audit --no-fund
fi

echo
echo "Готово. Запустите приложение командой:"
echo "  cd '$PROJECT_DIR' && ./start.sh"
echo
echo "Откройте http://localhost:5173."
echo "Уроки, тесты и проекты доступны без API-ключа."
echo "Для ИИ-функций укажите OPENAI_API_KEY в backend/.env и перезапустите приложение."
