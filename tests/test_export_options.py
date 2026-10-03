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

    def test_select_all_preserves_transparency_and_persists(self):
        for saving in (False, True):
            dialog = ExportDialog(self.source, self.lanes, self.settings, saving=saving)
            for check in dialog.checks.values():
                check.setChecked(False)
            dialog.text_alpha.setValue(25)
            dialog.select_all.click()
            self.assertTrue(all(dialog.options()[key] for key in dialog.checks))
            self.assertEqual(dialog.options()['text_transparency'], 25)
            self.assertEqual(dialog.options()['graphic_transparency'], 25)
            dialog.accept()
            saved = json.loads(self.settings.value('export/options'))
            self.assertTrue(all(saved[key] for key in dialog.checks))
            dialog.close()

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

    def test_band_ranges_follow_area_or_line_style_and_graphic_transparency(self):
        self.assertFalse(DEFAULT_OPTIONS['bands'])
        self.sample.peak_bounds = [(70, 90)]
        options = dict(DEFAULT_OPTIONS, photo=False, border=False, marker_mw=False,
                       lane_mw=False, annotation=False)
        self.assertIsNone(render_export(self.source, self.lanes, options).getchannel('A').getbbox())
        options['bands'] = True
        area = render_export(self.source, self.lanes, options, band_style='area')
        self.assertEqual(area.getpixel((180, 70))[3], 255)
        self.assertEqual(area.getpixel((180, 80))[3], 55)
        self.assertEqual(area.getpixel((180, 100))[3], 0)
        line = render_export(self.source, self.lanes, options, band_style='line')
        self.assertEqual(line.getpixel((180, 80))[3], 255)
        self.assertEqual(line.getpixel((180, 70))[3], 0)
        transparent = render_export(self.source, self.lanes,
                                    dict(options, graphic_transparency=100), band_style='area')
        self.assertIsNone(transparent.getchannel('A').getbbox())

    def test_band_option_is_remembered_and_preview_uses_current_style(self):
        old = {key: value for key, value in DEFAULT_OPTIONS.items() if key != 'bands'}
        self.settings.setValue('export/options', json.dumps(old))
        dialog = ExportDialog(self.source, self.lanes, self.settings, band_style='line')
        self.assertFalse(dialog.checks['bands'].isChecked())
        for key, check in dialog.checks.items(): check.setChecked(key == 'bands')
        dialog.refresh_preview()
        self.assertTrue(dialog.submit.isEnabled())
        self.assertEqual(dialog.band_style, 'line')
        self.assertEqual(dialog.preview.pixmap.toImage().pixelColor(180, 80).alpha(), 255)
        self.assertEqual(dialog.preview.pixmap.toImage().pixelColor(180, 70).alpha(), 0)
        dialog.accept()
        restored = ExportDialog(self.source, self.lanes, self.settings, saving=True, band_style='area')
        self.assertTrue(restored.checks['bands'].isChecked())
        self.assertEqual(restored.band_style, 'area')
        dialog.deleteLater(); restored.deleteLater()

    def test_lane_mw_is_off_by_default_and_independent_of_marker_mw(self):
        self.assertFalse(DEFAULT_OPTIONS['lane_mw'])
        empty = dict(DEFAULT_OPTIONS, photo=False, border=False, marker_mw=False, annotation=False)
        for marker, sample in ((False, True), (True, False), (True, True)):
            rendered = render_export(self.source, self.lanes,
                                     dict(empty, marker_mw=marker, lane_mw=sample))
            self.assertEqual(rendered.crop((20, 0, 100, 160)).getchannel('A').getbbox() is not None, marker)
            self.assertEqual(rendered.crop((140, 0, 220, 160)).getchannel('A').getbbox() is not None, sample)
        self.sample.kind = 'bsa'
        rendered = render_export(self.source, self.lanes, dict(empty, lane_mw=True))
        self.assertIsNotNone(rendered.crop((140, 0, 220, 160)).getchannel('A').getbbox())

    def test_old_saved_options_default_lane_mw_off_and_new_selection_is_remembered(self):
        old = {key: value for key, value in DEFAULT_OPTIONS.items() if key != 'lane_mw'}
        self.settings.setValue('export/options', json.dumps(old))
        dialog = ExportDialog(self.source, self.lanes, self.settings)
        self.assertFalse(dialog.checks['lane_mw'].isChecked())
        dialog.checks['lane_mw'].setChecked(True)
        dialog.accept()
        restored = ExportDialog(self.source, self.lanes, self.settings, saving=True)
        self.assertTrue(restored.checks['lane_mw'].isChecked())
        restored.text_alpha.setValue(100)
        rendered = render_export(self.source, self.lanes,
                                 dict(restored.options(), photo=False, border=False, annotation=False))
        self.assertIsNone(rendered.getchannel('A').getbbox())
        dialog.deleteLater(); restored.deleteLater()

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
