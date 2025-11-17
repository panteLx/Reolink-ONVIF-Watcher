# ONVIF Watcher für Reolink Kameras

Dieses Projekt überwacht deine Reolink-Kamera und erstellt automatisch Snapshots und Video-Clips, wenn eine Person erkannt wird.

## Features

- 🔍 Echtzeit-Personenerkennung über ONVIF Events
- 📸 Automatische Snapshot-Erstellung bei Erkennung
- 🎥 Video-Clip-Aufnahme während der Erkennung + 15 Sekunden
- 💾 Automatisches Speichern mit Zeitstempel
- 🔄 TCP Push Events für sofortige Benachrichtigungen

## Voraussetzungen

- Python 3.11 oder höher
- Reolink-Kamera mit aktivierter Personenerkennung
- Netzwerkzugriff zur Kamera

## Installation

### Automatische Installation (empfohlen)

```bash
# Setup-Skript ausführen (erstellt venv, installiert Abhängigkeiten)
./setup.sh

# .env Datei mit deinen Kamera-Daten bearbeiten
nano .env

# Programm starten
./run.sh
```

Das Setup-Skript:

- ✅ Prüft Python Version (>= 3.11)
- ✅ Erstellt automatisch ein Python Virtual Environment
- ✅ Installiert alle Abhängigkeiten
- ✅ Prüft und installiert FFmpeg (optional)
- ✅ Erstellt Konfigurationsdatei und Verzeichnisse

### Manuelle Installation

1. Repository klonen oder herunterladen

2. Virtual Environment erstellen:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Abhängigkeiten installieren:

   ```bash
   pip install -r requirements.txt
   ```

4. FFmpeg installieren (für Video-Aufnahme):

   ```bash
   sudo apt install ffmpeg
   ```

5. Konfigurationsdatei erstellen:
   ```bash
   cp .env.example .env
   nano .env  # Mit deinen Kamera-Daten ausfüllen
   ```

## Konfiguration

Bearbeite die `.env` Datei:

```env
CAMERA_HOST=192.168.1.100        # IP-Adresse deiner Kamera
CAMERA_USERNAME=admin             # Benutzername
CAMERA_PASSWORD=deinpasswort     # Passwort
CAMERA_PORT=80                   # HTTP Port (Standard: 80)
CAMERA_CHANNEL=0                 # Kanal (0 für Einzelkamera)
SNAPSHOT_DIR=./recordings/snapshots  # Snapshot-Speicherort
CLIP_DIR=./recordings/clips         # Clip-Speicherort
POST_DETECTION_DURATION=15       # Sekunden nach Erkennung aufnehmen
```

## Verwendung

### Mit Start-Skript (empfohlen)

```bash
./run.sh
```

Das Skript aktiviert automatisch das Virtual Environment und startet das Programm.

### Manuell

```bash
# Virtual Environment aktivieren
source venv/bin/activate

# Programm starten
python main.py
```

Der Watcher läuft kontinuierlich und:

- Verbindet sich mit der Kamera
- Abonniert Personenerkennungs-Events
- Erstellt automatisch Snapshots bei Erkennung
- Nimmt Video-Clips auf während die Person sichtbar ist + 15 Sekunden
- Speichert alle Dateien mit Zeitstempel

## Dateistruktur

```
recordings/
├── snapshots/
│   └── person_detection_20231117_143052.jpg
└── clips/
    └── person_detection_20231117_143052.mp4
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

- Stelle sicher, dass die Speicherverzeichnisse beschreibbar sind
- Prüfe verfügbaren Festplattenspeicher

## Hinweise

- Die Video-Clips werden als .mp4 Dateien gespeichert
- Snapshots sind im JPEG-Format
- Der Post-Detection-Timer startet, wenn keine Person mehr erkannt wird
- Mehrere Erkennungen während einer Aufnahme verlängern die Clip-Dauer

## Lizenz

MIT License
