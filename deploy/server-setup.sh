#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/mail_v"
REPO_URL="https://github.com/Artemkz/mail_v.git"
SERVICE_PORT=8000

echo "==> Подготовка директории ${APP_DIR}"
mkdir -p "${APP_DIR}"

if [ -d "${APP_DIR}/.git" ]; then
  cd "${APP_DIR}"
  git fetch --all
  git reset --hard origin/main
  git pull --rebase origin main
else
  git clone "${REPO_URL}" "${APP_DIR}"
  cd "${APP_DIR}"
fi

echo "==> Установка системных пакетов"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip

echo "==> Виртуальное окружение Python"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

if [ ! -f .env ]; then
  cp .env.example .env
fi

echo "==> Запуск через PM2"
pm2 delete mail_v 2>/dev/null || true
pm2 start .venv/bin/uvicorn \
  --name mail_v \
  --cwd "${APP_DIR}" \
  --interpreter none \
  -- app.main:app --host 127.0.0.1 --port "${SERVICE_PORT}"
pm2 save

echo "==> Готово: ${APP_DIR}"
pm2 status mail_v
