"""Render representative UI states without opening desktop windows.

Run with QT_SCALE_FACTOR=1, 1.25 and 1.5 to check scaled layouts.
Screenshots are written under build/ui-qa (not tracked).
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw
from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtGui import QFontDatabase, QFont
from PyQt5.QtWidgets import QApplication
from bandwagon.app import Analyzer
from bandwagon.export_dialog import ExportDialog
from bandwagon.straighten_dialog import StraightenDialog
from bandwagon.models import Lane
from bandwagon.dialogs import MarkerDialog, MarkerPresetManager
from bandwagon.composite import CompositeStudio
from bandwagon.update_dialog import UpdateDialog
from types import SimpleNamespace


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication([])
    # Qt's offscreen Windows plugin does not discover system fonts itself.
    if not QFontDatabase().families():
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/malgun.ttf"
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
            app.setFont(QFont("Malgun Gothic", 9))
    output = Path("build/ui-qa")
    output.mkdir(parents=True, exist_ok=True)
    scale = os.environ.get("QT_SCALE_FACTOR", "1")
    with tempfile.TemporaryDirectory() as settings_dir:
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, settings_dir)
        win = Analyzer()
        source = Image.new("RGB", (720, 520), "#c1d1dc")
        draw = ImageDraw.Draw(source)
        win._orig = source
        for x in range(80, 680, 120):
            for y in (90, 170, 280, 400):
                draw.rectangle((x, y, x + 60, y + 9), fill="#374f79")
        win._after_load("UI sample.png")
        win.lanes = [Lane(i, 70 + i * 120, 150 + i * 120) for i in range(5)]
        for lane in win.lanes:
            lane.peaks = [95, 175, 285, 405]
            lane.peak_bounds = [(y - 5, y + 5) for y in lane.peaks]
            lane.peak_area = [120.5, 234.5, 456.7, 890.1]
            lane.peak_volume = [10000, 20000, 30000, 40000]
        win.lanes[0].kind = "marker"
        win.lanes[0].mw = [100, 75, 50, 25]
        win._rebuild_lane_table(); win._refresh_results(); win.gel.set_lanes(win.lanes)
        win.resize(1000, 700); win.show()
        for index, name in ((0, "adjust"), (1, "lanes"), (2, "analysis"), (3, "quant"), (4, "memo")):
            win.tabs.setCurrentIndex(index); app.processEvents()
            win.grab().save(str(output / f"{name}-{scale}.png"))
        win.resize(900, 620); app.processEvents()
        win.grab().save(str(output / f"narrow-{scale}.png"))
        for tool, name in (("rotate", "geometry"), ("curve", "color"),
                           ("flip", "flip"), ("crop", "crop"), ("warp", "warp"),
                           ("bow", "bow"), ("shear", "shear"), ("brightness", "brightness"),
                           ("manual_lanes", "manual-lanes"), ("lane_list", "lane-list"),
                           ("bands", "bands"), ("range", "range")):
            win._select_ribbon_tool(tool); app.processEvents()
            win.grab().save(str(output / f"{name}-{scale}.png"))
        dialog = ExportDialog(source, win.lanes, win._layout_settings, win)
        dialog.checks["photo"].setChecked(False)
        dialog.refresh_preview(); dialog.show(); app.processEvents()
        dialog.grab().save(str(output / f"export-{scale}.png"))
        print(f"scale={scale}: main={win.width()}x{win.height()}, export={dialog.width()}x{dialog.height()}")
        dialog.reject()
        fixtures = [
            ('marker', MarkerDialog(4, [100, 75, 50, 25], win)),
            ('presets', MarkerPresetManager([], win)),
            ('composite', CompositeStudio(win)),
            ('update', UpdateDialog(SimpleNamespace(current_version='2.5.1', portable=False),
                SimpleNamespace(version='2.6.0', asset=None, release_notes='UI preview',
                                release_url='https://example.invalid/'), win)),
        ]
        for name, pane in fixtures:
            pane.show(); app.processEvents()
            pane.grab().save(str(output / f'{name}-{scale}.png'))
            pane.reject()
        win._select_ribbon_tool('bow')
        win._reference_bow()
        straight = win._inline_curve
        straight.points = [(0, 260), (180, 250), (330, 210), (540, 240), (719, 260)]
        straight.preview(); app.processEvents()
        win.grab().save(str(output / f"reference-curve-{scale}.png"))
        straight.cancel()
        win._saved_snapshot = win._project_state_snapshot()
        win.close(); app.processEvents()


if __name__ == "__main__":
    main()
