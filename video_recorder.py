"""
Video Recorder für Reolink-Kameras
Zeichnet Video-Clips während der Personenerkennung auf.
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional
from reolink_aio.api import Host

_LOGGER = logging.getLogger(__name__)


class VideoRecorder:
    """Verwaltet die Video-Aufnahme von der Reolink-Kamera."""

    def __init__(
        self,
        host_obj: Host,
        channel: int,
        output_dir: Path,
        post_detection_duration: int = 15,
        stream_format: str = "h264"
    ):
        """
        Initialisiert den Video-Recorder.

        Args:
            host_obj: Reolink Host Objekt
            channel: Kamera-Kanal
            output_dir: Ausgabeverzeichnis für Videos
            post_detection_duration: Sekunden nach Erkennung aufnehmen
            stream_format: Video-Format (h264 oder h265)
        """
        self.host_obj = host_obj
        self.channel = channel
        self.output_dir = output_dir
        self.post_detection_duration = post_detection_duration
        self.stream_format = stream_format.lower()

        self._recording_process: Optional[subprocess.Popen] = None
        self._recording_file: Optional[Path] = None
        self._stop_timer_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_recording = False
        self._recording_start_time: Optional[datetime] = None

    def _get_rtsp_url(self) -> str:
        """
        Erstellt die RTSP-URL für die Kamera.
        Unterstützt H.264 (Preview) und H.265 (h265Preview) Streams.
        Verwendet immer den Main-Stream.

        Returns:
            RTSP-URL
        """
        # RTSP Port abrufen
        rtsp_port = self.host_obj.rtsp_port or 554

        # Stream-Pfad basierend auf Format und Kanal
        # H.264: Preview_<channel>_main
        # H.265: h265Preview_<channel>_main
        # Reolink Kanäle beginnen bei 01, nicht 00 (channel 0 = 01, channel 1 = 02, etc.)
        channel_str = f"{self.channel + 1:02d}"  # 0 -> "01", 1 -> "02", etc.

        # Bestimme Stream-Präfix basierend auf Format
        if self.stream_format == "h265":
            stream_path = f"h265Preview_{channel_str}_main"
        else:
            stream_path = f"Preview_{channel_str}_main"

        # RTSP URL zusammenbauen
        url = (
            f"rtsp://{self.host_obj.username}:{self.host_obj._password}"
            f"@{self.host_obj.host}:{rtsp_port}"
            f"/{stream_path}"
        )

        return url

    async def start_recording(self) -> bool:
        """
        Startet die Video-Aufnahme.

        Returns:
            True bei Erfolg, False bei Fehler
        """
        # Wenn bereits aufgenommen wird, Timer abbrechen
        if self._is_recording:
            _LOGGER.info("Aufnahme läuft bereits, verlängere Dauer...")

            # Stop-Timer abbrechen falls vorhanden
            if self._stop_timer_task and not self._stop_timer_task.done():
                self._stop_timer_task.cancel()
                self._stop_timer_task = None

            return True

        try:
            # Dateiname mit Zeitstempel und Channel
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Füge Channel-Nummer hinzu um Kollisionen zu vermeiden
            filename = f"person_detection_{timestamp}_ch{self.channel}.mp4"
            self._recording_file = self.output_dir / filename

            # RTSP URL abrufen
            rtsp_url = self._get_rtsp_url()

            _LOGGER.info("Starte Video-Aufnahme auf Kanal %s: %s",
                         self.channel, self._recording_file.name)

            # FFmpeg Kommando zum Aufnehmen
            # -rtsp_transport tcp: Verwende TCP statt UDP für stabilere Verbindung
            # -i: Input (RTSP Stream)
            # -c:v copy: Kopiere Video-Stream ohne Re-Encoding (schneller, weniger CPU)
            # -c:a aac: Audio in AAC-Format enkodieren (MP4-kompatibel)
            # -b:a 128k: Audio-Bitrate 128 kbit/s
            # -movflags +faststart: Optimierung für MP4
            # -f mp4: Output-Format
            cmd = [
                'ffmpeg',
                '-rtsp_transport', 'tcp',
                '-i', rtsp_url,
                '-c:v', 'copy',
                # Audio aufnehmen und in AAC enkodieren
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-f', 'mp4',
                '-y',  # Überschreibe Datei falls vorhanden
                str(self._recording_file)
            ]

            # FFmpeg im Hintergrund starten mit eigener Prozessgruppe
            self._recording_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,  # stdin offen lassen für 'q' Kommando
                start_new_session=True  # Neue Session für sauberes Beenden
            )

            self._is_recording = True
            self._recording_start_time = datetime.now()

            # Starte Monitoring-Task
            self._monitor_task = asyncio.create_task(self._monitor_ffmpeg())

            _LOGGER.info("✓ Video-Aufnahme gestartet")
            return True

        except FileNotFoundError:
            _LOGGER.error(
                "FFmpeg nicht gefunden! Bitte installieren: sudo apt install ffmpeg")
            return False
        except Exception as e:
            _LOGGER.error("Fehler beim Starten der Aufnahme: %s",
                          e, exc_info=True)
            return False

    async def stop_recording(self) -> Optional[Path]:
        """
        Stoppt die Video-Aufnahme sofort.

        Returns:
            Pfad zur aufgenommenen Datei oder None
        """
        if not self._is_recording or not self._recording_process:
            return None

        try:
            _LOGGER.info("Stoppe Video-Aufnahme...")

            # Speichere Referenzen für Cleanup
            recording_file = self._recording_file
            recording_process = self._recording_process
            recording_start_time = self._recording_start_time
            monitor_task = self._monitor_task
            stop_timer_task = self._stop_timer_task

            # Setze Status sofort zurück
            self._is_recording = False
            self._recording_file = None
            self._recording_process = None
            self._recording_start_time = None
            self._monitor_task = None
            self._stop_timer_task = None

            # Timer abbrechen falls vorhanden
            if stop_timer_task and not stop_timer_task.done():
                stop_timer_task.cancel()
                try:
                    await stop_timer_task
                except asyncio.CancelledError:
                    pass

            # Monitor-Task abbrechen falls vorhanden
            if monitor_task and not monitor_task.done():
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass

            # Prozess beenden
            process_already_stopped = False
            if recording_process.poll() is not None:
                # Prozess ist bereits beendet
                process_already_stopped = True
                exit_code = recording_process.returncode
                _LOGGER.debug(
                    "FFmpeg bereits beendet (Exit-Code: %d)", exit_code)
            else:
                # Sende 'q' an FFmpeg stdin für sauberes Beenden
                try:
                    if recording_process.stdin and not recording_process.stdin.closed:
                        recording_process.stdin.write(b'q')
                        recording_process.stdin.flush()
                        _LOGGER.debug("'q' an FFmpeg gesendet")
                        # Gib FFmpeg mehr Zeit zum sauberen Beenden
                        await asyncio.sleep(0.5)
                except (BrokenPipeError, OSError):
                    _LOGGER.debug("Stdin bereits geschlossen")
                except Exception as e:
                    _LOGGER.debug("Fehler beim Senden von 'q': %s", e)

                # Warte auf Prozess-Ende (max 10 Sekunden für sicheres Schreiben)
                for _ in range(100):  # 10 Sekunden in 0.1s Schritten
                    if recording_process.poll() is not None:
                        break
                    await asyncio.sleep(0.1)

                if recording_process.poll() is None:
                    _LOGGER.warning(
                        "FFmpeg reagiert nicht, erzwinge Beenden...")
                    try:
                        recording_process.terminate()
                        await asyncio.sleep(2.0)  # Mehr Zeit zum Finalisieren
                        if recording_process.poll() is None:
                            recording_process.kill()
                            await asyncio.sleep(0.5)
                    except:
                        pass

                # Schließe stdin nach dem Warten
                try:
                    if recording_process.stdin and not recording_process.stdin.closed:
                        recording_process.stdin.close()
                except:
                    pass

            # Cleanup stderr
            if recording_process.stderr:
                try:
                    recording_process.stderr.close()
                except:
                    pass

            # Warte auf vollständiges Schreiben der Datei
            _LOGGER.debug("Warte auf vollständiges Schreiben der Datei...")
            max_wait_attempts = 30  # Max 15 Sekunden für sicheres Schreiben
            last_size = 0
            stable_count = 0

            for attempt in range(max_wait_attempts):
                await asyncio.sleep(0.5)

                if recording_file and recording_file.exists():
                    current_size = recording_file.stat().st_size

                    # Dateigröße muss 3x stabil sein für mehr Sicherheit
                    if current_size > 0:
                        if current_size == last_size:
                            stable_count += 1
                            if stable_count >= 3:
                                _LOGGER.debug(
                                    "Dateigröße stabil bei %d Bytes", current_size)
                                break
                        else:
                            stable_count = 0

                    last_size = current_size
                else:
                    last_size = 0

            # Extra Sicherheitswarte - wichtig für MP4 Finalisierung
            await asyncio.sleep(1.0)

            # Dauer berechnen
            duration = None
            if recording_start_time:
                duration = (datetime.now() -
                            recording_start_time).total_seconds()

            # Prüfe Endergebnis und logge IMMER
            if recording_file and recording_file.exists():
                final_size = recording_file.stat().st_size
                if final_size > 0:
                    size_mb = final_size / 1024 / 1024
                    if duration:
                        _LOGGER.info("✓ Video gespeichert: %s (%.2f MB, %.1f Sekunden)",
                                     recording_file.name, size_mb, duration)
                    else:
                        _LOGGER.info("✓ Video gespeichert: %s (%.2f MB)",
                                     recording_file.name, size_mb)
                    return recording_file
                else:
                    _LOGGER.warning(
                        "Aufnahme-Datei ist leer (0 Bytes), lösche...")
                    recording_file.unlink()
                    return None
            else:
                _LOGGER.warning("Aufnahme-Datei wurde nicht erstellt: %s",
                                recording_file if recording_file else "unbekannt")
                return None

        except Exception as e:
            _LOGGER.error("Fehler beim Stoppen der Aufnahme: %s",
                          e, exc_info=True)
            self._is_recording = False
            return None

    async def _monitor_ffmpeg(self) -> None:
        """Überwacht den FFmpeg-Prozess und loggt wenn er unerwartet endet."""
        try:
            while self._is_recording and self._recording_process:
                # Prüfe alle 2 Sekunden ob Prozess noch läuft
                await asyncio.sleep(2.0)

                if self._recording_process and self._recording_process.poll() is not None:
                    exit_code = self._recording_process.returncode

                    # Nur bei Fehlern warnen (Exit-Code != 0)
                    if exit_code != 0:
                        _LOGGER.error(
                            "⚠️ FFmpeg unerwartet beendet (Exit-Code: %d)", exit_code)

                        # Lese stderr für Fehlerdiagnose
                        if self._recording_process.stderr:
                            try:
                                stderr_output = self._recording_process.stderr.read().decode('utf-8',
                                                                                             errors='ignore')
                                if stderr_output:
                                    stderr_lines = stderr_output.strip().split('\n')
                                    last_lines = stderr_lines[-15:]
                                    _LOGGER.error(
                                        "FFmpeg Fehlerausgabe:\n%s", '\n'.join(last_lines))
                            except Exception as e:
                                _LOGGER.debug(
                                    "Konnte stderr nicht lesen: %s", e)
                    else:
                        _LOGGER.debug("FFmpeg normal beendet (Exit-Code: 0)")

                    # Prozess ist beendet - Monitor stoppt hier
                    # stop_recording() wird das Cleanup übernehmen
                    break

        except asyncio.CancelledError:
            _LOGGER.debug("FFmpeg Monitoring gestoppt")
            raise

    async def stop_recording_delayed(self) -> None:
        """
        Stoppt die Aufnahme nach dem konfigurierten Post-Detection-Timer.
        """
        # Vorherigen Timer abbrechen falls vorhanden
        if self._stop_timer_task and not self._stop_timer_task.done():
            self._stop_timer_task.cancel()

        # Neuen Timer starten
        self._stop_timer_task = asyncio.create_task(self._delayed_stop())

    async def _delayed_stop(self) -> None:
        """
        Interne Methode für verzögerten Stop.
        """
        try:
            _LOGGER.info("Aufnahme läuft noch %d Sekunden weiter...",
                         self.post_detection_duration)

            await asyncio.sleep(self.post_detection_duration)

            _LOGGER.info("Post-Detection-Timer abgelaufen")
            await self.stop_recording()

        except asyncio.CancelledError:
            _LOGGER.debug(
                "Verzögerter Stop wurde abgebrochen (erneute Erkennung)")
            raise

    @property
    def is_recording(self) -> bool:
        """Gibt True zurück wenn gerade aufgenommen wird."""
        return self._is_recording
