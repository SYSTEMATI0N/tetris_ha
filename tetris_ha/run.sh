#!/usr/bin/env bash
# Это скрипт запуска вашего приложения.
# Виртуальное окружение уже активировано через PATH в Dockerfile.

echo "🕹️  Запуск Tetris HA на $(uname -m)"
exec python3 /main.py
