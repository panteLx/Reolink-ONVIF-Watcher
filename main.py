"""
Reolink ONVIF Event Watcher
Überwacht Reolink-Kameras auf Personenerkennung und erstellt automatisch Snapshots und Video-Clips.
"""

import asyncio
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from reolink_aio.api import Host
from video_recorder import VideoRecorder

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_LOGGER = logging.getLogger(__name__)


class ReolinkWatcher:
    """Überwacht Reolink-Kamera auf Personenerkennung."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 80,
        channel: int = 0,
        snapshot_dir: str = "./recordings/snapshots",
        clip_dir: str = "./recordings/clips",
        post_detection_duration: int = 15
    ):
        """
        Initialisiert den Reolink Watcher.

        Args:
            host: IP-Adresse der Kamera
            username: Benutzername
            password: Passwort
            port: HTTP Port der Kamera
            channel: Kamera-Kanal (0 für Einzelkamera)
            snapshot_dir: Verzeichnis für Snapshots
            clip_dir: Verzeichnis für Video-Clips
            post_detection_duration: Sekunden nach Erkennung aufnehmen
        """
        self.host_obj = Host(host=host, username=username,
                             password=password, port=port)
        self.channel = channel
        self.snapshot_dir = Path(snapshot_dir)
        self.clip_dir = Path(clip_dir)
        self.post_detection_duration = post_detection_duration

        # Verzeichnisse erstellen
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.clip_dir.mkdir(parents=True, exist_ok=True)

        # Video-Recorder
        self.video_recorder: Optional[VideoRecorder] = None

        # Status
        self._person_detected = False
        self._last_detection_time: Optional[datetime] = None

    async def initialize(self) -> bool:
        """
        Initialisiert die Verbindung zur Kamera.

        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            _LOGGER.info("Verbinde mit Kamera %s...", self.host_obj.host)

            # Kamera-Daten abrufen
            await self.host_obj.get_host_data()

            _LOGGER.info("Verbunden mit: %s", self.host_obj.nvr_name)
            _LOGGER.info("Modell: %s", self.host_obj.model)
            _LOGGER.info("Firmware: %s", self.host_obj.sw_version)
            _LOGGER.info("Kanäle: %s", self.host_obj.channels)

            # Prüfe ob Personenerkennung unterstützt wird
            if not self.host_obj.ai_supported(self.channel, "person"):
                _LOGGER.error(
                    "Personenerkennung wird auf Kanal %s nicht unterstützt!", self.channel)
                return False

            _LOGGER.info("Personenerkennung wird unterstützt ✓")

            # Prüfe ONVIF Unterstützung
            if not self.host_obj.onvif_enabled:
                _LOGGER.warning(
                    "ONVIF ist nicht aktiviert, versuche TCP Push Events...")

            # Video-Recorder initialisieren
            self.video_recorder = VideoRecorder(
                host_obj=self.host_obj,
                channel=self.channel,
                output_dir=self.clip_dir,
                post_detection_duration=self.post_detection_duration
            )

            return True

        except Exception as e:
            _LOGGER.error("Fehler bei der Initialisierung: %s",
                          e, exc_info=True)
            return False

    async def take_snapshot(self) -> Optional[Path]:
        """
        Erstellt einen Snapshot von der Kamera.

        Returns:
            Pfad zum gespeicherten Snapshot oder None bei Fehler
        """
        try:
            _LOGGER.info("Erstelle Snapshot...")

            # Snapshot abrufen
            snapshot_data = await self.host_obj.get_snapshot(self.channel)

            if not snapshot_data:
                _LOGGER.error("Konnte keinen Snapshot abrufen")
                return None

            # Dateiname mit Zeitstempel
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"person_detection_{timestamp}.jpg"
            filepath = self.snapshot_dir / filename

            # Snapshot speichern
            with open(filepath, 'wb') as f:
                f.write(snapshot_data)

            _LOGGER.info("Snapshot gespeichert: %s (%.2f KB)",
                         filepath, len(snapshot_data) / 1024)
            return filepath

        except Exception as e:
            _LOGGER.error(
                "Fehler beim Erstellen des Snapshots: %s", e, exc_info=True)
            return None

    def on_person_detection_changed(self) -> None:
        """
        Callback für Personenerkennungs-Events.
        Wird aufgerufen wenn sich der Erkennungsstatus ändert.
        """
        # Status von der Kamera abrufen
        person_detected = self.host_obj.ai_detected(self.channel, "person")

        if person_detected != self._person_detected:
            self._person_detected = person_detected
            self._last_detection_time = datetime.now()

            if person_detected:
                _LOGGER.info("🚶 Person erkannt!")

                # Nur Snapshot erstellen wenn noch keine Aufnahme läuft (neue Erkennung)
                if self.video_recorder and not self.video_recorder.is_recording:
                    asyncio.create_task(self.take_snapshot())

                # Video-Aufnahme starten
                if self.video_recorder:
                    asyncio.create_task(self.video_recorder.start_recording())
            else:
                _LOGGER.info("Person nicht mehr sichtbar")

                # Video-Aufnahme mit Post-Detection-Timer beenden
                if self.video_recorder:
                    asyncio.create_task(
                        self.video_recorder.stop_recording_delayed())

    async def start_monitoring(self) -> None:
        """
        Startet die Überwachung der Kamera.
        Verwendet TCP Push Events für Echtzeit-Benachrichtigungen.
        """
        try:
            _LOGGER.info("Starte Event-Monitoring...")

            # Callback registrieren
            self.host_obj.baichuan.register_callback(
                "person_watcher", self.on_person_detection_changed)

            # TCP Events abonnieren
            await self.host_obj.baichuan.subscribe_events()

            _LOGGER.info(
                "✓ Event-Monitoring aktiv - warte auf Personenerkennung...")

            # Endlos-Schleife - Events werden über Callback empfangen
            while True:
                await asyncio.sleep(60)

                # Periodischer Status-Check
                if self._last_detection_time:
                    elapsed = (datetime.now() -
                               self._last_detection_time).total_seconds()
                    _LOGGER.debug(
                        "Letzte Erkennung vor %.0f Sekunden", elapsed)

        except asyncio.CancelledError:
            _LOGGER.info("Monitoring wird beendet...")
            raise
        except Exception as e:
            _LOGGER.error("Fehler beim Event-Monitoring: %s", e, exc_info=True)
            raise

    async def cleanup(self) -> None:
        """
        Räumt Ressourcen auf und trennt die Verbindung.
        """
        try:
            _LOGGER.info("Trenne Verbindung...")

            # Video-Recorder stoppen
            if self.video_recorder:
                await self.video_recorder.stop_recording()

            # Events deabonnieren
            try:
                await self.host_obj.baichuan.unsubscribe_events()
            except:
                pass

            # Logout
            await self.host_obj.logout()

            _LOGGER.info("Verbindung getrennt")

        except Exception as e:
            _LOGGER.error("Fehler beim Cleanup: %s", e, exc_info=True)


