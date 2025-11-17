# ONVIF Watcher für Reolink Kameras

Dieses Projekt überwacht deine Reolink-Kameras und erstellt automatisch Snapshots und Video-Clips, wenn eine Person erkannt wird. **Unterstützt mehrere Kameras gleichzeitig!**

## Features

- 🔍 Echtzeit-Personenerkennung über ONVIF Events
- � **Multi-Kamera-Support** - überwache mehrere Kameras parallel
- �📸 Automatische Snapshot-Erstellung bei neuer Erkennung
- 🎥 Video-Clip-Aufnahme während der Erkennung + konfigurierbarer Nachlauf
- 💾 Automatisches Speichern mit Zeitstempel
- � Separate Verzeichnisse für jede Kamera
- �🔄 TCP Push Events für sofortige Benachrichtigungen
- 🐳 Docker-Support für einfaches Deployment

## Voraussetzungen

- Docker und Docker Compose **ODER** Python 3.11+
- Reolink-Kamera(s) mit aktivierter Personenerkennung
- Netzwerkzugriff zu den Kameras

## Installation

### Mit Docker (empfohlen)

```bash
# 1. Konfigurationsdatei erstellen
cp cameras.json.example cameras.json
nano cameras.json  # Mit deinen Kamera-Daten ausfüllen

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
   cp cameras.json.example cameras.json
   nano cameras.json  # Mit deinen Kamera-Daten ausfüllen
   ```

5. Programm starten:
   ```bash
   python main.py
   ```

## Konfiguration

Bearbeite die `cameras.json` Datei:

```json
{
  "cameras": [
    {
      "name": "garten",
      "host": "192.168.1.100",
      "username": "admin",
      "password": "deinpasswort",
      "port": 80,
      "channel": 0,
      "enabled": true
    },
    {
      "name": "haustuer",
      "host": "192.168.1.101",
      "username": "admin",
      "password": "deinpasswort",
      "port": 80,
      "channel": 0,
      "enabled": true
    }
  ],
  "settings": {
    "post_detection_duration": 15,
    "recordings_base_dir": "./recordings"
  }
}
```

**Wichtig:**

- Jede Kamera braucht einen eindeutigen `name` (wird für Verzeichnisse verwendet)
- Mit `enabled: false` kannst du Kameras temporär deaktivieren
- `post_detection_duration`: Sekunden nach Erkennung weiter aufnehmen
- Füge weitere Kameras einfach zum `cameras`-Array hinzu

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

- Verbindet sich mit allen konfigurierten Kameras parallel
- Abonniert Personenerkennungs-Events für jede Kamera
- Erstellt automatisch Snapshots bei **neuer** Erkennung (nicht bei Verlängerung)
- Nimmt Video-Clips auf während die Person sichtbar ist + konfigurierbarer Nachlauf
- Speichert alle Dateien in kamera-spezifischen Verzeichnissen

## Dateistruktur

```
recordings/
├── garten/
│   ├── snapshots/
│   │   └── person_detection_20231117_143052.jpg
│   └── clips/
│       └── person_detection_20231117_143052.mp4
├── haustuer/
│   ├── snapshots/
│   │   └── person_detection_20231117_144235.jpg
│   └── clips/
│       └── person_detection_20231117_144235.mp4
└── garage/
    ├── snapshots/
    └── clips/
```

Jede Kamera erhält basierend auf dem `name` in der Konfiguration einen eigenen Unterordner.

## Docker-Verwaltung

```bash
# Status prüfen
docker-compose ps

# Ressourcen-Nutzung anzeigen
docker stats reolink-watcher

# In Container einloggen (Debugging)
docker-compose exec onif-watcher /bin/bash

# Aufnahmen anzeigen (alle Kameras)
ls -lh recordings/*/snapshots/
ls -lh recordings/*/clips/

# Aufnahmen einer spezifischen Kamera
ls -lh recordings/garten/snapshots/
ls -lh recordings/garten/clips/
```

## Multi-Kamera-Tipps

- **Ressourcen:** Jede Kamera benötigt ca. 200-300MB RAM. Passe die Docker-Limits entsprechend an.
- **Netzwerk:** Verwende `network_mode: host` für optimale RTSP-Performance
- **Logging:** Mit `[kamera_name]` Präfix in den Logs kannst du Events pro Kamera verfolgen
- **Speicher:** Stelle sicher, dass genug Festplattenspeicher für alle Kameras vorhanden ist

## Fehlerbehebung

### Verbindungsprobleme

- Prüfe IP-Adressen und Ports in `cameras.json`
- Stelle sicher, dass alle Kameras im Netzwerk erreichbar sind
- Überprüfe Benutzernamen und Passwörter
- Bei mehreren Kameras: Logs zeigen welche Kamera Probleme hat

### Keine Events empfangen

- Stelle sicher, dass Personenerkennung in **jeder** Kamera aktiviert ist
- Prüfe, ob ONVIF in den Kameras aktiviert ist
- Überprüfe die Kamera-Firmware (aktuell halten)
- Deaktiviere problematische Kameras temporär mit `enabled: false`

### Aufnahme-Probleme

- **Docker:** Prüfe ob Volume-Mount korrekt ist (`./recordings` muss existieren)
- **Berechtigungen:** Stelle sicher, dass die Verzeichnisse beschreibbar sind
- Prüfe verfügbaren Festplattenspeicher (besonders bei vielen Kameras!)
- FFmpeg-Logs prüfen: `docker-compose logs -f | grep <kamera_name>`
- Die Logs zeigen den Kamera-Namen, um spezifische Probleme zu identifizieren

## Verhalten

- **Snapshots:** Werden nur bei **neuen** Erkennungen erstellt, nicht wenn eine laufende Aufnahme verlängert wird
- **Video-Clips:** Werden als .mp4 Dateien gespeichert (Stream-Copy, kein Re-Encoding)
- **Post-Detection-Timer:** Startet wenn keine Person mehr erkannt wird
- **Verlängerung:** Mehrere Erkennungen während einer Aufnahme verlängern die Clip-Dauer automatisch

## Lizenz

MIT License
