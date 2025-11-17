#!/bin/bash

# Start-Skript für Reolink ONVIF Watcher
# Aktiviert automatisch das venv und startet das Programm

set -e

# Prüfe ob venv existiert
if [ ! -d "venv" ]; then
    echo "❌ Virtual Environment nicht gefunden!"
    echo "Bitte zuerst setup.sh ausführen: ./setup.sh"
    exit 1
fi

# Prüfe ob .env existiert
if [ ! -f ".env" ]; then
    echo "❌ .env Datei nicht gefunden!"
    echo "Bitte zuerst setup.sh ausführen und .env konfigurieren"
    exit 1
fi

# Aktiviere venv
source venv/bin/activate

# Starte Programm
echo "🚀 Starte Reolink ONVIF Watcher..."
echo ""
python main.py
