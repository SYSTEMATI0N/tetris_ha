ARG BUILD_FROM=ghcr.io/hassio-addons/base:14.4.1
FROM $BUILD_FROM

ENV LANG C.UTF-8

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-numpy \
    py3-pyaudio \
    bluez \
    pulseaudio \
    pulseaudio-alsa \
    alsa-utils \
    bash && \
    pip3 install --no-cache-dir bleak

COPY run.sh /run.sh
COPY main.py /main.py

RUN chmod +x /run.sh

CMD [ "/run.sh" ]
