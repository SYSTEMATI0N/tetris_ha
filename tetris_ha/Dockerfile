ARG BUILD_FROM=ghcr.io/hassio-addons/base:14.4.1
FROM ${BUILD_FROM}

ENV LANG C.UTF-8
# включим venv в PATH сразу, чтобы python/PIP ссылались на окружение
ENV PATH="/venv/bin:${PATH}"

# 1) Устанавливаем необходимые system‑библиотеки и инструменты сборки
# 2) Создаём виртуальное окружение /venv
# 3) Апгрейдим pip/setuptools/wheel и ставим bleak
# 4) Чистим ненужные зависимости и кеш
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
    pip install --upgrade pip setuptools wheel && \
    pip install bleak && \
    apk del \
      build-base \
      libffi-dev \
      openssl-dev \
      linux-headers && \
    rm -rf /var/cache/apk/*

# Копируем скрипты
COPY run.sh /run.sh
COPY main.py /main.py

RUN chmod +x /run.sh

CMD ["/run.sh"]
