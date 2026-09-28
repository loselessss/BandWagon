"""Per-window crash recovery, independent of explicit project saves."""
import logging
import json
import os
import zipfile
import tempfile
from datetime import datetime
import uuid
from pathlib import Path

from PyQt5.QtCore import QLockFile, QStandardPaths, QTimer, QThread
from PyQt5.QtWidgets import QMessageBox, QApplication
from PIL import Image

from .i18n import tr
from .meta import APP_NAME, APP_VERSION


def recovery_directory():
    return Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation)) / "BandWagon" / "recovery"


class RecoveryWriter(QThread):
    """No widget access: encode a captured revision into a private staging file."""
    def __init__(self, owner, path, snapshot, metadata, image, gray):
        super().__init__(owner)
        self.path, self.snapshot = path, snapshot
        self.metadata, self.image, self.gray = metadata, image, gray
        self.temporary = None
        self.error = None
        self.disposition = "publish"
        self.lock = None

    def run(self):
        try:
            fd, self.temporary = tempfile.mkstemp(prefix=".bandwagon-", suffix=".tmp", dir=self.path.parent)
            os.close(fd)
            with zipfile.ZipFile(self.temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                # Independent PIL wrapper prevents concurrent manual-save encoder state races.
                with archive.open(zipfile.ZipInfo("image.png"), "w", force_zip64=True) as stream:
                    self.image.copy().save(stream, format="PNG")
                archive.writestr("project.json", self.metadata)
                if self.gray is not None:
                    with archive.open(zipfile.ZipInfo("wb_gray_override.png"), "w", force_zip64=True) as stream:
                        Image.fromarray(self.gray, "L").save(stream, format="PNG")
            with open(self.temporary, "rb+") as durable:
                os.fsync(durable.fileno())
        except Exception as error:
            self.error = str(error)
            logging.exception("Autosave encoding failed")
        finally:
            self.image = self.gray = None


class RecoveryMixin:
    def _init_recovery(self):
        self._recovery_path = None
        self._recovery_lock = None
        self._recovery_snapshot = None
        self._recovery_worker = None
        QApplication.instance().aboutToQuit.connect(self._finish_recovery_on_exit)
        self._recovery_timer = QTimer(self)
        self._recovery_timer.timeout.connect(self._autosave)
        self._recovery_timer.start(30000)

    def _clear_recovery(self):
        if self._recovery_worker is not None and self._recovery_worker.disposition == "publish":
            self._recovery_worker.disposition = "discard"
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
        worker = getattr(self, "_recovery_worker", None)
        if worker is not None and worker.disposition == "publish":
            worker.disposition = "detach"
            worker.lock = self._recovery_lock
            self._recovery_lock = None
        if getattr(self, "_recovery_lock", None):
            self._recovery_lock.unlock()
        self._recovery_path = self._recovery_lock = None
        self._recovery_snapshot = None

    def _autosave(self):
        if self._closing or self._orig is None or self._history_suspended or self._recovery_worker is not None:
            return
        try:
            snapshot = self._project_state_snapshot()
            if snapshot == self._saved_snapshot:
                self._clear_recovery()
                return
            if snapshot == self._recovery_snapshot:
                return
            if self._recovery_path is None:
                directory = recovery_directory()
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / (uuid.uuid4().hex + ".bandwagon")
                lock = QLockFile(str(path) + ".lock")
                lock.setStaleLockTime(0)
                if not lock.tryLock(0):
                    raise OSError("Unable to lock recovery file")
                self._recovery_path, self._recovery_lock = path, lock
            metadata = json.dumps(self._capture_project_metadata(recovery=True), ensure_ascii=False, indent=2)
            worker = RecoveryWriter(self, self._recovery_path, snapshot, metadata,
                                    self._orig, self._wb_gray_override)
            self._recovery_worker = worker
            worker.finished.connect(self._recovery_finished)
            worker.start()
        except Exception:
            logging.exception("Autosave failed")
            self.status.showMessage(tr("autosave_failed"), 10000)

    def _recovery_finished(self):
        worker = self._recovery_worker
        if worker is None:
            return
        try:
            if worker.error:
                if not self._closing:
                    self.status.showMessage(tr("autosave_failed"), 10000)
            elif worker.disposition != "discard":
                os.replace(worker.temporary, worker.path)
                worker.temporary = None
                if worker.disposition == "publish":
                    self._recovery_snapshot = worker.snapshot
        except Exception:
            logging.exception("Autosave publication failed")
            if not self._closing:
                self.status.showMessage(tr("autosave_failed"), 10000)
        finally:
            if worker.temporary:
                try:
                    Path(worker.temporary).unlink(missing_ok=True)
                except OSError:
                    logging.exception("Unable to remove autosave temporary file")
            if worker.lock:
                worker.lock.unlock()
            self._recovery_worker = None
            worker.deleteLater()
            if self._closing and self._update_worker is None:
                self.deleteLater()

    def _finish_recovery_on_exit(self):
        # Only application shutdown waits; editing and ordinary window closes never do.
        if self._recovery_worker is not None:
            self._recovery_worker.wait()
            self._recovery_finished()

    def _restore_recovery(self, path):
        if not self.open_project(str(path)):
            return False
        # Recovery is a copy: Ctrl+S must ask for a permanent destination.
        self._current_project_path = None
        self._last_dir = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or os.path.expanduser("~")
        self._saved_snapshot = None
        self._base_title = f"{tr('recovery_window_title')} — {APP_NAME} v{APP_VERSION}"
        self._refresh_title()
        return True

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
                    # Transfer the existing durable backup; no unsafe async copy/delete gap.
                    win._recovery_path, win._recovery_lock = path, lock
                    win._recovery_snapshot = win._project_state_snapshot()
                    lock = None
                win.show()
            except Exception:
                logging.exception("Recovery failed; retaining snapshot")
            finally:
                if lock is not None:
                    lock.unlock()
