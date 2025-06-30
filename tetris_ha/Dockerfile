ARG BUILD_FROM=ghcr.io/hassio-addons/base:14.4.1
FROM ${BUILD_FROM}

ENV LANG C.UTF-8
ENV PATH="/venv/bin:${PATH}"

# Установка системных библиотек, создание виртуального окружения и установка зависимостей
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
    python3 -m venv /venv && \
    /venv/bin/pip install --upgrade pip setuptools wheel && \
    /venv/bin/pip install bleak aiohttp asyncio-mqtt && \
    apk del build-base libffi-dev openssl-dev linux-headers && \
    rm -rf /var/cache/apk/*

COPY run.sh /run.sh
COPY main.py /main.py

RUN chmod +x /run.sh

ENTRYPOINT ["/run.sh"]
