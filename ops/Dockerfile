FROM python:3.12.12-slim-bookworm
RUN groupadd -g 1000 pz && useradd -u 1000 -g pz -m pz
WORKDIR /opt/pz
COPY ops/pzops /opt/pz/pzops
COPY scripts /opt/pz/scripts
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 1000:1000
CMD ["python", "-m", "pzops.service"]
