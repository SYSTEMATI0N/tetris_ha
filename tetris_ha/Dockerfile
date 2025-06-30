ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8

# Установка зависимостей
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-numpy \
    py3-pyaudio \
    bluez \
    pulseaudio \
    pulseaudio-alsa \
    alsa-utils \
    bash

# Установка bleak
RUN pip3 install bleak

# Копируем файлы
COPY run.sh /
RUN chmod +x /run.sh

# Устанавливаем точку входа
CMD [ "/run.sh" ]
