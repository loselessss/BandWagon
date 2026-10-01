"""Scalable, font-independent line icons for the whole application."""
from PyQt5.QtCore import QObject, QEvent, Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QPainterPath
from PyQt5.QtWidgets import QPushButton, QAction, QTabWidget
from .i18n import tr


def icon(name, color='#f3f3f3'):
    pm = QPixmap(48, 48); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing); p.scale(2, 2)
    p.setPen(QPen(QColor(color), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    path = QPainterPath()
    if name == 'open':
        path.moveTo(3, 19); path.lineTo(3, 5); path.lineTo(10, 5); path.lineTo(12, 8); path.lineTo(21, 8); path.lineTo(18, 19); path.closeSubpath()
        path.moveTo(4, 11); path.lineTo(20, 11)
    elif name == 'save':
        p.drawRoundedRect(4, 3, 16, 18, 2, 2); p.drawRect(8, 3, 8, 6); p.drawRect(8, 14, 8, 7)
    elif name in ('copy', 'paste'):
        p.drawRoundedRect(8, 7, 12, 14, 2, 2); path.moveTo(5, 17); path.lineTo(3, 17); path.lineTo(3, 3); path.lineTo(15, 3)
    elif name in ('undo', 'redo', 'reset'):
        if name == 'redo': p.translate(24, 0); p.scale(-1, 1)
        path.moveTo(9, 4); path.lineTo(3, 10); path.lineTo(9, 15)
        path.moveTo(3, 10); path.lineTo(14, 10); path.cubicTo(23, 10, 22, 20, 14, 20)
    elif name in ('zoom_in', 'zoom_out'):
        p.drawEllipse(3, 3, 12, 12); p.drawLine(14, 14, 21, 21); p.drawLine(6, 9, 12, 9)
        if name == 'zoom_in': p.drawLine(9, 6, 9, 12)
    elif name == 'lanes':
        for x in (4, 10, 16): p.drawRoundedRect(x, 4, 4, 16, 1, 1)
    elif name in ('analysis', 'quant'):
        path.moveTo(3, 3); path.lineTo(3, 21); path.lineTo(21, 21)
        if name == 'analysis':
            path.moveTo(5, 18); path.lineTo(9, 13); path.lineTo(12, 16); path.lineTo(17, 6); path.lineTo(21, 10)
        else:
            for x, y in ((6, 15), (11, 10), (16, 5)): p.drawRect(x, y, 3, 20-y)
    elif name == 'adjust':
        for x, y in ((5, 8), (12, 16), (19, 10)):
            p.drawLine(x, 3, x, 21); p.fillRect(x-2, y-2, 4, 4, QColor('#272727')); p.drawEllipse(x-2, y-2, 4, 4)
    elif name == 'curve':
        path.moveTo(3, 18); path.cubicTo(8, 18, 10, 5, 21, 5)
        p.drawEllipse(10, 9, 4, 4)
    elif name == 'color':
        p.drawEllipse(3, 3, 18, 18); p.setBrush(QColor(color)); p.drawPie(3, 3, 18, 18, 90*16, 180*16)
    elif name == 'crop':
        path.moveTo(7, 3); path.lineTo(7, 17); path.lineTo(21, 17)
        path.moveTo(3, 7); path.lineTo(17, 7); path.lineTo(17, 21)
    elif name == 'rotate':
        path.moveTo(5, 9); path.cubicTo(6, 1, 20, 2, 21, 11)
        path.moveTo(2, 6); path.lineTo(5, 10); path.lineTo(9, 7)
        p.drawRoundedRect(8, 12, 11, 9, 1, 1)
    elif name == 'flip':
        path.moveTo(3, 5); path.lineTo(3, 19); path.lineTo(9, 19); path.closeSubpath()
        path.moveTo(21, 5); path.lineTo(21, 19); path.lineTo(15, 19); path.closeSubpath()
        p.setPen(QPen(QColor(color), 1, Qt.DashLine)); p.drawLine(12, 2, 12, 22)
        p.setPen(QPen(QColor(color), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    elif name in ('warp', 'shear'):
        path.moveTo(7, 4); path.lineTo(21, 4); path.lineTo(17, 20); path.lineTo(3, 20); path.closeSubpath()
        if name == 'warp':
            p.drawRect(7, 8, 10, 8)
        else:
            path.moveTo(9, 12); path.lineTo(15, 12); path.moveTo(12, 9); path.lineTo(15, 12); path.lineTo(12, 15)
    elif name == 'delete':
        path.moveTo(3, 6); path.lineTo(21, 6); p.drawRoundedRect(6, 6, 12, 15, 1, 1); p.drawLine(9, 3, 15, 3); p.drawLine(10, 10, 10, 17); p.drawLine(14, 10, 14, 17)
    elif name == 'download':
        path.moveTo(12, 3); path.lineTo(12, 16); path.moveTo(7, 11); path.lineTo(12, 16); path.lineTo(17, 11)
        path.moveTo(3, 17); path.lineTo(3, 21); path.lineTo(21, 21); path.lineTo(21, 17)
    elif name == 'memo':
        p.drawRoundedRect(4, 3, 16, 18, 2, 2)
        for y in (8, 12, 16): p.drawLine(8, y, 16, y)
    else:
        p.drawEllipse(3, 3, 18, 18); p.drawLine(12, 10, 12, 17); p.drawPoint(12, 7)
    p.drawPath(path); p.end(); pm.setDevicePixelRatio(2)
    return QIcon(pm)


KEYS = {
    'open': ('dlg_open_title', 'toolbar_composite_import', 'menu_project_open_location',
             'menu_western_open', 'wb_btn_load_visible', 'wb_btn_load_uv'),
    'save': ('toolbar_project_save', 'toolbar_project_save_as', 'toolbar_save_result', 'export_save_action', 'composite_btn_export'),
    'copy': ('toolbar_copy_result', 'export_copy_action'), 'paste': ('toolbar_paste',),
    'undo': ('toolbar_undo',), 'redo': ('toolbar_redo',),
    'reset': ('toolbar_reset_all', 'btn_reset_curve', 'btn_reset_adjust_all', 'reset_rotation', 'reset_bow', 'reset_shear', 'reference_reset', 'btn_reset_corners'),
    'analysis': ('btn_run_analysis', 'tab_analysis'), 'lanes': ('btn_auto_detect_lanes', 'tab_lanes'),
    'adjust': ('tab_adjust', 'tab_geometry'), 'color': ('btn_invert_colors', 'tab_color'),
    'curve': ('reference_bow_title',), 'crop': ('btn_auto_warp', 'btn_apply_warp'),
    'download': ('toolbar_export_csv', 'toolbar_check_updates', 'update_download_install'),
    'memo': ('project_memo_label',), 'quant': ('tab_std',), 'help': ('toolbar_help', 'toolbar_about'),
}


class IconStyler(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Show:
            mapping = {tr(key): name for name, keys in KEYS.items() for key in keys}
            if isinstance(obj, QPushButton) and obj.icon().isNull():
                name = mapping.get(obj.text())
                if name and obj.maximumWidth() > 80:
                    # Accent controls use dark foregrounds for icon contrast too.
                    color = '#10212b' if 'background:#60cdff;' in obj.styleSheet() else '#f3f3f3'
                    obj.setIcon(icon(name, color)); obj.setIconSize(QSize(16, 16))
            if isinstance(obj, QTabWidget):
                for i in range(obj.count()):
                    name = mapping.get(obj.tabText(i))
                    if name: obj.setTabIcon(i, icon(name))
                obj.setIconSize(QSize(14, 14))
            if hasattr(obj, 'actions'):
                for action in obj.actions():
                    name = mapping.get(action.text())
                    if name and action.icon().isNull(): action.setIcon(icon(name))
        return False


def install_icons(app):
    if not hasattr(app, '_fluent_icon_styler'):
        app._fluent_icon_styler = IconStyler(app)
        app.installEventFilter(app._fluent_icon_styler)
