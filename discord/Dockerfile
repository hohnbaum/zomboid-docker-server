FROM python:3.12.12-slim-bookworm
RUN groupadd -g 1000 pz && useradd -u 1000 -g pz -m pz
WORKDIR /opt/pz
COPY discord/requirements.lock /opt/pz/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY ops/pzops /opt/pz/pzops
COPY discord/bot.py /opt/pz/bot.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 1000:1000
CMD ["python", "bot.py"]