async def main():
    """Hauptfunktion."""
    # Umgebungsvariablen laden
    load_dotenv()

    # Konfiguration aus .env laden
    camera_host = os.getenv('CAMERA_HOST')
    camera_username = os.getenv('CAMERA_USERNAME')
    camera_password = os.getenv('CAMERA_PASSWORD')
    camera_port = int(os.getenv('CAMERA_PORT', '80'))
    camera_channel = int(os.getenv('CAMERA_CHANNEL', '0'))
    snapshot_dir = os.getenv('SNAPSHOT_DIR', './recordings/snapshots')
    clip_dir = os.getenv('CLIP_DIR', './recordings/clips')
    post_detection_duration = int(os.getenv('POST_DETECTION_DURATION', '15'))

    # Validierung
    if not all([camera_host, camera_username, camera_password]):
        _LOGGER.error(
            "Fehlende Konfiguration! Bitte .env Datei erstellen und ausfüllen.")
        _LOGGER.error("Siehe .env.example für ein Beispiel.")
        return

    # Watcher erstellen
    watcher = ReolinkWatcher(
        host=camera_host,
        username=camera_username,
        password=camera_password,
        port=camera_port,
        channel=camera_channel,
        snapshot_dir=snapshot_dir,
        clip_dir=clip_dir,
        post_detection_duration=post_detection_duration
    )

    try:
        # Initialisieren
        if not await watcher.initialize():
            _LOGGER.error("Initialisierung fehlgeschlagen")
            return

        # Monitoring starten
        await watcher.start_monitoring()

    except KeyboardInterrupt:
        _LOGGER.info("Programm durch Benutzer beendet")
    except Exception as e:
        _LOGGER.error("Unerwarteter Fehler: %s", e, exc_info=True)
    finally:
        # Aufräumen
        await watcher.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
