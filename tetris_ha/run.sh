#!/usr/bin/env bashio
bashio::log.info "Initializing PulseAudio..."
pulseaudio --start
sleep 2

bashio::log.info "Launching Tetris HA..."
exec s6-svscan /etc/services.d
