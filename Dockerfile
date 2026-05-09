FROM --platform=linux/amd64 ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:1
ENV WINEPREFIX=/root/.wine
ENV WINEARCH=win64
ENV WINEDEBUG=-all
ENV WINEESYNC=1
ENV WINEDLLOVERRIDES=winemenubuilder.exe=
ENV RESOLUTION=1280x800x24

RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y \
        wget curl gnupg2 ca-certificates \
        xvfb x11vnc novnc websockify \
        supervisor \
        python3 python3-pip \
        xdotool net-tools procps \
        fonts-liberation x11-apps imagemagick \
    && wget -qO /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -qO /etc/apt/sources.list.d/winehq-jammy.sources https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources \
    && apt-get update \
    && apt-get install -y --install-recommends winehq-staging \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install websocket-client pillow

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY start.sh /start.sh
COPY init_wine.sh /init_wine.sh

RUN chmod +x /start.sh /init_wine.sh

EXPOSE 5900 6080

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
