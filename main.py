"""
Reolink ONVIF Event Watcher
Überwacht Reolink-Kameras auf Personenerkennung und erstellt automatisch Snapshots und Video-Clips.
Unterstützt mehrere Kameras gleichzeitig.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from reolink_aio.api import Host
from reolink_aio.exceptions import LoginPrivacyModeError
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
        camera_name: str,
        host: str,
        username: str,
        password: str,
        port: int = 80,
        channel: int = 0,
        recordings_base_dir: str = "./recordings",
        post_detection_duration: int = 15,
        stream_format: str = "h264"
    ):
        """
        Initialisiert den Reolink Watcher.

        Args:
            camera_name: Eindeutiger Name der Kamera (für Verzeichnisstruktur)
            host: IP-Adresse der Kamera
            username: Benutzername
            password: Passwort
            port: HTTP Port der Kamera
            channel: Kamera-Kanal (0 für Einzelkamera)
            recordings_base_dir: Basis-Verzeichnis für alle Aufnahmen
            post_detection_duration: Sekunden nach Erkennung aufnehmen
            stream_format: Video-Format (h264 oder h265)
        """
        self.camera_name = camera_name
        self.host_obj = Host(host=host, username=username,
                             password=password, port=port)
        self.channel = channel
        self.stream_format = stream_format

        # Kamera-spezifische Verzeichnisse erstellen
        base_path = Path(recordings_base_dir) / camera_name
        self.snapshot_dir = base_path / "snapshots"
        self.clip_dir = base_path / "clips"
        self.post_detection_duration = post_detection_duration

        # Verzeichnisse erstellen
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.clip_dir.mkdir(parents=True, exist_ok=True)

        # Video-Recorder
        self.video_recorder: Optional[VideoRecorder] = None

        # Status
        self._person_detected = False
        self._last_detection_time: Optional[datetime] = None
        self._is_privacy_mode = False
        self._is_connected = False
        self._privacy_check_interval = 30  # Sekunden zwischen Privacy Mode Checks

    async def initialize(self) -> bool:
        """
        Initialisiert die Verbindung zur Kamera.

        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            _LOGGER.info("[%s] Verbinde mit Kamera %s...",
                         self.camera_name, self.host_obj.host)

            # Kamera-Daten abrufen
            await self.host_obj.get_host_data()

            _LOGGER.info("[%s] Verbunden mit: %s",
                         self.camera_name, self.host_obj.nvr_name)
            _LOGGER.info("[%s] Modell: %s", self.camera_name,
                         self.host_obj.model)
            _LOGGER.info("[%s] Firmware: %s", self.camera_name,
                         self.host_obj.sw_version)
            _LOGGER.info("[%s] Kanäle: %s", self.camera_name,
                         self.host_obj.channels)

            # Prüfe ob Personenerkennung unterstützt wird
            if not self.host_obj.ai_supported(self.channel, "person"):
                _LOGGER.error(
                    "[%s] Personenerkennung wird auf Kanal %s nicht unterstützt!",
                    self.camera_name, self.channel)
                return False

            _LOGGER.info(
                "[%s] Personenerkennung wird unterstützt ✓", self.camera_name)

            # Prüfe ONVIF Unterstützung
            if not self.host_obj.onvif_enabled:
                _LOGGER.warning(
                    "[%s] ONVIF ist nicht aktiviert, versuche TCP Push Events...", self.camera_name)

            # Video-Recorder initialisieren
            self.video_recorder = VideoRecorder(
                host_obj=self.host_obj,
                channel=self.channel,
                output_dir=self.clip_dir,
                post_detection_duration=self.post_detection_duration,
                stream_format=self.stream_format
            )

            self._is_connected = True
            self._is_privacy_mode = False
            return True

        except LoginPrivacyModeError as e:
            _LOGGER.warning("[%s] Privacy Mode ist aktiviert: %s",
                            self.camera_name, e)
            self._is_privacy_mode = True
            self._is_connected = False
            return False
        except Exception as e:
            _LOGGER.error("[%s] Fehler bei der Initialisierung: %s",
                          self.camera_name, e, exc_info=True)
            self._is_connected = False
            return False

    async def take_snapshot(self) -> Optional[Path]:
        """
        Erstellt einen Snapshot von der Kamera.
        Versucht zuerst die API-Methode, bei Fehler (z.B. H.265) wird FFmpeg verwendet.

        Returns:
            Pfad zum gespeicherten Snapshot oder None bei Fehler
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"person_detection_{timestamp}.jpg"
        filepath = self.snapshot_dir / filename

        try:
            _LOGGER.info("[%s] Erstelle Snapshot...", self.camera_name)

            # Versuche zuerst die API-Methode (funktioniert bei H.264)
            snapshot_data = await self.host_obj.get_snapshot(self.channel)

            if snapshot_data:
                # Snapshot speichern
                with open(filepath, 'wb') as f:
                    f.write(snapshot_data)

                _LOGGER.info("[%s] Snapshot gespeichert: %s (%.2f KB)",
                             self.camera_name, filepath, len(snapshot_data) / 1024)
                return filepath

        except Exception as e:
            # API-Methode fehlgeschlagen (z.B. bei H.265), versuche FFmpeg
            _LOGGER.info(
                "[%s] API-Snapshot fehlgeschlagen, verwende FFmpeg-Methode...",
                self.camera_name)

        # Fallback: Snapshot mit FFmpeg aus RTSP-Stream erstellen
        try:
            return await self._take_snapshot_ffmpeg(filepath)
        except Exception as e:
            _LOGGER.error(
                "[%s] Fehler beim Erstellen des Snapshots: %s",
                self.camera_name, e, exc_info=True)
            return None

    async def _take_snapshot_ffmpeg(self, filepath: Path) -> Optional[Path]:
        """
        Erstellt einen Snapshot mit FFmpeg aus dem RTSP-Stream.
        Diese Methode funktioniert auch bei H.265-Kameras.

        Args:
            filepath: Pfad zum Speichern des Snapshots

        Returns:
            Pfad zum gespeicherten Snapshot oder None bei Fehler
        """
        if not self.video_recorder:
            _LOGGER.error(
                "[%s] Video-Recorder nicht initialisiert", self.camera_name)
            return None

        # RTSP-URL vom VideoRecorder holen
        rtsp_url = self.video_recorder._get_rtsp_url()

        # FFmpeg-Befehl: Einen Frame extrahieren
        cmd = [
            'ffmpeg',
            '-y',  # Überschreiben ohne Nachfrage
            '-rtsp_transport', 'tcp',  # TCP Transport für bessere Stabilität
            '-i', rtsp_url,  # Input RTSP-Stream
            '-frames:v', '1',  # Nur einen Frame extrahieren
            '-q:v', '2',  # Hohe Qualität (1-31, 2 ist sehr gut)
            '-f', 'image2',  # Output-Format
            str(filepath)
        ]

        try:
            # FFmpeg asynchron ausführen
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Warten mit Timeout (max 10 Sekunden)
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=10.0
            )

            if process.returncode == 0 and filepath.exists():
                file_size = filepath.stat().st_size
                _LOGGER.info(
                    "[%s] FFmpeg-Snapshot gespeichert: %s (%.2f KB)",
                    self.camera_name, filepath, file_size / 1024
                )
                return filepath
            else:
                _LOGGER.error(
                    "[%s] FFmpeg-Snapshot fehlgeschlagen: %s",
                    self.camera_name, stderr.decode() if stderr else "Unbekannter Fehler"
                )
                return None

        except asyncio.TimeoutError:
            _LOGGER.error("[%s] FFmpeg-Snapshot Timeout", self.camera_name)
            if process:
                process.kill()
            return None
        except Exception as e:
            _LOGGER.error(
                "[%s] FFmpeg-Fehler: %s",
                self.camera_name, e, exc_info=True
            )
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
                _LOGGER.info("[%s] 🚶 Person erkannt!", self.camera_name)

                # Nur Snapshot erstellen wenn noch keine Aufnahme läuft (neue Erkennung)
                if self.video_recorder and not self.video_recorder.is_recording:
                    asyncio.create_task(self.take_snapshot())

                # Video-Aufnahme starten
                if self.video_recorder:
                    asyncio.create_task(self.video_recorder.start_recording())
            else:
                _LOGGER.info("[%s] Person nicht mehr sichtbar",
                             self.camera_name)

                # Video-Aufnahme mit Post-Detection-Timer beenden
                if self.video_recorder:
                    asyncio.create_task(
                        self.video_recorder.stop_recording_delayed())

    async def start_monitoring(self) -> None:
        """
        Startet die Überwachung der Kamera.
        Verwendet TCP Push Events für Echtzeit-Benachrichtigungen.
        Prüft kontinuierlich auf Privacy Mode und reconnected automatisch.
        """
        try:
            _LOGGER.info("[%s] Starte Event-Monitoring...", self.camera_name)

            # Wenn Kamera nicht verbunden ist (z.B. wegen Privacy Mode), starte Reconnection Loop
            if not self._is_connected:
                await self._privacy_mode_recovery_loop()
                return

            # Callback registrieren
            self.host_obj.baichuan.register_callback(
                f"person_watcher_{self.camera_name}", self.on_person_detection_changed)

            # TCP Events abonnieren
            await self.host_obj.baichuan.subscribe_events()

            _LOGGER.info(
                "[%s] ✓ Event-Monitoring aktiv - warte auf Personenerkennung...", self.camera_name)

            # Endlos-Schleife - Events werden über Callback empfangen
            while True:
                await asyncio.sleep(self._privacy_check_interval)

                # Periodischer Privacy Mode Check
                if not await self._check_connection_status():
                    # Verbindung verloren oder Privacy Mode aktiviert
                    _LOGGER.warning(
                        "[%s] Verbindung verloren, starte Recovery...", self.camera_name)
                    await self._privacy_mode_recovery_loop()
                    break

                # Periodischer Status-Check
                if self._last_detection_time:
                    elapsed = (datetime.now() -
                               self._last_detection_time).total_seconds()
                    _LOGGER.debug(
                        "[%s] Letzte Erkennung vor %.0f Sekunden", self.camera_name, elapsed)

        except asyncio.CancelledError:
            _LOGGER.info("[%s] Monitoring wird beendet...", self.camera_name)
            raise
        except Exception as e:
            _LOGGER.error("[%s] Fehler beim Event-Monitoring: %s",
                          self.camera_name, e, exc_info=True)
            raise

    async def _check_connection_status(self) -> bool:
        """
        Prüft ob die Verbindung zur Kamera noch besteht.

        Returns:
            True wenn verbunden, False wenn Verbindung verloren oder Privacy Mode aktiv
        """
        try:
            # Versuche eine einfache Abfrage zu machen
            await self.host_obj.get_state("GetDevInfo")
            return True
        except LoginPrivacyModeError:
            _LOGGER.warning(
                "[%s] Privacy Mode wurde aktiviert", self.camera_name)
            self._is_privacy_mode = True
            self._is_connected = False
            return False
        except Exception as e:
            _LOGGER.warning("[%s] Verbindungsprüfung fehlgeschlagen: %s",
                            self.camera_name, e)
            self._is_connected = False
            return False

    async def _privacy_mode_recovery_loop(self) -> None:
        """
        Wartet darauf, dass Privacy Mode deaktiviert wird und stellt dann die Verbindung wieder her.
        """
        _LOGGER.info("[%s] 🔒 Privacy Mode Recovery aktiv - warte auf Deaktivierung...",
                     self.camera_name)

        retry_count = 0

        while True:
            try:
                await asyncio.sleep(self._privacy_check_interval)
                retry_count += 1

                _LOGGER.debug("[%s] Privacy Mode Check #%d...",
                              self.camera_name, retry_count)

                # Versuche neu zu verbinden
                # Erstelle neues Host-Objekt für sauberen Reconnect
                test_host = Host(
                    host=self.host_obj.host,
                    username=self.host_obj.username,
                    password=self.host_obj._password,
                    port=self.host_obj.port
                )

                try:
                    await test_host.get_host_data()

                    # Erfolg! Privacy Mode ist deaktiviert
                    _LOGGER.info("[%s] ✓ Privacy Mode deaktiviert - stelle Verbindung wieder her...",
                                 self.camera_name)

                    # Cleanup des alten Host-Objekts
                    try:
                        await self.host_obj.logout()
                    except:
                        pass

                    # Verwende das neue Host-Objekt
                    self.host_obj = test_host

                    # Re-initialisiere
                    if await self.initialize():
                        _LOGGER.info(
                            "[%s] ✓ Erfolgreich reconnected!", self.camera_name)
                        # Starte Monitoring neu
                        await self.start_monitoring()
                        return
                    else:
                        _LOGGER.error(
                            "[%s] Re-Initialisierung fehlgeschlagen", self.camera_name)
                        await test_host.logout()

                except LoginPrivacyModeError:
                    # Privacy Mode noch aktiv
                    await test_host.logout()
                    # Log alle 10 Versuche (alle 5 Minuten bei 30s Intervall)
                    if retry_count % 10 == 0:
                        _LOGGER.info("[%s] Privacy Mode noch aktiv (Check #%d)...",
                                     self.camera_name, retry_count)
                except Exception as e:
                    # Anderer Fehler
                    await test_host.logout()
                    if retry_count % 10 == 0:
                        _LOGGER.warning("[%s] Verbindungsversuch fehlgeschlagen: %s",
                                        self.camera_name, e)

            except asyncio.CancelledError:
                _LOGGER.info(
                    "[%s] Privacy Mode Recovery wird beendet...", self.camera_name)
                raise
            except Exception as e:
                _LOGGER.error("[%s] Fehler im Recovery Loop: %s",
                              self.camera_name, e, exc_info=True)
                # Warte trotzdem weiter
                await asyncio.sleep(self._privacy_check_interval)

    async def cleanup(self) -> None:
        """
        Räumt Ressourcen auf und trennt die Verbindung.
        """
        try:
            _LOGGER.info("[%s] Trenne Verbindung...", self.camera_name)

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

            _LOGGER.info("[%s] Verbindung getrennt", self.camera_name)

        except Exception as e:
            _LOGGER.error("[%s] Fehler beim Cleanup: %s",
                          self.camera_name, e, exc_info=True)


class MultiCameraManager:
    """Verwaltet mehrere Reolink-Kameras parallel."""

    def __init__(self, config_file: str = "cameras.json"):
        """
        Initialisiert den Multi-Kamera-Manager.

        Args:
            config_file: Pfad zur JSON-Konfigurationsdatei
        """
        self.config_file = config_file
        self.watchers: List[ReolinkWatcher] = []
        self.monitoring_tasks: List[asyncio.Task] = []

    def load_config(self) -> Dict[str, Any]:
        """
        Lädt die Konfiguration aus der JSON-Datei.

        Returns:
            Konfigurationsdaten als Dictionary
        """
        config_path = Path(self.config_file)

        if not config_path.exists():
            _LOGGER.error(
                "Konfigurationsdatei nicht gefunden: %s", self.config_file)
            _LOGGER.error(
                "Bitte cameras.json.example zu cameras.json kopieren und anpassen.")
            raise FileNotFoundError(
                f"Konfigurationsdatei {self.config_file} nicht gefunden")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            _LOGGER.info("Konfiguration geladen: %d Kamera(s) definiert", len(
                config.get('cameras', [])))
            return config

        except json.JSONDecodeError as e:
            _LOGGER.error("Fehler beim Parsen der Konfigurationsdatei: %s", e)
            raise
        except Exception as e:
            _LOGGER.error("Fehler beim Laden der Konfiguration: %s", e)
            raise

    async def initialize_cameras(self) -> bool:
        """
        Initialisiert alle Kameras aus der Konfiguration.

        Returns:
            True wenn mindestens eine Kamera erfolgreich initialisiert wurde
        """
        try:
            config = self.load_config()

            cameras = config.get('cameras', [])
            settings = config.get('settings', {})

            post_detection_duration = settings.get(
                'post_detection_duration', 15)
            recordings_base_dir = settings.get(
                'recordings_base_dir', './recordings')

            if not cameras:
                _LOGGER.error("Keine Kameras in der Konfiguration definiert!")
                return False

            # Filter nur aktivierte Kameras
            enabled_cameras = [
                cam for cam in cameras if cam.get('enabled', True)]

            if not enabled_cameras:
                _LOGGER.warning("Alle Kameras sind deaktiviert!")
                return False

            _LOGGER.info("Initialisiere %d Kamera(s)...", len(enabled_cameras))

            # Initialisiere jede Kamera
            success_count = 0
            privacy_mode_count = 0
            for camera_config in enabled_cameras:
                try:
                    name = camera_config.get('name')
                    if not name:
                        _LOGGER.warning("Kamera ohne Namen übersprungen")
                        continue

                    # Erstelle Watcher für diese Kamera
                    watcher = ReolinkWatcher(
                        camera_name=name,
                        host=camera_config.get('host'),
                        username=camera_config.get('username'),
                        password=camera_config.get('password'),
                        port=camera_config.get('port', 80),
                        channel=camera_config.get('channel', 0),
                        recordings_base_dir=recordings_base_dir,
                        post_detection_duration=post_detection_duration,
                        stream_format=camera_config.get(
                            'stream_format', 'h264')
                    )

                    # Initialisiere Verbindung
                    init_result = await watcher.initialize()

                    # Füge Watcher immer hinzu, auch wenn Privacy Mode aktiv ist
                    self.watchers.append(watcher)

                    if init_result:
                        success_count += 1
                        _LOGGER.info("[%s] ✓ Erfolgreich initialisiert", name)
                    elif watcher._is_privacy_mode:
                        privacy_mode_count += 1
                        _LOGGER.info(
                            "[%s] 🔒 Privacy Mode aktiv - wird im Recovery Mode gestartet", name)
                    else:
                        _LOGGER.error(
                            "[%s] Initialisierung fehlgeschlagen", name)

                except Exception as e:
                    _LOGGER.error("Fehler beim Initialisieren der Kamera '%s': %s",
                                  camera_config.get('name', 'unbekannt'), e, exc_info=True)

            total_usable = success_count + privacy_mode_count

            if total_usable == 0:
                _LOGGER.error(
                    "Keine Kamera konnte initialisiert werden!")
                return False

            _LOGGER.info("✓ %d von %d Kamera(s) verbunden, %d im Privacy Mode Recovery",
                         success_count, len(enabled_cameras), privacy_mode_count)
            return True

        except Exception as e:
            _LOGGER.error(
                "Fehler bei der Kamera-Initialisierung: %s", e, exc_info=True)
            return False

    async def start_monitoring_all(self) -> None:
        """
        Startet die Überwachung aller Kameras parallel.
        """
        if not self.watchers:
            _LOGGER.error("Keine Kameras zum Überwachen verfügbar!")
            return

        _LOGGER.info("Starte Überwachung für %d Kamera(s)...",
                     len(self.watchers))

        # Erstelle Monitoring-Task für jede Kamera
        for watcher in self.watchers:
            task = asyncio.create_task(watcher.start_monitoring())
            self.monitoring_tasks.append(task)

        _LOGGER.info("✓ Alle Kameras überwachen aktiv")

        # Warte auf alle Tasks (läuft bis Abbruch)
        try:
            await asyncio.gather(*self.monitoring_tasks)
        except asyncio.CancelledError:
            _LOGGER.info("Monitoring aller Kameras wird beendet...")
            raise

    async def cleanup_all(self) -> None:
        """
        Räumt alle Kameras auf und trennt die Verbindungen.
        """
        _LOGGER.info("Beende alle Kamera-Verbindungen...")

        # Breche alle Monitoring-Tasks ab
        for task in self.monitoring_tasks:
            if not task.done():
                task.cancel()

        # Warte auf Abbruch aller Tasks
        if self.monitoring_tasks:
            await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)

        # Cleanup für jede Kamera
        cleanup_tasks = []
        for watcher in self.watchers:
            cleanup_tasks.append(watcher.cleanup())

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

        _LOGGER.info("✓ Alle Verbindungen getrennt")


async def main():
    """Hauptfunktion."""
    # Umgebungsvariablen laden (optional, falls noch .env verwendet wird)
    load_dotenv()

    # Multi-Kamera-Manager erstellen
    manager = MultiCameraManager(config_file="cameras.json")

    try:
        # Kameras initialisieren
        if not await manager.initialize_cameras():
            _LOGGER.error("Initialisierung fehlgeschlagen")
            return

        # Monitoring für alle Kameras starten
        await manager.start_monitoring_all()

    except KeyboardInterrupt:
        _LOGGER.info("Programm durch Benutzer beendet")
    except Exception as e:
        _LOGGER.error("Unerwarteter Fehler: %s", e, exc_info=True)
    finally:
        # Alle Kameras aufräumen
        await manager.cleanup_all()


if __name__ == "__main__":
    asyncio.run(main())
