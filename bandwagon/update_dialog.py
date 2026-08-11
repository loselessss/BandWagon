"""GitHub Releases 업데이트 확인 및 다운로드 UI."""
from pathlib import Path
from threading import Event

from PyQt5.QtCore import QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QTextBrowser, QVBoxLayout,
)

from .dialogs import _dialog_style, _no_help_button
from .i18n import tr


def _size_text(size):
    return f"{size / (1024 * 1024):.1f} MB" if size > 0 else tr("update_size_unknown")


class UpdateCheckWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self._service = service

    def run(self):
        try:
            self.completed.emit(self._service.check())
        except Exception as error:
            self.failed.emit(str(error))


class UpdateDownloadWorker(QThread):
    progress = pyqtSignal(object)
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, service, update, parent=None):
        super().__init__(parent)
        self._service = service
        self._update = update
        self._cancel = Event()

    def request_cancel(self):
        self._cancel.set()

    def run(self):
        try:
            path = self._service.download(
                self._update, progress=self.progress.emit, cancel=self._cancel)
            self.completed.emit(str(path))
        except Exception as error:
            self.failed.emit(str(error))


class UpdateDialog(QDialog):
    install_requested = pyqtSignal(object)

    def __init__(self, service, update, parent=None):
        super().__init__(parent)
        _no_help_button(self)
        self.setStyleSheet(_dialog_style())
        self._service = service
        self._update = update
        self._worker = None
        self.setWindowTitle(tr("update_title"))
        self.setMinimumSize(600, 450)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"<h3>{tr('update_available', version=update.version)}</h3>"))
        form = QFormLayout()
        form.addRow(tr("update_current_version"), QLabel(service.current_version))
        form.addRow(tr("update_new_version"), QLabel(update.version))
        form.addRow(tr("update_package"), QLabel(
            f"{update.asset.name} ({_size_text(update.asset.size)})"
            if update.asset else tr("update_asset_pending")))
        layout.addLayout(form)
        layout.addWidget(QLabel(tr("update_release_notes")))
        self.notes = QTextBrowser()
        self.notes.setPlainText(update.release_notes or tr("update_no_notes"))
        layout.addWidget(self.notes, 1)
        self.progress = QProgressBar(); self.progress.hide(); layout.addWidget(self.progress)
        self.status_label = QLabel(""); self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText(tr("update_later"))
        buttons.rejected.connect(self.reject)
        self.release_button = QPushButton(tr("update_release_page"))
        self.release_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(update.release_url)))
        buttons.addButton(self.release_button, QDialogButtonBox.ActionRole)
        self.install_button = QPushButton(tr("update_download_install"))
        self.install_button.clicked.connect(self._start_download)
        buttons.addButton(self.install_button, QDialogButtonBox.AcceptRole)
        layout.addWidget(buttons)

        if update.asset is None:
            self.install_button.setEnabled(False)
            self.status_label.setText(tr(
                "update_no_portable" if service.portable else "update_no_installer"))
        elif not update.asset.sha256:
            self.install_button.setEnabled(False)
            self.status_label.setText(tr("update_no_checksum"))

    def _start_download(self):
        if self._worker is not None:
            return
        self.install_button.setEnabled(False); self.release_button.setEnabled(False)
        self.progress.show(); self.status_label.setText(tr("update_downloading"))
        worker = UpdateDownloadWorker(self._service, self._update, self)
        worker.progress.connect(self._on_progress)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_finished)
        self._worker = worker; worker.start()

    def _on_progress(self, value):
        if value.total_bytes:
            self.progress.setRange(0, 100)
            self.progress.setValue(min(100, round(
                value.completed_bytes * 100 / value.total_bytes)))
        else:
            self.progress.setRange(0, 0)
        self.status_label.setText(tr(
            "update_progress",
            completed=value.completed_bytes / (1024 * 1024),
            total=_size_text(value.total_bytes),
            speed=value.bytes_per_second / (1024 * 1024),
        ))

    def _on_completed(self, path):
        self.progress.setRange(0, 100); self.progress.setValue(100)
        self.status_label.setText(tr("update_verified"))
        self.install_requested.emit(Path(path)); self.accept()

    def _on_failed(self, message):
        self.status_label.setText(message)
        QMessageBox.warning(self, tr("update_download_failed"), message)

    def _on_finished(self):
        worker = self._worker; self._worker = None
        if worker:
            worker.deleteLater()
        self.release_button.setEnabled(True)
        if self._update.asset and self._update.asset.sha256:
            self.install_button.setEnabled(True)

    def reject(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_cancel()
            self.status_label.setText(tr("update_cancelling"))
            return
        super().reject()
