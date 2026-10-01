"""Horizontal task ribbon and tool-specific settings routing."""
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QToolButton, QScrollArea, QTabWidget, QButtonGroup
from .fluent_icons import icon
from .i18n import tr
from .theme import *


class ToolStrip(QWidget):
    def __init__(self, commands, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self); layout.setContentsMargins(4, 2, 4, 2); layout.setSpacing(3)
        self.left = QToolButton(); self.left.setArrowType(Qt.LeftArrow); self.left.setToolTip(tr('ribbon_more_left'))
        self.right = QToolButton(); self.right.setArrowType(Qt.RightArrow); self.right.setToolTip(tr('ribbon_more_right'))
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget(); row = QHBoxLayout(content); row.setContentsMargins(2, 2, 2, 2); row.setSpacing(3)
        self.buttons = {}; self.group = QButtonGroup(self); self.group.setExclusive(True)
        for key, label, symbol, callback, selectable in commands:
            button = QToolButton(); button.setText(tr(label)); button.setIcon(icon(symbol)); button.setIconSize(QSize(24, 24))
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon); button.setToolTip(tr(label)); button.setAccessibleName(tr(label))
            button.setMinimumSize(65, 62)
            button.setCheckable(selectable)
            if selectable: self.group.addButton(button)
            button.clicked.connect(lambda checked=False, fn=callback: fn())
            row.addWidget(button); self.buttons[key] = button
        row.addStretch(); self.scroll.setWidget(content)
        layout.addWidget(self.left); layout.addWidget(self.scroll, 1); layout.addWidget(self.right)
        bar = self.scroll.horizontalScrollBar()
        self.left.clicked.connect(lambda: bar.setValue(bar.value() - 160))
        self.right.clicked.connect(lambda: bar.setValue(bar.value() + 160))
        bar.rangeChanged.connect(lambda *_: self.update_arrows())
        bar.valueChanged.connect(lambda *_: self.update_arrows())
        self.setStyleSheet(f'QToolButton{{border:1px solid transparent;border-radius:5px;padding:4px;color:{INKT};background:transparent;}}'
                          f'QToolButton:hover{{background:{INK3};}}QToolButton:checked{{background:#254553;border-color:{CYAN};}}'
                          f'QToolButton:focus{{border-color:{CYAN};}}QToolButton:pressed{{background:{INK4};}}')
        self.update_arrows()

    def update_arrows(self):
        bar = self.scroll.horizontalScrollBar()
        self.left.setVisible(bar.maximum() > 0); self.right.setVisible(bar.maximum() > 0)
        self.left.setEnabled(bar.value() > 0); self.right.setEnabled(bar.value() < bar.maximum())

    def select(self, key):
        if key in self.buttons:
            self.buttons[key].setChecked(True)
            self.scroll.ensureWidgetVisible(self.buttons[key], 8, 0)


