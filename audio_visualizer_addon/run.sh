#!/bin/bash

echo "[INFO] Starting PulseAudio..."
pulseaudio --start
sleep 2

echo "[INFO] Starting audio visualizer..."
python3 /audio_visualizer.py
