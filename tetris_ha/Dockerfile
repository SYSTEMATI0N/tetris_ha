ARG BUILD_FROM=ghcr.io/hassio-addons/base-debian:14.0.3
FROM $BUILD_FROM

ENV LANG C.UTF-8

# Устанавливаем всё в одном слое
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      python3 python3-pip python3-numpy bluez bash && \
    pip3 install --no-cache-dir bleak && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Копируем скрипты
COPY run.sh /run.sh
COPY main.py /main.py

RUN chmod +x /run.sh

CMD ["/run.sh"]
