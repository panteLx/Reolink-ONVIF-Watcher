# Verwende Python 3.11 slim als Basis
FROM python:3.11-slim

# Metadaten
LABEL maintainer="onif-watcher"
LABEL description="Reolink ONVIF Event Watcher - Automatische Personenerkennung und Video-Aufnahme"

# Umgebungsvariablen
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Arbeitsverzeichnis erstellen
WORKDIR /app

# System-Abhängigkeiten installieren (FFmpeg für Video-Aufnahme)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python-Abhängigkeiten kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Anwendungscode kopieren
COPY main.py .
COPY video_recorder.py .

# Verzeichnisse für Aufnahmen erstellen
RUN mkdir -p /app/recordings/snapshots /app/recordings/clips

# Volume für persistente Speicherung der Aufnahmen
VOLUME ["/app/recordings"]

# Standard-Umgebungsvariablen (können über docker-compose überschrieben werden)
ENV SNAPSHOT_DIR=/app/recordings/snapshots \
    CLIP_DIR=/app/recordings/clips \
    POST_DETECTION_DURATION=15 \
    CAMERA_CHANNEL=0 \
    CAMERA_PORT=80

# Anwendung starten
CMD ["python", "-u", "main.py"]