class RibbonMixin:
    def _build_ribbon(self):
        self.ribbon = QTabWidget(); self.ribbon.setFixedHeight(110)
        self.ribbon.setStyleSheet(self._tabs_css() + 'QTabBar::tab{padding:8px 12px;}')
        self.ribbon_strips = []; self.ribbon_tools = {}
        self._ribbon_last = {1: 'rotate', 2: 'auto_lanes'}
        self._lane_last_tool = 'auto_lanes'
        self._active_tool = 'rotate'; self._switching_tool = False
        def action(key, label, symbol, fn): return (key, label, symbol, fn, False)
        def setting(key, label, symbol):
            return (key, label, symbol, lambda: self._select_ribbon_tool(key), True)
        pages = [
            ('menu_file', [action('open','dlg_open_title','open',self.open_anything),
                action('new','menu_new_window','open',self.new_window),
                action('recent','menu_recent_files','open',lambda: self.m_recent.exec_(self.ribbon.mapToGlobal(self.ribbon.rect().bottomLeft()))),
                action('paste','toolbar_paste','paste',self.paste_image),
                action('save','toolbar_project_save','save',self.save_project),
                action('save_as','toolbar_project_save_as','save',self.save_project_as),
                action('location','menu_project_open_location','open',self.open_project_location),
                action('copy','toolbar_copy_result','copy',self.copy_image),
                action('image','toolbar_save_result','save',self.save_image),
                action('csv','toolbar_export_csv','download',self.export_csv),
                setting('memo','project_memo_label','memo')]),
            ('tab_adjust', [setting(k,'tool_'+k, sym) for k,sym in (
                ('rotate','rotate'),('flip','flip'),('crop','crop'),('warp','warp'),('bow','curve'),
                ('shear','shear'),('brightness','adjust'),('curve','curve'))]
                + [action('invert','tool_invert','color',self._invert_ribbon_colors)]),
            ('tab_lanes', [setting(k, 'tool_'+k, sym) for k,sym in (
                ('auto_lanes','lanes'),('manual_lanes','adjust'),('lane_list','memo'),('range','crop'),('bands','analysis'))]
                + [action('run','btn_run_analysis','analysis',self._run_ribbon_analysis),
                setting('marker','tool_marker','marker'),
                setting('results','tool_results','analysis'),setting('quant','tab_std','quant'),
                action('marker_presets','tool_marker_presets','marker',self._open_marker_presets)]),
            ('menu_western', [action('make','menu_western_open','open',self.open_composite_studio),
                action('import','toolbar_composite_import','open',self.import_composite)]),
            ('menu_info', [action('undo','toolbar_undo','undo',self._undo),action('redo','toolbar_redo','redo',self._redo),
                action('reset','toolbar_reset_all','reset',self.reset_all),
                action('help','toolbar_help','help',self._show_help),action('about','toolbar_about','help',self._show_about),
                action('update','toolbar_check_updates','download',lambda: self.check_for_updates(True)),
                action('language','menu_language','color',lambda: self.m_language.exec_(self.ribbon.mapToGlobal(self.ribbon.rect().bottomLeft())))])]
        category_icons = ('open', 'adjust', 'lanes', 'open', 'help')
        for index, (title, commands) in enumerate(pages):
            strip = ToolStrip(commands); self.ribbon.addTab(strip, tr(title)); self.ribbon_strips.append(strip)
            self.ribbon.setTabIcon(index, icon(category_icons[index]))
            for key, _, _, _, selectable in commands:
                if selectable: self.ribbon_tools[key] = (index, strip.buttons[key])
                if key == 'marker_presets': strip.buttons[key].setToolTip(tr('marker_preset_btn_tip'))
                if key == 'invert': strip.buttons[key].setToolTip(tr('invert_hint'))
        self.ribbon.currentChanged.connect(self._on_ribbon_category)
        self.ribbon.setCurrentIndex(1)
        self._select_ribbon_tool('rotate')
        self.btn_undo.changed.connect(self._sync_ribbon_history)
        self.btn_redo.changed.connect(self._sync_ribbon_history)
        self._sync_ribbon_history()
        return self.ribbon

    def _sync_ribbon_history(self):
        strip = self.ribbon_strips[4]
        strip.buttons['undo'].setEnabled(self.btn_undo.isEnabled())
        strip.buttons['redo'].setEnabled(self.btn_redo.isEnabled())

    def _run_ribbon_analysis(self):
        self._finish_tool_preview()
        if self.run_analysis():
            self._select_ribbon_tool('bands')

    def _invert_ribbon_colors(self):
        if self._orig is None: return
        self._finish_tool_preview()
        self._invert_colors()

    def _on_ribbon_category(self, index):
        if self._switching_tool: return
        if index in self._ribbon_last:
            self._select_ribbon_tool(self._ribbon_last[index])
        elif index in (0, 3):
            # Finish visible edits before saving/exporting or opening the studio.
            self._finish_tool_preview()
            self._switching_tool = True
            try: self._on_tab_changed(self.tabs.currentIndex())
            finally: self._switching_tool = False

    def _finish_tool_preview(self):
        editor = getattr(self, '_inline_curve', None)
        if editor is not None: editor.apply()
        if getattr(self, '_color_preview_base', None) is not None:
            self._commit_adjust()
        pending = any(base is not None for base in (self._rot_base, self._curve_base, self._shear_base))
        self._finalize_pending_rotation(); self._finalize_pending_bow(); self._finalize_pending_shear()
        if pending: self._refresh_after_pixels_changed()

    def _select_ribbon_tool(self, name):
        if self._switching_tool: return
        if getattr(self, '_active_tool', None) != name:
            self._finish_tool_preview()
        self._switching_tool = True
        try:
            self._active_tool = name
            category, _ = self.ribbon_tools[name]
            self._ribbon_last[category] = name
            self.ribbon.setCurrentIndex(category)
            self.ribbon_strips[category].select(name)
            if name in self.correct_tools:
                self.tabs.setCurrentIndex(0); self._show_correct_tool(name)
            elif name in self.lane_tools:
                self._lane_last_tool = name
                self.tabs.setCurrentIndex(1); self._show_lane_tool(name)
            else:
                self.tabs.setCurrentIndex({'results': 2, 'quant': 3, 'memo': 4}[name])
            self._on_tab_changed(self.tabs.currentIndex())
            self.settings_title.setText(self.ribbon_tools[name][1].text())
            self.profile.setVisible(self.tabs.currentIndex() in (1, 2, 3))
            if name == 'crop': self.btn_crop.setChecked(True)
        finally:
            self._switching_tool = False

    def _sync_ribbon_from_tab(self, index):
        if not hasattr(self, 'ribbon') or self._switching_tool: return
        name = {0: self._ribbon_last.get(1, 'rotate'), 1: self._lane_last_tool,
                2: 'results', 3: 'quant', 4: 'memo'}[index]
        if name != self._active_tool: self._select_ribbon_tool(name)
