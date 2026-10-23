"""Local-photo workflow smoke check; never commit its photo or output.

Example: python scripts/qa_workflow_phase2.py --photo C:/local/gel.png
Marker MW values below are test-only placeholders, not scientific results.
This exercises app commands, not a measured human click-count comparison.
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import QApplication
from bandwagon.app import Analyzer
from bandwagon.export_dialog import DEFAULT_OPTIONS, render_export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--photo', required=True)
    parser.add_argument('--rotate', type=int, default=-90)
    parser.add_argument('--crop', type=int, nargs=4, default=(330, 210, 1100, 735))
    parser.add_argument('--lanes', type=int, default=14)
    args = parser.parse_args()
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication([])
    if not QFontDatabase().families():
        font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/malgun.ttf'
        if font.exists():
            QFontDatabase.addApplicationFont(str(font)); app.setFont(QFont('Malgun Gothic', 9))
    output = Path('build/workflow-phase2'); output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as settings:
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, settings)
        win = Analyzer(); win.resize(900, 620); win.show()
        try:
            win.load_image(args.photo)
            assert win._orig is not None
            win._rotate(args.rotate)
            win._select_ribbon_tool('crop'); win.gel.crop_rect = tuple(args.crop)
            win.gel._crop_fresh = False; win._apply_crop()
            win._select_ribbon_tool('manual_lanes'); win.sp_lane_n.setValue(args.lanes)
            win._auto_lanes()
            assert len(win.lanes) == args.lanes
            assert not win._analysis_stale
            marker = win.lanes[0]
            assert marker.peaks is not None and len(marker.peaks) >= 2
            marker.kind = 'marker'
            marker.marker_mw = [round(250 / (i + 1), 2) for i in range(len(marker.peaks))]
            win._commit_lanes(); win._select_ribbon_tool('results'); app.processEvents()
            win.grab().save(str(output / 'photo-results.png'))
            values = [(lane.peaks.copy(), lane.peak_volume.copy(), list(lane.mw)) for lane in win.lanes]
            rendered = render_export(win._display, win.lanes, DEFAULT_OPTIONS)
            rendered.save(output / 'test-only-export.png')
            win.gel.selected_lane = win.lanes[4]
            win._select_ribbon_tool('quant'); app.processEvents()
            win.grab().save(str(output / 'photo-quant.png'))
            project = str(output / 'local-photo.bandwagon')
            assert win._write_project_file(project)
            assert win.open_project(project)
            assert win._active_tool == 'quant' and win.gel.selected_lane is win.lanes[4]
            for lane, (peaks, volumes, mw) in zip(win.lanes, values):
                np.testing.assert_array_equal(lane.peaks, peaks)
                np.testing.assert_array_equal(lane.peak_volume, volumes)
                assert lane.mw == mw
            assert render_export(win._display, win.lanes, DEFAULT_OPTIONS).tobytes() == rendered.tobytes()
            win.sp_prom.setValue(max(1, win.sp_prom.value() - 1))
            assert win._analysis_stale and not win._prepare_output()
            report = {'lanes': len(win.lanes), 'bands': sum(len(lane.peaks) for lane in win.lanes),
                      'resume_stage_selection': 'passed', 'mw_volume_roundtrip': 'identical',
                      'export_pixels_roundtrip': 'identical', 'stale_output_blocked': True,
                      'note': 'Test-only MW values. Scripted smoke check, not human click-count or accuracy validation.'}
            (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False))
        finally:
            win._saved_snapshot = win._project_state_snapshot(); win.close(); app.processEvents()


if __name__ == '__main__':
    main()
