ARG BUILD_FROM=ghcr.io/hassio-addons/base:14.4.1
FROM $BUILD_FROM

ENV LANG C.UTF-8

# Устанавливаем системные зависимости и компиляторы для bleak
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-numpy \
    bluez \
    bash \
    build-base \
    libffi-dev \
    openssl-dev \
    linux-headers && \
    pip3 install --no-cache-dir bleak

# Копируем исполняемые файлы
COPY run.sh /run.sh
COPY main.py /main.py

RUN chmod +x /run.sh

CMD ["/run.sh"]
