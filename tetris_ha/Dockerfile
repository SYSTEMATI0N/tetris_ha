ARG BUILD_FROM=ghcr.io/hassio-addons/base-debian:14.0.3
FROM $BUILD_FROM

ENV LANG C.UTF-8

# Установка зависимостей
RUN apt-get update && \
    apt-get install -y \
        python3 \
        python3-pip \
        python3-numpy \
        python3-pyaudio \
        bluez \
        pulseaudio \
        alsa-utils && \
    pip3 install bleak && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Копируем файлы
COPY run.sh /run.sh
COPY main.py /main.py

# Устанавливаем разрешения
RUN chmod +x /run.sh

CMD [ "/run.sh" ]
