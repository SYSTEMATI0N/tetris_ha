#!/usr/bin/env bash
# Теперь этот скрипт станет PID 1 внутри контейнера — всё, что дальше запустится,
# будет дочерним процессом PID 1 и не попытается вызвать s6-overlay-suexec.

echo "🕹️  Запуск Tetris HA на $(uname -m)"
exec python3 /main.py
