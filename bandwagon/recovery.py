"""Per-window crash recovery, independent of explicit project saves."""
import logging
import json
import os
import zipfile
from datetime import datetime
import uuid
from pathlib import Path

from PyQt5.QtCore import QLockFile, QStandardPaths, QTimer
from PyQt5.QtWidgets import QMessageBox

from .i18n import tr
from .meta import APP_NAME, APP_VERSION


def recovery_directory():
    return Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation)) / "BandWagon" / "recovery"


class RecoveryMixin:
    def _init_recovery(self):
        self._recovery_path = None
        self._recovery_lock = None
        self._recovery_snapshot = None
        self._recovery_timer = QTimer(self)
        self._recovery_timer.timeout.connect(self._autosave)
        self._recovery_timer.start(30000)

    def _clear_recovery(self):
        try:
            if self._recovery_path:
                self._recovery_path.unlink(missing_ok=True)
        except OSError:
            logging.exception("Unable to remove recovery snapshot")
        if self._recovery_lock:
            self._recovery_lock.unlock()
        self._recovery_path = self._recovery_lock = None
        self._recovery_snapshot = None

    def _detach_recovery(self):
        """Keep the previous session's copy when replacing its image."""
        if getattr(self, "_recovery_lock", None):
            self._recovery_lock.unlock()
        self._recovery_path = self._recovery_lock = None
        self._recovery_snapshot = None

    def _autosave(self):
        if self._orig is None or self._history_suspended:
            return
        snapshot = self._project_state_snapshot()
        if snapshot == self._saved_snapshot:
            self._clear_recovery()
            return
        if snapshot == self._recovery_snapshot:
            return
        try:
            if self._recovery_path is None:
                directory = recovery_directory()
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / (uuid.uuid4().hex + ".bandwagon")
                lock = QLockFile(str(path) + ".lock")
                lock.setStaleLockTime(0)
                if not lock.tryLock(0):
                    raise OSError("Unable to lock recovery file")
                self._recovery_path, self._recovery_lock = path, lock
            if self._write_project_file(str(self._recovery_path), recovery=True):
                self._recovery_snapshot = snapshot
        except Exception:
            logging.exception("Autosave failed")
            self.status.showMessage(tr("autosave_failed"), 10000)

    def _restore_recovery(self, path):
        if not self.open_project(str(path)):
            return False
        # Recovery is a copy: Ctrl+S must ask for a permanent destination.
        self._current_project_path = None
        self._last_dir = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or os.path.expanduser("~")
        self._saved_snapshot = None
        self._base_title = f"{tr('recovery_window_title')} — {APP_NAME} v{APP_VERSION}"
        self._refresh_title()
        self._autosave()
        return self._recovery_snapshot is not None

    def offer_recovery(self):
        directory = recovery_directory()
        if not directory.exists():
            return
        for path in sorted(directory.glob("*.bandwagon")):
            lock = QLockFile(str(path) + ".lock")
            lock.setStaleLockTime(0)
            if not lock.tryLock(0):
                continue  # Another live window/process owns this snapshot.
            try:
                try:
                    with zipfile.ZipFile(path) as archive:
                        source = json.loads(archive.read("project.json")).get("recovery_source", path.stem)
                except (OSError, ValueError, KeyError, zipfile.BadZipFile):
                    source = path.stem
                choice = QMessageBox.question(
                    self, tr("recovery_title"),
                    tr("recovery_question", source=source, time=datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")),
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    QMessageBox.Yes)
                if choice == QMessageBox.Cancel:
                    break  # Keep remaining copies for the next launch.
                if choice == QMessageBox.No:
                    path.unlink()
                    continue
                win = self.__class__()
                self.__class__._open_windows.append(win)
                if win._restore_recovery(path):
                    path.unlink()  # New window now owns a fresh durable copy.
                win.show()
            except Exception:
                logging.exception("Recovery failed; retaining snapshot")
            finally:
                lock.unlock()
