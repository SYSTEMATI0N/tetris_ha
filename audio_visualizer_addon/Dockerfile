ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG C.UTF-8

RUN apk add --no-cache \
    python3 py3-pip py3-numpy py3-pyaudio \
    bluez pulseaudio pulseaudio-alsa alsa-utils \
    && pip3 install bleak

COPY run.sh /run.sh
COPY audio_visualizer.py /audio_visualizer.py

RUN chmod +x /run.sh

CMD [ "/run.sh" ]
