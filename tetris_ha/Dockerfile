ARG BUILD_FROM
FROM $BUILD_FROM
LABEL io.hass.name="Tetris HA" \
      io.hass.description="Tetris game visualizer for LED via BLE" \
      org.opencontainers.image.source="https://github.com/SYSTEMATI0N/tetris_ha"

ENV LANG C.UTF-8

RUN apk add --no-cache \
    python3 py3-pip py3-numpy py3-pyaudio \
    bluez pulseaudio pulseaudio-alsa alsa-utils \
    bash \
  && pip3 install bleak \
  && apk add --no-cache s6-overlay

COPY rootfs/ /  
COPY run.sh /run.sh  
COPY tetris.py /tetris.py  

RUN chmod +x /run.sh

ENTRYPOINT ["/init"]
CMD ["/run.sh"]
