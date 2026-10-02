FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl lib32gcc-s1 lib32stdc++6 python3 procps \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -o -g 1000 pz && useradd -o -u 1000 -g pz -m pz \
    && mkdir -p /opt/steamcmd /opt/pz /pz/app /pz/data /pz/control /pz/logs \
    && curl --fail --location --retry 3 https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz \
       | tar -xz -C /opt/steamcmd \
    && chown -R pz:pz /opt/steamcmd /home/pz
COPY ops/pzops /opt/pz/pzops
COPY server/agent.py /opt/pz/server_agent.py
ENV PYTHONPATH=/opt/pz PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/home/pz
USER 1000:1000
WORKDIR /pz/app
CMD ["python3", "/opt/pz/server_agent.py"]
