# Docker Setup für Reolink ONIF Watcher

## Schnellstart

### 1. Konfiguration erstellen

Kopiere `.env.example` nach `.env` und passe die Werte an:

```bash
cp .env.example .env
nano .env
```

Wichtige Einstellungen in `.env`:

```env
CAMERA_HOST=192.168.1.100          # IP deiner Reolink Kamera
CAMERA_USERNAME=admin               # Kamera Benutzername
CAMERA_PASSWORD=deinpasswort        # Kamera Passwort
CAMERA_PORT=80                      # HTTP Port (Standard: 80)
CAMERA_CHANNEL=0                    # Kanal (0 für Einzelkamera)
POST_DETECTION_DURATION=15          # Sekunden nach Erkennung aufnehmen
```

### 2. Container starten

```bash
# Container bauen und im Hintergrund starten
docker-compose up -d

# Logs anschauen
docker-compose logs -f

# Container stoppen
docker-compose down
```

## Befehle

### Container-Verwaltung

```bash
# Container neu bauen (nach Code-Änderungen)
docker-compose build

# Container neu starten
docker-compose restart

# Container stoppen
docker-compose stop

# Container stoppen und löschen
docker-compose down

# Container und Images löschen
docker-compose down --rmi all
```

### Logs und Debugging

```bash
# Live-Logs anzeigen
docker-compose logs -f

# Letzte 100 Zeilen
docker-compose logs --tail=100

# In Container einloggen (für Debugging)
docker-compose exec onif-watcher /bin/bash
```

### Aufnahmen verwalten

```bash
# Snapshots anzeigen
ls -lh recordings/snapshots/

# Videos anzeigen
ls -lh recordings/clips/

# Speicherplatz prüfen
du -sh recordings/
```

## Volume-Mounts

Die Aufnahmen werden in `./recordings` auf dem Host gespeichert:

- `./recordings/snapshots/` - Snapshots bei Personenerkennung
- `./recordings/clips/` - Video-Aufnahmen

## Netzwerk-Modus

Der Container verwendet `network_mode: host` für optimale RTSP-Performance.

**Alternative:** Bridge-Modus (wenn host nicht funktioniert):

```yaml
# In docker-compose.yml ändern:
network_mode: bridge
ports:
  - "554:554" # RTSP
```

## Ressourcen-Limits

Standardmäßig keine Limits. Bei Bedarf in `docker-compose.yml` aktivieren:

```yaml
deploy:
  resources:
    limits:
      cpus: "1.0"
      memory: 512M
```

## Automatischer Start beim Booten

Der Container startet automatisch durch `restart: unless-stopped`.

Zum Deaktivieren:

```bash
docker update --restart=no reolink-watcher
```

## Troubleshooting

### FFmpeg-Fehler

```bash
# Prüfe ob FFmpeg installiert ist
docker-compose exec onif-watcher ffmpeg -version
```

### Verbindungsprobleme

```bash
# Teste Kamera-Erreichbarkeit
docker-compose exec onif-watcher ping -c 3 <CAMERA_IP>
```

### Logs prüfen

```bash
# Detaillierte Logs
docker-compose logs -f --tail=200
```

### Container neu bauen (clean build)

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Update

```bash
# Code aktualisieren (z.B. via git pull)
git pull

# Container neu bauen und starten
docker-compose up -d --build
```

## Backup

### Aufnahmen sichern

```bash
tar -czf recordings-backup-$(date +%Y%m%d).tar.gz recordings/
```

### Konfiguration sichern

```bash
cp .env .env.backup
```
