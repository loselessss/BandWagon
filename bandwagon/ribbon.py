"""Horizontal task ribbon and tool-specific settings routing."""
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QToolButton,
                            QScrollArea, QTabWidget, QButtonGroup, QLabel,
                            QPushButton, QAction, QMessageBox, QMenu)
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
            button = QToolButton(); button.setText(tr(label)); button.setIcon(icon(symbol)); button.setIconSize(QSize(18, 18))
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); button.setToolTip(tr(label)); button.setAccessibleName(tr(label))
            button.setMinimumHeight(34)
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
                          f'QToolButton:hover{{background:{INK3};}}QToolButton:checked{{background:{INK3};border-bottom:2px solid {CYAN};}}'
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
        self.ribbon = QTabWidget(); self.ribbon.setFixedHeight(84)
        self.ribbon.setStyleSheet(self._tabs_css() + 'QTabBar::tab{padding:8px 12px;}')
        self.ribbon_strips = []; self.ribbon_tools = {}
        self._ribbon_last = {0: 'rotate', 1: 'marker', 2: 'manual_lanes', 3: 'results'}
        self._lane_last_tool = 'manual_lanes'
        self._active_tool = 'rotate'; self._switching_tool = False
        def action(key, label, symbol, fn): return (key, label, symbol, fn, False)
        def setting(key, label, symbol):
            return (key, label, symbol, lambda: self._select_ribbon_tool(key), True)
        pages = [
            ('workflow_prepare', [action('open','dlg_open_title','open',self.open_anything),
                action('paste','toolbar_paste','paste',self.paste_image)]
                + [setting(k, label, sym) for k,label,sym in (
                ('rotate','tool_orientation','rotate'),('crop','tool_crop','crop'),
                ('bow','tool_shape','curve'),('brightness','tool_brightness','adjust'),('curve','tool_curve','curve'))]
                + [action('invert','tool_invert','color',self._invert_ribbon_colors)]),
            ('workflow_marker', [setting('marker','tool_marker','marker')]),
            ('workflow_lanes', [setting(k, 'tool_lane_adjust' if k == 'manual_lanes' else 'tool_'+k, sym) for k,sym in (
                ('manual_lanes','lanes'),('lane_list','memo'),('range','crop'))]),
            ('workflow_results', [setting('results','tool_results','analysis'),
                setting('quant','tab_std','quant'),
                action('copy','toolbar_copy_result','copy',self.copy_image),
                action('image','toolbar_save_result','save',self.save_image),
                action('csv','toolbar_export_csv','download',self.export_csv)])]
        category_icons = ('adjust', 'marker', 'lanes', 'analysis')
        existing_tips = {
            'save': 'toolbar_project_save_tip', 'save_as': 'toolbar_project_save_as_tip',
            'copy': 'toolbar_copy_result_tip', 'image': 'toolbar_save_result_tip',
            'make': 'toolbar_composite_studio_tip', 'import': 'toolbar_composite_import_tip',
            'undo': 'toolbar_undo_tip', 'redo': 'toolbar_redo_tip',
            'marker_presets': 'marker_preset_btn_tip', 'invert': 'invert_hint',
        }
        for index, (title, commands) in enumerate(pages):
            strip = ToolStrip(commands); self.ribbon.addTab(strip, f'{index + 1}  {tr(title)}'); self.ribbon_strips.append(strip)
            self.ribbon.setTabIcon(index, icon(category_icons[index]))
            for key, _, _, _, selectable in commands:
                if selectable: self.ribbon_tools[key] = (index, strip.buttons[key])
                strip.buttons[key].setToolTip(tr(existing_tips.get(key, 'ribbon_tip_' + key)))
        # File and infrequent utilities remain reachable without pretending to
        # be steps in the analysis workflow. History stays visible at all times.
        quick = QWidget(); row = QHBoxLayout(quick); row.setContentsMargins(0, 0, 8, 0); row.setSpacing(2)
        self.quick_buttons = {}
        for key, label, symbol, callback in (
                ('file', 'menu_file', 'open', None),
                ('save', 'toolbar_project_save', 'save', self.save_project),
                ('undo', 'toolbar_undo', 'undo', self._undo),
                ('redo', 'toolbar_redo', 'redo', self._redo)):
            button = QToolButton(); button.setIcon(icon(symbol)); button.setIconSize(QSize(18, 18))
            button.setAccessibleName(tr(label)); button.setToolTip(tr('workflow_file_tip' if key == 'file' else existing_tips[key]))
            button.setMinimumSize(30, 32)
            if key == 'file':
                button.setText(tr(label)); button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
                button.setMenu(self.m_file); button.setPopupMode(QToolButton.InstantPopup)
            else: button.clicked.connect(lambda checked=False, fn=callback: fn())
            row.addWidget(button); self.quick_buttons[key] = button
        self.memo_action = QAction(icon('memo'), tr('project_memo_label'), self)
        self.memo_action.setCheckable(True); self.memo_action.setToolTip(tr('ribbon_tip_memo'))
        self.memo_action.triggered.connect(lambda: self._select_ribbon_tool('memo'))
        self.m_file.addSeparator(); self.m_file.addAction(self.memo_action)
        for menu in (self.m_western, self.m_edit): self.m_file.addMenu(menu)
        self.ribbon.setCornerWidget(quick, Qt.TopLeftCorner)
        self.options_menu = QMenu(tr('workflow_options'), self)
        self.marker_presets_action = self.options_menu.addAction(icon('marker'), tr('tool_marker_presets'))
        self.marker_presets_action.setToolTip(tr('marker_preset_btn_tip'))
        self.marker_presets_action.triggered.connect(self._open_marker_presets)
        self.options_menu.addSeparator()
        self.options_menu.addMenu(self.m_language)
        for item in self.m_info.actions():
            if not item.isSeparator() and item.menu() is not self.m_language:
                self.options_menu.addAction(item)
        options = QToolButton(); options.setText(tr('workflow_options')); options.setIcon(icon('adjust'))
        options.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); options.setMenu(self.options_menu)
        options.setPopupMode(QToolButton.InstantPopup); options.setToolTip(tr('workflow_options_tip'))
        options.setMinimumHeight(32); self.options_button = options
        self.ribbon.setCornerWidget(options, Qt.TopRightCorner)
        self.ribbon.currentChanged.connect(self._on_ribbon_category)
        self.ribbon.tabBarClicked.connect(self._on_workflow_tab_clicked)
        self._select_ribbon_tool('rotate')
        self.btn_undo.changed.connect(self._sync_ribbon_history)
        self.btn_redo.changed.connect(self._sync_ribbon_history)
        self._sync_ribbon_history()
        return self.ribbon

    def _sync_ribbon_history(self):
        self.quick_buttons['undo'].setEnabled(self.btn_undo.isEnabled())
        self.quick_buttons['redo'].setEnabled(self.btn_redo.isEnabled())

    def _build_workflow_footer(self):
        footer = QWidget(); layout = QVBoxLayout(footer); layout.setContentsMargins(4, 4, 4, 4)
        self.workflow_hint = QLabel(); self.workflow_hint.setWordWrap(True)
        self.workflow_hint.setStyleSheet(f'color:{MUTE};font-size:11px;')
        layout.addWidget(self.workflow_hint)
        row = QHBoxLayout()
        self.workflow_back = QPushButton(tr('workflow_back')); self.workflow_back.setStyleSheet(self._btn_css())
        self.workflow_back.clicked.connect(lambda: self.ribbon.setCurrentIndex(max(0, self.ribbon.currentIndex() - 1)))
        self.workflow_next = QPushButton(); self.workflow_next.setStyleSheet(self._btn_accent_css())
        self.workflow_next.setMinimumHeight(36); self.workflow_next.clicked.connect(self._workflow_advance)
        row.addWidget(self.workflow_back); row.addWidget(self.workflow_next, 1); layout.addLayout(row)
        return footer

    def _update_workflow_state(self):
        if not hasattr(self, 'ribbon') or not hasattr(self, 'workflow_next'): return
        stage = self.ribbon.currentIndex()
        image = self._orig is not None
        detected = bool(self.lanes) and any(lane.peaks is not None and len(lane.peaks) for lane in self.lanes)
        fresh = detected and not getattr(self, '_analysis_stale', False)
        calibrated = fresh and any(lane.kind == 'marker' and
            sum(value is not None and value > 0 for value in lane.mw) >= 2 for lane in self.lanes)
        hints = ('workflow_prepare_hint', 'workflow_marker_hint', 'workflow_lanes_hint', 'workflow_results_hint')
        hint = hints[stage]
        if not image: hint = 'workflow_empty_hint'
        elif stage in (1, 2, 3) and getattr(self, '_analysis_stale', False): hint = 'workflow_stale_hint'
        elif stage == 2 and not fresh: hint = 'workflow_detect_hint'
        self.workflow_hint.setText(tr(hint))
        self.workflow_back.setVisible(stage > 0)
        self.workflow_back.setToolTip(tr('workflow_back_tip'))
        self.workflow_next.setText(tr(('workflow_to_marker', 'workflow_to_lanes', 'workflow_to_results', 'toolbar_copy_result')[stage]))
        self.workflow_next.setEnabled((image, image, fresh, image)[stage])
        self.workflow_next.setToolTip(tr(hint if not self.workflow_next.isEnabled() else
                                      ('workflow_marker_hint', 'workflow_lanes_hint', 'workflow_results_hint', 'toolbar_copy_result_tip')[stage]))
        selected = self.gel.selected_lane
        if selected in self.lanes:
            self.selected_lane_summary.setText(tr('workflow_selected_lane', name=selected.name,
                left=selected.x1, right=selected.x2, width=selected.x2 - selected.x1 + 1))
        else: self.selected_lane_summary.setText(tr('workflow_select_lane_hint'))
        # Detection/assignment is primary until complete; afterwards the next
        # step is primary. Never present two competing blue execution buttons.
        cta_state = (fresh, calibrated, bool(self.lanes), stage)
        if getattr(self, '_workflow_cta_state', None) != cta_state:
            self.btn_detect_bands.setStyleSheet(self._btn_css() if fresh else self._btn_accent_css())
            self.btn_marker_setup.setStyleSheet(self._btn_css() if calibrated or not self.lanes else self._btn_accent_css())
            self.workflow_next.setStyleSheet(self._btn_css() if stage == 1 and self.lanes and not calibrated else self._btn_accent_css())
            self._workflow_cta_state = cta_state

    def _workflow_advance(self):
        self._update_workflow_state()
        if not self.workflow_next.isEnabled(): return
        stage = self.ribbon.currentIndex()
        if stage == 3: self.copy_image()
        else: self.ribbon.setCurrentIndex(stage + 1)

    def _run_band_detection(self):
        self._finish_tool_preview()
        if self.run_analysis():
            if (not self._compute_mw() and self._prepared_marker_pending
                    and self.marker_preset_combo.currentData() is not None):
                self._select_ribbon_tool('marker')
                self._configure_marker_lane()
            else:
                self._select_ribbon_tool('results')

    def _invert_ribbon_colors(self):
        if self._orig is None: return
        self._finish_tool_preview()
        self._invert_colors()

    def _on_ribbon_category(self, index):
        if self._switching_tool: return
        self._select_ribbon_tool(self._ribbon_last[index])

    def _on_workflow_tab_clicked(self, index):
        if self._active_tool == 'memo' and index == self.ribbon.currentIndex():
            self._select_ribbon_tool(self._ribbon_last[index])

    def _confirm_tool_change(self):
        editor = getattr(self, '_inline_curve', None)
        curve = editor is not None and any(abs(y - editor.baseline) > 1e-6 for _, y in editor.points)
        crop = (self.gel.mode == 'crop' and self.gel.crop_rect is not None
                and not self.gel._crop_fresh)
        if not curve and not crop: return True
        box = self._box(QMessageBox.Question, tr('workflow_pending_title'), tr('workflow_pending_text'))
        apply = box.addButton(tr('workflow_apply_continue'), QMessageBox.AcceptRole)
        discard = box.addButton(tr('workflow_discard_continue'), QMessageBox.DestructiveRole)
        box.addButton(tr('btn_cancel'), QMessageBox.RejectRole)
        box.setStandardButtons(QMessageBox.NoButton); box.exec_()
        clicked = box.clickedButton()
        if clicked is apply:
            if editor is not None: editor.apply()
            elif crop: self._apply_crop()
            return True
        if clicked is discard:
            if editor is not None: editor.cancel()
            if crop: self._cancel_crop()
            return True
        return False

    def _finish_tool_preview(self):
        editor = getattr(self, '_inline_curve', None)
        if editor is not None: editor.apply()
        if getattr(self, '_color_preview_base', None) is not None:
            self._commit_adjust()
        pending = any(base is not None for base in (self._rot_base, self._curve_base, self._shear_base))
        self._finalize_pending_rotation(); self._finalize_pending_bow(); self._finalize_pending_shear()
        if pending: self._refresh_after_pixels_changed()

    def _select_ribbon_tool(self, name):
        name = {'flip': 'rotate', 'shear': 'bow'}.get(name, name)
        if name == 'auto_lanes':
            name = 'manual_lanes'
        if self._switching_tool: return
        if name == self._active_tool and (getattr(self, '_inline_curve', None) is not None
                or (name == 'crop' and self.gel.mode == 'crop')):
            # Re-clicking the active tool is not an Apply or Reset command.
            return
        if getattr(self, '_active_tool', None) != name:
            if not self._confirm_tool_change():
                category = (getattr(self, '_memo_stage', 0) if self._active_tool == 'memo'
                            else self.ribbon_tools[self._active_tool][0])
                self.ribbon.blockSignals(True); self.ribbon.setCurrentIndex(category); self.ribbon.blockSignals(False)
                self.ribbon_strips[category].select(self._active_tool)
                self._update_workflow_state()
                return
            self._finish_tool_preview()
        self._switching_tool = True
        try:
            selected = self.gel.selected_lane
            self._active_tool = name
            if name == 'memo':
                self._memo_stage = self.ribbon.currentIndex()
                category = self._memo_stage
            else:
                category, _ = self.ribbon_tools[name]
                self._ribbon_last[category] = name
            self.ribbon.setCurrentIndex(category)
            self.ribbon_strips[category].select(name)
            self.memo_action.setChecked(name == 'memo')
            if name == 'memo':
                group = self.ribbon_strips[category].group
                group.setExclusive(False)
                for button in group.buttons(): button.setChecked(False)
                group.setExclusive(True)
            if name in self.correct_tools:
                self.tabs.setCurrentIndex(0); self._show_correct_tool(name)
            elif name in self.lane_tools:
                self._lane_last_tool = name
                self.tabs.setCurrentIndex(1); self._show_lane_tool(name)
            else:
                self.tabs.setCurrentIndex({'results': 2, 'quant': 3, 'memo': 4}[name])
            self._on_tab_changed(self.tabs.currentIndex())
            if selected in self.lanes: self.gel.selected_lane = selected
            self.settings_title.setText(tr('project_memo_label') if name == 'memo' else self.ribbon_tools[name][1].text())
            self.profile_section.setVisible(self.tabs.currentIndex() in (1, 2, 3))
            if name == 'crop': self.btn_crop.setChecked(True)
            elif name == 'manual_lanes' and self._orig is not None:
                self.btn_lane.setChecked(True); self.gel.set_mode('lane')
            elif name == 'range' and self._orig is not None:
                self.btn_vrange.setChecked(True); self.gel.set_mode('vrange')
            self._update_workflow_state()
        finally:
            self._switching_tool = False

    def _sync_ribbon_from_tab(self, index):
        if not hasattr(self, 'ribbon') or self._switching_tool: return
        name = {0: self._ribbon_last.get(0, 'rotate'), 1: self._lane_last_tool,
                2: 'results', 3: 'quant', 4: 'memo'}[index]
        if name != self._active_tool: self._select_ribbon_tool(name)
