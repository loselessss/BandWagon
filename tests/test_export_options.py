import json
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

from bandwagon.export_dialog import DEFAULT_OPTIONS, ExportDialog, render_export
from bandwagon.models import Lane


class ExportOptionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = QSettings(os.path.join(self.temp.name, "export.ini"), QSettings.IniFormat)
        self.source = Image.new("RGB", (240, 160), "white")
        self.marker = Lane(0, 20, 100)
        self.marker.kind = "marker"
        self.marker.peaks = [80]
        self.marker.mw = [50.0]
        self.sample = Lane(1, 140, 220)
        self.sample.peaks = [80]
        self.sample.mw = [30.0]
        self.lanes = [self.marker, self.sample]

    def tearDown(self):
        self.settings = None
        self.temp.cleanup()

    def test_three_overlay_components_are_independent(self):
        empty = dict(DEFAULT_OPTIONS, photo=False, border=False, marker_mw=False, annotation=False)
        self.assertIsNone(render_export(self.source, self.lanes, empty).getchannel("A").getbbox())
        border = render_export(self.source, self.lanes, dict(empty, border=True))
        self.assertEqual(border.getpixel((20, 100))[3], 255)
        self.assertEqual(border.getpixel((60, 80))[3], 0)  # no band fills
        mw = render_export(self.source, self.lanes, dict(empty, marker_mw=True))
        self.assertIsNotNone(mw.crop((20, 0, 100, 160)).getchannel("A").getbbox())
        self.assertIsNone(mw.crop((140, 0, 220, 160)).getchannel("A").getbbox())
        names = render_export(self.source, self.lanes, dict(empty, annotation=True))
        self.assertGreater(names.height, self.source.height)
        self.assertIsNotNone(names.getchannel("A").getbbox())

    def test_text_and_graphic_transparency_are_independent(self):
        options = dict(DEFAULT_OPTIONS, photo=False, text_transparency=100, graphic_transparency=50)
        rendered = render_export(self.source, self.lanes, options)
        header = rendered.height - self.source.height
        self.assertIsNone(rendered.crop((0, 0, 240, header)).getchannel("A").getbbox())
        self.assertEqual(rendered.getpixel((20, header + 100))[3], 128)
        photo = render_export(self.source, [], dict(DEFAULT_OPTIONS, graphic_transparency=75))
        self.assertEqual(photo.size, self.source.size)
        self.assertEqual(photo.getpixel((0, 0))[3], 64)

    def test_dialog_remembers_accepted_options_and_cancel_does_not_save(self):
        dialog = ExportDialog(self.source, self.lanes, self.settings)
        dialog.linked.setChecked(False)
        dialog.text_alpha.setValue(35)
        dialog.graphic_alpha.setValue(65)
        dialog.accept()
        saved = json.loads(self.settings.value("export/options"))
        self.assertEqual(saved["text_transparency"], 35)
        restored = ExportDialog(self.source, self.lanes, self.settings)
        self.assertEqual(restored.options(), saved)
        restored.text_alpha.setValue(80)
        restored.reject()
        self.assertEqual(json.loads(self.settings.value("export/options")), saved)
        dialog.deleteLater(); restored.deleteLater()

    def test_empty_export_is_disabled_and_linked_values_follow(self):
        dialog = ExportDialog(self.source, self.lanes, self.settings)
        dialog.text_alpha.setValue(42)
        self.assertEqual(dialog.graphic_alpha.value(), 42)
        for check in dialog.checks.values():
            check.setChecked(False)
        dialog.refresh_preview()
        self.assertFalse(dialog.submit.isEnabled())
        dialog.accept()
        self.assertIsNone(self.settings.value("export/options"))
        dialog.deleteLater()

    def test_preview_is_bounded_and_does_not_change_lanes(self):
        source = Image.new("RGB", (3600, 2400))
        dialog = ExportDialog(source, self.lanes, self.settings)
        self.assertLessEqual(max(dialog.preview_source.size), 900)
        self.assertEqual(self.marker.x1, 20)
        self.assertEqual(self.marker.peaks, [80])
        self.assertEqual(dialog.preview_lanes[0].x1, 5)
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
