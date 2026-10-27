import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

from bandwagon.app import Analyzer
from bandwagon.export_dialog import DEFAULT_OPTIONS
from bandwagon.fileio import _load_recent_files


class RecentFilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.directory = Path(directory).resolve()
        self.enterContext(patch('bandwagon.fileio._RECENT_FILES_PATH',
                                self.directory / 'recent.json'))
        settings_path = str(self.directory / 'settings.ini')
        self.enterContext(patch('bandwagon.app.QSettings', side_effect=lambda *args:
                                QSettings(settings_path, QSettings.IniFormat)))
        self.win = Analyzer()
        self.win._orig = Image.new('RGB', (100, 80), 'white')
        self.win._after_load('clipboard.png')

    def tearDown(self):
        self.win._saved_snapshot = self.win._project_state_snapshot()
        self.win.close()
        self.win.deleteLater()
        self.app.processEvents()

    def test_save_as_records_final_extension_and_updates_menu(self):
        path = self.directory / 'new project'
        with patch('bandwagon.fileio.QFileDialog.getSaveFileName',
                   return_value=(str(path), '')):
            self.win.save_project_as()
        saved = path.with_suffix('.bandwagon')
        self.assertTrue(saved.is_file())
        self.assertEqual(_load_recent_files(), [str(saved.resolve())])
        self.win._rebuild_recent_menu()
        action = self.win.m_recent.actions()[0]
        self.assertEqual(action.text(), saved.name)
        self.assertEqual(action.toolTip(), str(saved.resolve()))

    def test_save_existing_project_moves_to_front_without_duplicates(self):
        path = str(self.directory / 'existing.bandwagon')
        self.assertTrue(self.win._write_project_file(path))
        other = str(self.directory / 'other.png')
        self.win._add_recent_file(other)
        self.win.save_project()
        self.win.save_project()
        self.assertEqual(_load_recent_files(), [path, other])

    def test_cancelled_project_save_does_not_record_file(self):
        with patch('bandwagon.fileio.QFileDialog.getSaveFileName',
                   return_value=('', '')):
            self.win.save_project_as()
        self.assertEqual(_load_recent_files(), [])

    def test_failed_project_save_keeps_recent_list(self):
        existing = str(self.directory / 'previous.png')
        self.win._add_recent_file(existing)
        target = self.directory / 'failed.bandwagon'
        with patch('bandwagon.fileio.os.replace', side_effect=OSError('disk full')), \
                patch.object(self.win, '_warn') as warning:
            self.assertFalse(self.win._write_project_file(str(target)))
        warning.assert_called_once()
        self.assertFalse(target.exists())
        self.assertEqual(_load_recent_files(), [existing])

    def test_recovery_save_does_not_record_file(self):
        path = self.directory / 'recovery.bandwagon'
        self.assertTrue(self.win._write_project_file(str(path), recovery=True))
        self.assertTrue(path.is_file())
        self.assertEqual(_load_recent_files(), [])

    def test_saved_image_is_recorded(self):
        path = self.directory / 'result.png'
        with patch.object(self.win, '_export_options', return_value=DEFAULT_OPTIONS.copy()), \
                patch('bandwagon.fileio.QFileDialog.getSaveFileName',
                      return_value=(str(path), 'PNG (*.png)')):
            self.win.save_image()
        self.assertTrue(path.is_file())
        self.assertEqual(_load_recent_files(), [str(path.resolve())])

    def test_cancelled_image_save_does_not_record_file(self):
        with patch.object(self.win, '_export_options', return_value=DEFAULT_OPTIONS.copy()), \
                patch('bandwagon.fileio.QFileDialog.getSaveFileName',
                      return_value=('', '')):
            self.win.save_image()
        self.assertEqual(_load_recent_files(), [])

    def test_failed_image_save_does_not_record_file(self):
        path = self.directory / 'result.png'
        with patch.object(self.win, '_export_options', return_value=DEFAULT_OPTIONS.copy()), \
                patch('bandwagon.fileio.QFileDialog.getSaveFileName',
                      return_value=(str(path), 'PNG (*.png)')), \
                patch('PIL.Image.Image.save', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.win.save_image()
        self.assertEqual(_load_recent_files(), [])
