# ONVIF Watcher für Reolink Kameras

Dieses Projekt überwacht deine Reolink-Kamera und erstellt automatisch Snapshots und Video-Clips, wenn eine Person erkannt wird.

## Features

- 🔍 Echtzeit-Personenerkennung über ONVIF Events
- 📸 Automatische Snapshot-Erstellung bei neuer Erkennung
- 🎥 Video-Clip-Aufnahme während der Erkennung + konfigurierbarer Nachlauf
- 💾 Automatisches Speichern mit Zeitstempel
- 🔄 TCP Push Events für sofortige Benachrichtigungen
- 🐳 Docker-Support für einfaches Deployment

## Voraussetzungen

- Docker und Docker Compose **ODER** Python 3.11+
- Reolink-Kamera mit aktivierter Personenerkennung
- Netzwerkzugriff zur Kamera

## Installation

### Mit Docker (empfohlen)

```bash
# 1. Konfigurationsdatei erstellen
cp .env.example .env
nano .env  # Mit deinen Kamera-Daten ausfüllen

# 2. Container starten
docker-compose up -d

# 3. Logs anschauen
docker-compose logs -f
```

Vorteile:

- ✅ Keine manuelle Installation von Python oder FFmpeg
- ✅ Läuft isoliert vom Rest des Systems
- ✅ Automatischer Neustart bei Problemen
- ✅ Einfaches Update mit `docker-compose up -d --build`

### Manuelle Installation (ohne Docker)

1. Virtual Environment erstellen:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Abhängigkeiten installieren:

   ```bash
   pip install -r requirements.txt
   ```

3. FFmpeg installieren (für Video-Aufnahme):

   ```bash
   sudo apt install ffmpeg
   ```

4. Konfigurationsdatei erstellen:

   ```bash
   cp .env.example .env
   nano .env  # Mit deinen Kamera-Daten ausfüllen
   ```

5. Programm starten:
   ```bash
   python main.py
   ```

## Konfiguration

Bearbeite die `.env` Datei:

```env
CAMERA_HOST=192.168.1.100        # IP-Adresse deiner Kamera
CAMERA_USERNAME=admin             # Benutzername
CAMERA_PASSWORD=deinpasswort     # Passwort
CAMERA_PORT=80                   # HTTP Port (Standard: 80)
CAMERA_CHANNEL=0                 # Kanal (0 für Einzelkamera)
POST_DETECTION_DURATION=15       # Sekunden nach Erkennung aufnehmen
```

Für Docker werden die Snapshot- und Clip-Verzeichnisse automatisch in `./recordings` gespeichert.

## Verwendung

### Mit Docker

```bash
# Container starten
docker-compose up -d

# Logs live verfolgen
docker-compose logs -f

# Container stoppen
docker-compose down

# Container neu starten (z.B. nach Code-Änderungen)
docker-compose up -d --build
```

### Ohne Docker

```bash
# Virtual Environment aktivieren
source venv/bin/activate

# Programm starten
python main.py
```

Der Watcher läuft kontinuierlich und:

- Verbindet sich mit der Kamera
- Abonniert Personenerkennungs-Events
- Erstellt automatisch Snapshots bei **neuer** Erkennung (nicht bei Verlängerung)
- Nimmt Video-Clips auf während die Person sichtbar ist + konfigurierbarer Nachlauf
- Speichert alle Dateien mit Zeitstempel

## Dateistruktur

```
recordings/
├── snapshots/
│   └── person_detection_20231117_143052.jpg
└── clips/
    └── person_detection_20231117_143052.mp4
```

## Docker-Verwaltung

```bash
# Status prüfen
docker-compose ps

# Ressourcen-Nutzung anzeigen
docker stats reolink-watcher

# In Container einloggen (Debugging)
docker-compose exec onif-watcher /bin/bash

# Aufnahmen anzeigen
ls -lh recordings/snapshots/
ls -lh recordings/clips/
```

## Fehlerbehebung

### Verbindungsprobleme

- Prüfe IP-Adresse und Port
- Stelle sicher, dass die Kamera im Netzwerk erreichbar ist
- Überprüfe Benutzername und Passwort

### Keine Events empfangen

- Stelle sicher, dass Personenerkennung in der Kamera aktiviert ist
- Prüfe, ob ONVIF in der Kamera aktiviert ist
- Überprüfe die Kamera-Firmware (aktuell halten)

### Aufnahme-Probleme

- **Docker:** Prüfe ob Volume-Mount korrekt ist (`./recordings` muss existieren)
- Stelle sicher, dass die Speicherverzeichnisse beschreibbar sind
- Prüfe verfügbaren Festplattenspeicher
- FFmpeg-Logs prüfen: `docker-compose logs -f`

## Verhalten

- **Snapshots:** Werden nur bei **neuen** Erkennungen erstellt, nicht wenn eine laufende Aufnahme verlängert wird
- **Video-Clips:** Werden als .mp4 Dateien gespeichert (Stream-Copy, kein Re-Encoding)
- **Post-Detection-Timer:** Startet wenn keine Person mehr erkannt wird
- **Verlängerung:** Mehrere Erkennungen während einer Aufnahme verlängern die Clip-Dauer automatisch

## Lizenz

MIT License
