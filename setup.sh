#!/bin/bash

# Setup-Skript für Reolink ONVIF Watcher
# Erstellt automatisch ein Python venv und installiert alle Abhängigkeiten

set -e  # Beende bei Fehler

echo "🔧 Reolink ONVIF Watcher - Setup"
echo "================================"
echo ""

# Prüfe Python Version
echo "Prüfe Python Installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 ist nicht installiert!"
    echo "Installiere mit: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Python $PYTHON_VERSION gefunden"

# Prüfe ob Python >= 3.11
REQUIRED_VERSION="3.11"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "⚠️  Warnung: Python >= 3.11 wird empfohlen (gefunden: $PYTHON_VERSION)"
    read -p "Trotzdem fortfahren? (j/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Jj]$ ]]; then
        exit 1
    fi
fi

# Prüfe FFmpeg
echo ""
echo "Prüfe FFmpeg Installation..."
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  FFmpeg ist nicht installiert (benötigt für Video-Aufnahme)"
    read -p "FFmpeg jetzt installieren? (j/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Jj]$ ]]; then
        echo "Installiere FFmpeg..."
        sudo dnf update
        sudo dnf install -y ffmpeg
        echo "✓ FFmpeg installiert"
    else
        echo "⚠️  Ohne FFmpeg können keine Videos aufgenommen werden!"
    fi
else
    FFMPEG_VERSION=$(ffmpeg -version | head -n1 | cut -d' ' -f3)
    echo "✓ FFmpeg $FFMPEG_VERSION gefunden"
fi

# Erstelle Virtual Environment
echo ""
echo "Erstelle Python Virtual Environment..."
if [ -d "venv" ]; then
    echo "⚠️  venv Verzeichnis existiert bereits"
    read -p "Neu erstellen? (löscht bestehendes venv) (j/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Jj]$ ]]; then
        rm -rf venv
        python3 -m venv venv
        echo "✓ Virtual Environment neu erstellt"
    else
        echo "✓ Verwende bestehendes Virtual Environment"
    fi
else
    python3 -m venv venv
    echo "✓ Virtual Environment erstellt"
fi

# Aktiviere Virtual Environment
echo ""
echo "Aktiviere Virtual Environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Update pip..."
pip install --upgrade pip wheel setuptools

# Installiere Requirements
echo ""
echo "Installiere Python-Abhängigkeiten..."
pip install -r requirements.txt

echo ""
echo "✓ Alle Abhängigkeiten installiert"

# Erstelle .env falls nicht vorhanden
echo ""
if [ ! -f ".env" ]; then
    echo "Erstelle Konfigurationsdatei..."
    cp .env.example .env
    echo "✓ .env Datei erstellt"
    echo ""
    echo "⚠️  WICHTIG: Bitte .env Datei mit deinen Kamera-Daten ausfüllen:"
    echo "   - CAMERA_HOST (IP-Adresse)"
    echo "   - CAMERA_USERNAME"
    echo "   - CAMERA_PASSWORD"
else
    echo "✓ .env Datei existiert bereits"
fi

# Erstelle Aufnahme-Verzeichnisse
echo ""
echo "Erstelle Aufnahme-Verzeichnisse..."
mkdir -p recordings/snapshots
mkdir -p recordings/clips
echo "✓ Verzeichnisse erstellt"

echo ""
echo "================================"
echo "✅ Setup erfolgreich abgeschlossen!"
echo ""
echo "Nächste Schritte:"
echo "1. Bearbeite .env Datei mit deinen Kamera-Daten"
echo "2. Aktiviere Virtual Environment: source venv/bin/activate"
echo "3. Starte das Programm: python main.py"
echo ""
echo "Oder nutze das Start-Skript: ./run.sh"
echo ""
