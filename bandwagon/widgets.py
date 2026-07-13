"""bandwagon.widgets

커스텀 paintEvent 위젯들: CurveWidget/ChannelBar/GelView/
ThumbView/ProfileView/StdCurveView/SliderRow.

(BandWagon v1.1을 모듈로 분할한 것 — 동작은 원본과 동일.)
"""
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFileDialog, QSlider, QGroupBox, QStatusBar,
    QToolBar, QAction, QSizePolicy, QMessageBox, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget, QSpinBox, QDoubleSpinBox,
    QComboBox, QInputDialog, QDialog, QDialogButtonBox, QFormLayout,
    QScrollArea, QCheckBox,
)
from PyQt5.QtCore import Qt, QPoint, QPointF, QRectF, QRect, QSize, pyqtSignal, QTimer, QStandardPaths
from PyQt5.QtGui import (
    QPainter, QPen, QColor, QPixmap, QImage, QBrush,
    QPainterPath, QLinearGradient, QFont, QFontMetrics, QPolygonF, QPalette,
)
from .theme import *
from .i18n import tr
from .models import CurveModel
from .imaging import pil_to_pixmap


class CurveWidget(QWidget):
    """포토샵식 톤 커브 위젯. QRectF/QPointF/QPainterPath/setClipRect
    조합이 일부 Qt5.15/Windows에서 차트 영역을 통째로 안 그리는 흰배경
    버그를 냈던 적이 있어, 모든 좌표를 정수(int)로 계산해 정수 오버로드
    그리기 함수만 쓴다."""
    changed = pyqtSignal()
    released = pyqtSignal()   # 점 편집을 끝낸 시점(드래그 release/우클릭 삭제) — 되돌리기 커밋 지점
    SIDE = 286
    GRAD = 11
    PADT = 9

    def __init__(self, channel="RGB", parent=None):
        super().__init__(parent)
        self.channel = channel
        self.model = CurveModel()
        self.hist = None
        self._sel = None
        self._hover = None
        self._drag = False
        self._dirty = False   # changed를 emit했지만 아직 released를 안 보낸 상태
        self._marker = None
        self.setFixedSize(self.SIDE, self.SIDE)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

    def set_histogram(self, h):
        self.hist = h
        self.update()

    def _chart(self):
        l = self.GRAD; t = self.PADT
        w = self.width() - self.GRAD - self.PADT
        h = self.height() - self.PADT - self.GRAD
        return (l, t, w, h)

    def _wx(self, ix):
        l, t, w, h = self._chart()
        return int(round(l + ix / 255.0 * w))

    def _wy(self, iy):
        l, t, w, h = self._chart()
        return int(round(t + (1.0 - iy / 255.0) * h))

    def _to_curve(self, wx, wy):
        l, t, w, h = self._chart()
        ix = (wx - l) / max(w, 1) * 255.0
        iy = (1.0 - (wy - t) / max(h, 1)) * 255.0
        return (int(round(float(np.clip(ix, 0, 255)))),
                int(round(float(np.clip(iy, 0, 255)))))

    def _hit(self, wx, wy):
        for i, (px, py) in enumerate(self.model.points):
            if (wx - self._wx(px)) ** 2 + (wy - self._wy(py)) ** 2 < 12 ** 2:
                return i
        return None

    def mousePressEvent(self, e):
        wx, wy = e.x(), e.y()
        idx = self._hit(wx, wy)
        if e.button() == Qt.LeftButton:
            if idx is not None:
                self._sel = idx; self._drag = True
            else:
                cx, cy = self._to_curve(wx, wy)
                self._sel = self.model.add_point(cx, cy)
                self._drag = True
                self.changed.emit()
                self._dirty = True
        elif e.button() == Qt.RightButton:
            if idx is not None:
                self.model.remove_point(idx)
                self._sel = None
                self.changed.emit()
                self.released.emit()   # 우클릭 삭제는 release가 안 따라오므로 즉시 커밋
        self.update()

    def mouseMoveEvent(self, e):
        wx, wy = e.x(), e.y()
        if self._drag and self._sel is not None:
            cx, cy = self._to_curve(wx, wy)
            ax = self.model.move_point(self._sel, cx, cy)
            for i, (px, _) in enumerate(self.model.points):
                if px == ax:
                    self._sel = i; break
            self._marker = ax
            self.changed.emit()
            self._dirty = True
        else:
            self._hover = self._hit(wx, wy)
            l, t, w, h = self._chart()
            inside = (l <= wx <= l + w and t <= wy <= t + h)
            self._marker = self._to_curve(wx, wy)[0] if inside else None
        self.update()

    def mouseReleaseEvent(self, e):
        self._drag = False
        if self._dirty:
            self._dirty = False
            self.released.emit()

    def leaveEvent(self, e):
        self._marker = None; self._hover = None
        self.update()

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        l, t, w, h = self._chart()
        right = l + w
        bottom = t + h

        qp.fillRect(0, 0, self.width(), self.height(), QColor(INK2))
        qp.fillRect(l, t, w, h, QColor(INK0))

        hist = self.hist
        if hist is not None and len(hist) == 256 and np.all(np.isfinite(hist)):
            mx = float(hist.max()) or 1.0
            pts = []
            for i in range(256):
                x = l + int(i / 255.0 * w)
                y = bottom - int((float(hist[i]) / mx) * h * 0.9)
                pts.append(QPoint(x, y))
            qp.setPen(QPen(QColor(120, 140, 155, 90), 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            qp.drawPolyline(*pts)

        qp.setPen(QPen(QColor(GRIDC), 1))
        for i in range(1, 4):
            gx = l + int(i / 4.0 * w)
            gy = t + int(i / 4.0 * h)
            qp.drawLine(gx, t, gx, bottom)
            qp.drawLine(l, gy, right, gy)

        qp.setPen(QPen(QColor(LINE2), 1, Qt.DashLine))
        qp.drawLine(self._wx(0), self._wy(0), self._wx(255), self._wy(255))

        if self._marker is not None:
            ix = self._marker
            iy = int(self.model.lut()[ix])
            gx = self._wx(ix); gy = self._wy(iy)
            qp.setPen(QPen(QColor(234, 242, 247, 90), 1, Qt.DotLine))
            qp.drawLine(gx, t, gx, bottom)
            qp.drawLine(l, gy, right, gy)

        lut = self.model.lut()
        col = CH_COLOR.get(self.channel, CH_COLOR["RGB"])
        pts = [QPoint(self._wx(i), self._wy(int(lut[i]))) for i in range(256)]
        glow = QColor(col); glow.setAlpha(55)
        qp.setPen(QPen(glow, 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        qp.drawPolyline(*pts)
        qp.setPen(QPen(col, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        qp.drawPolyline(*pts)

        for i, (px, py) in enumerate(self.model.points):
            cx = self._wx(px); cy = self._wy(py)
            sel = (i == self._sel); hov = (i == self._hover)
            rad = 6 if (sel or hov) else 5
            qp.setPen(Qt.NoPen); qp.setBrush(QColor(0, 0, 0, 110))
            qp.drawEllipse(QPoint(cx, cy), rad + 2, rad + 2)
            if sel:
                qp.setBrush(QColor(255, 255, 255)); qp.setPen(QPen(col, 2))
            else:
                qp.setBrush(col); qp.setPen(QPen(QColor(234, 242, 247), 2))
            qp.drawEllipse(QPoint(cx, cy), rad, rad)

        if self._marker is not None:
            ix = self._marker; iy = int(self.model.lut()[ix])
            qp.setFont(QFont("DejaVu Sans Mono", 8))
            qp.setPen(Qt.NoPen); qp.setBrush(QColor(13, 18, 23, 215))
            qp.drawRoundedRect(l + 5, t + 5, 122, 18, 4, 4)
            qp.setPen(QColor(INKT))
            qp.drawText(l + 5, t + 5, 122, 18, Qt.AlignCenter,
                        tr("curve_io_label", ix=ix, iy=iy))

        gv = QLinearGradient(0, t, 0, bottom)
        gv.setColorAt(0, QColor(238, 242, 247)); gv.setColorAt(1, QColor(8, 11, 14))
        qp.fillRect(0, t, self.GRAD - 2, h, QBrush(gv))
        gh = QLinearGradient(l, 0, right, 0)
        gh.setColorAt(0, QColor(8, 11, 14)); gh.setColorAt(1, QColor(238, 242, 247))
        qp.fillRect(l, bottom + 2, w, self.GRAD - 2, QBrush(gh))

        qp.setPen(QPen(QColor(LINE2), 1)); qp.setBrush(Qt.NoBrush)
        qp.drawRect(l, t, w, h)

    def reset(self):
        self.model.reset(); self._sel = None
        self.changed.emit(); self.update()


# ═══════════════════════════════════════════════════════════════════
#  채널 탭 바
# ═══════════════════════════════════════════════════════════════════
class ChannelBar(QWidget):
    channelChanged = pyqtSignal(str)
    CHS = ["RGB", "Red", "Green", "Blue"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current = "RGB"
        self.setFixedSize(286, 30)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _):
        qp = QPainter(self); qp.setRenderHint(QPainter.Antialiasing)
        qp.setPen(Qt.NoPen); qp.setBrush(QColor(INK0))
        qp.drawRoundedRect(self.rect(), 6, 6)
        w = self.width() / len(self.CHS)
        for i, ch in enumerate(self.CHS):
            cell = QRectF(i * w + 2, 2, w - 4, self.height() - 4)
            col = CH_COLOR[ch]; act = (ch == self.current)
            if act:
                bg = QColor(col); bg.setAlpha(40)
                qp.setPen(Qt.NoPen); qp.setBrush(bg)
                qp.drawRoundedRect(cell, 5, 5)
                qp.setPen(QPen(col, 1.2)); qp.setBrush(Qt.NoBrush)
                qp.drawRoundedRect(cell, 5, 5)
            qp.setPen(col if act else QColor(MUTE))
            qp.setFont(QFont("DejaVu Sans", 9, QFont.Bold if act else QFont.Normal))
            qp.drawText(cell, Qt.AlignCenter, ch)

    def mousePressEvent(self, e):
        w = self.width() / len(self.CHS)
        idx = int(e.x() // w)
        if 0 <= idx < len(self.CHS):
            self.current = self.CHS[idx]
            self.channelChanged.emit(self.current)
            self.update()




class GelView(QWidget):
    laneAdded = pyqtSignal(int, int)
    laneEdgeChanged = pyqtSignal()   # 기존 레인의 x1/x2를 드래그로 조정 완료
    cornerChanged = pyqtSignal(int)
    cropChanged = pyqtSignal(bool)   # 선택 영역 존재 여부
    vrangeChanged = pyqtSignal(bool)  # 세로 분석 범위가 (재)지정/조정 완료
    zoomChanged = pyqtSignal(float)  # 현재 줌 배율(1.0 = 100%)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 420)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._pm = None
        self._img_size = (1, 1)
        self._rect = QRect()
        self.lanes = []
        self.mode = "lane"
        self.show_overlay = True  # 라이브 프리뷰에서 레인/밴드/MW 오버레이 표시 여부
        self.band_display_style = "area"  # "area"(경계 영역) 또는 "line"(피크 위치 한 줄)
        self.selected_band = None  # (lane, band_index) — 결과 표에서 고른 밴드를 캔버스에서 굵게 강조
        self.show_guides = False  # 회전/펴기 보정 중 격자+중앙 십자선 가이드 표시 여부
        self._lane_a = None
        self._lane_b = None
        self._lane_edge_drag = None   # (lane, "x1"|"x2") 레인 경계를 드래그 중일 때
        self._lane_move_drag = None   # (lane, drag_start_wx, orig_x1, orig_x2) 레인 라벨을 잡고 평행이동 중일 때
        self.corners = []
        self._corner_drag = None
        self._box_a = None          # 코너 모드 박스 드래그 시작점(이미지 좌표)
        self._box_b = None          # 코너 모드 박스 드래그 현재점
        self.crop_rect = None       # (x1,y1,x2,y2) 이미지 좌표
        self._crop_a = None
        self._crop_b = None
        # 세로(이동거리) 분석 범위 — (y1,y2) 원본 이미지 행 좌표, None=전체.
        # 레인과 달리 젤 전체에 하나만 둔다(펴기로 이미 직사각형 좌표계라
        # 모든 레인이 같은 세로 기준을 공유하기 때문).
        self.vrange = None
        self._vrange_a = None        # 새 범위를 드래그로 만드는 중일 때 시작 y(이미지 좌표)
        self._vrange_b = None        # 〃 현재 y
        self._vrange_edge_drag = None  # "top" | "bottom" — 기존 줄을 잡고 미세조정 중일 때
        self._zoom = 1.0             # 1.0 = 화면에 맞춤(기본). 휠로 0.2~8.0 범위 조정
        self._pan_x = 0.0            # 확대 상태에서 보이는 영역의 중심 오프셋(이미지 좌표계, px)
        self._pan_y = 0.0
        self._pan_drag = None        # (start_wx, start_wy, start_pan_x, start_pan_y) 중간클릭 드래그 중
        # 표시용으로 스케일한 픽스맵 캐시. paintEvent가 매번 원본 해상도
        # 픽스맵을 SmoothTransformation으로 재스케일하면 팬/레인 드래그처럼
        # 프레임마다 update()가 도는 상황에서 큰 이미지가 심하게 렉이 걸린다.
        # 스케일 결과는 (대상 크기, 보간 모드)에만 의존하므로 그 키가 같으면
        # 재사용한다 — 팬은 _rect 위치만 바꾸고 크기는 그대로라 캐시가 계속
        # 유효하다. 키 형태: ((w, h, mode) -> QPixmap).
        self._scaled_cache = None

    def set_image(self, pm, size):
        self._pm = pm
        self._img_size = size
        self._scaled_cache = None   # 원본 픽스맵이 바뀌었으니 스케일 캐시 무효화
        self._recompute_rect()
        self.update()

    def set_lanes(self, lanes):
        self.lanes = lanes
        self.update()

    def set_mode(self, m):
        self.mode = m
        self._lane_a = self._lane_b = None
        self._lane_edge_drag = None
        self._lane_move_drag = None
        self._vrange_a = self._vrange_b = None
        self._vrange_edge_drag = None
        if m in ("lane", "corner", "crop", "vrange"):
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.OpenHandCursor)  # view 모드: 좌클릭 드래그로 패닝 가능
        self.update()

    def clear_corners(self):
        self.corners = []
        self.update()

    def clear_crop(self):
        self.crop_rect = None
        self._crop_a = self._crop_b = None
        self.cropChanged.emit(False)
        self.update()

    def clear_vrange(self):
        """세로 분석 범위를 지우고 전체 높이로 되돌린다. 신호는 emit하지
        않는다(코너/자르기 초기화와 동일한 패턴) — 호출부가 이미지 교체 등
        다른 초기화와 함께 직접 라벨을 갱신하는 게 자연스러운 경우가
        많아서다."""
        self.vrange = None
        self._vrange_a = self._vrange_b = None
        self._vrange_edge_drag = None
        self.update()

    def _recompute_rect(self):
        if self._pm is None:
            return
        pw, ph = self.width(), self.height()
        iw, ih = self._img_size
        s = min(pw / iw, ph / ih) * self._zoom
        dw, dh = int(iw * s), int(ih * s)
        # 줌 1.0(기본)일 때는 위젯 중앙에 맞추고, 확대 상태에서는 팬 오프셋을
        # 추가로 반영한다. 팬은 이미지 좌표계(px) 단위로 저장하므로 화면
        # 배율(s)을 곱해 위젯 좌표로 변환한다.
        cx = pw / 2 - self._pan_x * s
        cy = ph / 2 - self._pan_y * s
        self._rect = QRect(int(cx - dw / 2), int(cy - dh / 2), dw, dh)

    def _clamp_pan(self):
        """줌이 1.0으로 돌아오거나 이미지가 위젯보다 작아지면 팬을 0으로 리셋.
        과도하게 먼 곳을 패닝해 이미지가 화면 밖으로 완전히 나가는 것도 막는다."""
        if self._zoom <= 1.0001:
            self._pan_x = self._pan_y = 0.0
            return
        iw, ih = self._img_size
        # 패닝 가능한 한계: 이미지 절반 크기 정도까지만 (화면 밖으로 너무 멀리 못 가게)
        self._pan_x = float(np.clip(self._pan_x, -iw / 2, iw / 2))
        self._pan_y = float(np.clip(self._pan_y, -ih / 2, ih / 2))

    def set_zoom(self, zoom, anchor_wx=None, anchor_wy=None):
        """확대/축소를 적용한다. anchor_wx/wy(위젯 좌표)가 주어지면 그 지점이
        화면에서 같은 자리에 머물도록 팬을 같이 보정한다(마우스 휠 줌의 자연스러운 동작)."""
        zoom = float(np.clip(zoom, 0.2, 8.0))
        if anchor_wx is not None and self._pm is not None and self._rect.width() > 0:
            # 줌 전, anchor 위치가 가리키는 이미지 좌표를 구해둔다
            img_x, img_y = self._wpos_to_img(anchor_wx, anchor_wy)
            old_zoom = self._zoom
            self._zoom = zoom
            self._clamp_pan()
            self._recompute_rect()
            # 줌 후 같은 이미지 좌표가 다시 anchor 위치에 오도록 팬을 보정
            new_wx = self._ix_to_wx(img_x); new_wy = self._iy_to_wy(img_y)
            pw, ph = self.width(), self.height()
            iw, ih = self._img_size
            s = min(pw / iw, ph / ih) * self._zoom
            self._pan_x -= (anchor_wx - new_wx) / s
            self._pan_y -= (anchor_wy - new_wy) / s
            self._clamp_pan()
        else:
            self._zoom = zoom
            self._clamp_pan()
        self._recompute_rect()
        self.update()
        self.zoomChanged.emit(self._zoom)

    def reset_zoom(self):
        self._zoom = 1.0
        self._pan_x = self._pan_y = 0.0
        self._recompute_rect()
        self.update()
        self.zoomChanged.emit(self._zoom)

    def wheelEvent(self, e):
        if self._pm is None:
            return
        delta = e.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        pos = e.pos()
        self.set_zoom(self._zoom * factor, pos.x(), pos.y())

    def resizeEvent(self, e):
        self._recompute_rect()

    def _wx_to_ix(self, wx):
        r = self._rect
        if r.width() == 0:
            return 0
        return int(np.clip((wx - r.left()) / r.width() * self._img_size[0], 0, self._img_size[0] - 1))

    def _wpos_to_img(self, wx, wy):
        r = self._rect
        if r.width() == 0 or r.height() == 0:
            return (0.0, 0.0)
        return (float((wx - r.left()) / r.width() * self._img_size[0]),
                float((wy - r.top()) / r.height() * self._img_size[1]))

    def _ix_to_wx(self, ix):
        r = self._rect
        return r.left() + ix / self._img_size[0] * r.width()

    def _iy_to_wy(self, iy):
        r = self._rect
        return r.top() + iy / self._img_size[1] * r.height()

    def _corner_hit(self, wx, wy):
        for i, (ix, iy) in enumerate(self.corners):
            if (wx - self._ix_to_wx(ix)) ** 2 + (wy - self._iy_to_wy(iy)) ** 2 < 14 ** 2:
                return i
        return None

    def _lane_edge_hit(self, wx):
        """레인 경계선(x1 또는 x2) 근처를 클릭했는지 검사. (lane, 'x1'|'x2') 또는 None."""
        TOL = 7  # 위젯 좌표 허용오차(px)
        best = None; best_d = TOL + 1
        for lane in self.lanes:
            for edge in ("x1", "x2"):
                ex = self._ix_to_wx(getattr(lane, edge))
                d = abs(wx - ex)
                if d < best_d:
                    best_d = d; best = (lane, edge)
        return best if best_d <= TOL else None

    def _lane_label_hit(self, wx, wy):
        """레인 이름 라벨(좌상단에 그려지는 텍스트) 영역을 클릭했는지 검사.
        paintEvent에서 그리는 라벨 사각형(QRectF(x1+2, top+2, max(40,폭), 16))과
        동일한 영역을 써서, 보이는 라벨과 클릭 가능 영역이 정확히 일치하게 한다."""
        r = self._rect
        for lane in self.lanes:
            x1 = self._ix_to_wx(lane.x1); x2 = self._ix_to_wx(lane.x2)
            label_rect = QRectF(x1 + 2, r.top() + 2, max(40, x2 - x1), 16)
            if label_rect.contains(QPointF(wx, wy)):
                return lane
        return None

    def _vrange_edge_hit(self, wy):
        """현재 지정된 세로 범위의 위/아래 줄 근처를 클릭했는지 검사.
        ("top"|"bottom") 또는 None. 범위가 아직 없으면 항상 None."""
        if not self.vrange:
            return None
        TOL = 7  # 위젯 좌표 허용오차(px) — 레인 경계 판정과 동일 기준
        top_wy = self._iy_to_wy(self.vrange[0])
        bot_wy = self._iy_to_wy(self.vrange[1])
        if abs(wy - top_wy) <= TOL:
            return "top"
        if abs(wy - bot_wy) <= TOL:
            return "bottom"
        return None

    def mousePressEvent(self, e):
        if self._pm is None:
            return
        if e.button() == Qt.MiddleButton:
            self._pan_drag = (e.x(), e.y(), self._pan_x, self._pan_y)
            self.setCursor(Qt.ClosedHandCursor)
            return
        if e.button() != Qt.LeftButton:
            return
        if self.mode == "corner":
            hit = self._corner_hit(e.x(), e.y())
            if hit is not None:
                self._corner_drag = hit          # 기존 모서리를 끌어 미세 조정
            else:
                # 빈 곳을 누르면 사각형(러버밴드)을 시작 — 떼면 그 사각형의
                # 네 모서리가 코너로 생성된다. 이후 각 모서리를 끌어 맞춘다.
                self._box_a = self._wpos_to_img(e.x(), e.y())
                self._box_b = self._box_a
            return
        if self.mode == "crop":
            self._crop_a = self._wpos_to_img(e.x(), e.y())
            self._crop_b = self._crop_a
            return
        if self.mode == "vrange":
            hit = self._vrange_edge_hit(e.y())
            if hit is not None:
                self._vrange_edge_drag = hit   # 기존 줄을 끌어 미세 조정
            else:
                # 빈 곳을 누르면 위→아래 드래그로 새 범위를 만든다(가로는 항상
                # 이미지 전체 폭 — 세로 범위는 젤 전체에 공통이라 x는 의미 없음).
                self._vrange_a = self._wpos_to_img(e.x(), e.y())[1]
                self._vrange_b = self._vrange_a
            return
        if self.mode == "lane":
            label_lane = self._lane_label_hit(e.x(), e.y())
            if label_lane is not None:
                self._lane_move_drag = (label_lane, self._wx_to_ix(e.x()), label_lane.x1, label_lane.x2)
                return
            hit = self._lane_edge_hit(e.x())
            if hit is not None:
                self._lane_edge_drag = hit
                return
            self._lane_a = self._wx_to_ix(e.x())
            self._lane_b = self._lane_a
            return
        # view 모드(레인/코너/자르기 모두 꺼진 기본 상태)에서는 좌클릭 드래그로도
        # 패닝할 수 있게 한다. 다른 모드는 좌클릭이 이미 다른 용도로 쓰이고 있어
        # 충돌을 피하려고 view 모드에서만 적용한다 (패닝 자체는 중간클릭으로도 가능).
        if self.mode == "view":
            self._pan_drag = (e.x(), e.y(), self._pan_x, self._pan_y)
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self._pan_drag is not None:
            start_wx, start_wy, start_pan_x, start_pan_y = self._pan_drag
            pw, ph = self.width(), self.height()
            iw, ih = self._img_size
            s = min(pw / iw, ph / ih) * self._zoom
            if s > 0:
                self._pan_x = start_pan_x - (e.x() - start_wx) / s
                self._pan_y = start_pan_y - (e.y() - start_wy) / s
                self._clamp_pan()
                self._recompute_rect()
                self.update()
            return
        if self.mode == "vrange" and self._vrange_edge_drag is not None:
            iy = self._wpos_to_img(e.x(), e.y())[1]
            ih = self._img_size[1]
            MIN_GAP = 5  # 위/아래 줄이 너무 가까워져 범위가 사라지지 않게
            top, bot = self.vrange
            if self._vrange_edge_drag == "top":
                top = max(0, min(iy, bot - MIN_GAP))
            else:
                bot = min(ih - 1, max(iy, top + MIN_GAP))
            self.vrange = (top, bot)
            self.update()
            return
        if self.mode == "vrange" and self._vrange_a is not None:
            self._vrange_b = self._wpos_to_img(e.x(), e.y())[1]
            self.update()
            return
        if self.mode == "vrange":
            hit = self._vrange_edge_hit(e.y())
            self.setCursor(Qt.SizeVerCursor if hit is not None else Qt.CrossCursor)
        if self.mode == "lane" and self._lane_move_drag is not None:
            lane, start_wx_img, orig_x1, orig_x2 = self._lane_move_drag
            cur_ix = self._wx_to_ix(e.x())
            delta = cur_ix - start_wx_img
            width = orig_x2 - orig_x1
            img_w = self._img_size[0]
            new_x1 = orig_x1 + delta
            new_x1 = max(0, min(new_x1, img_w - width))  # 이미지 폭 안에서만 이동
            lane.x1 = new_x1
            lane.x2 = new_x1 + width
            self.update()
            return
        if self.mode == "lane" and self._lane_edge_drag is not None:
            lane, edge = self._lane_edge_drag
            ix = self._wx_to_ix(e.x())
            other = lane.x2 if edge == "x1" else lane.x1
            MIN_W = 3
            if edge == "x1":
                ix = min(ix, other - MIN_W)
            else:
                ix = max(ix, other + MIN_W)
            setattr(lane, edge, max(0, ix))
            lane.x1, lane.x2 = min(lane.x1, lane.x2), max(lane.x1, lane.x2)
            self.update()
            return
        if self.mode == "lane" and self._lane_a is None:
            if self._lane_label_hit(e.x(), e.y()) is not None:
                self.setCursor(Qt.OpenHandCursor)
            elif self._lane_edge_hit(e.x()) is not None:
                self.setCursor(Qt.SizeHorCursor)
            else:
                self.setCursor(Qt.CrossCursor)
        if self.mode == "corner" and self._corner_drag is not None:
            self.corners[self._corner_drag] = self._wpos_to_img(e.x(), e.y())
            self.update()
            return
        if self.mode == "corner" and self._box_a is not None:
            self._box_b = self._wpos_to_img(e.x(), e.y())
            self.update()
            return
        if self.mode == "corner":
            self.setCursor(Qt.OpenHandCursor if self._corner_hit(e.x(), e.y()) is not None
                           else Qt.CrossCursor)
        if self.mode == "crop" and self._crop_a is not None:
            self._crop_b = self._wpos_to_img(e.x(), e.y())
            self.update()
        if self.mode == "lane" and self._lane_a is not None:
            self._lane_b = self._wx_to_ix(e.x())
            self.update()

    def mouseReleaseEvent(self, e):
        if self._pan_drag is not None and e.button() in (Qt.MiddleButton, Qt.LeftButton):
            self._pan_drag = None
            self.setCursor(Qt.CrossCursor if self.mode in ("lane", "corner", "crop", "vrange") else Qt.OpenHandCursor)
            return
        if self.mode == "lane" and self._lane_move_drag is not None:
            self._lane_move_drag = None
            self.laneEdgeChanged.emit()
            return
        if self.mode == "lane" and self._lane_edge_drag is not None:
            self._lane_edge_drag = None
            self.laneEdgeChanged.emit()
            return
        if self.mode == "corner" and self._box_a is not None and e.button() == Qt.LeftButton:
            (ax, ay), (bx, by) = self._box_a, self._box_b
            self._box_a = self._box_b = None
            if abs(bx - ax) > 5 and abs(by - ay) > 5:
                x1, y1 = min(ax, bx), min(ay, by)
                x2, y2 = max(ax, bx), max(ay, by)
                self.corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]  # 좌상,우상,우하,좌하
                self.cornerChanged.emit(4)
            self.update()
            return
        if self.mode == "corner" and self._corner_drag is not None:
            self._corner_drag = None
            # 드래그로 옮긴 뒤에도 emit해야 합성 탭 라이브 블렌드처럼 코너
            # '위치'에 반응하는 쪽이 다시 그려진다(개수만 보던 펴기 탭
            # 용도로는 안 보였던 빈틈).
            self.cornerChanged.emit(len(self.corners))
            return
        if self.mode == "crop" and self._crop_a is not None and e.button() == Qt.LeftButton:
            (x1, y1), (x2, y2) = self._crop_a, self._crop_b
            if abs(x2 - x1) > 3 and abs(y2 - y1) > 3:
                self.crop_rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                self.cropChanged.emit(True)
            self._crop_a = self._crop_b = None
            self.update()
            return
        if self.mode == "vrange" and self._vrange_edge_drag is not None:
            self._vrange_edge_drag = None
            self.vrangeChanged.emit(True)
            return
        if self.mode == "vrange" and self._vrange_a is not None and e.button() == Qt.LeftButton:
            a, b = self._vrange_a, self._vrange_b
            self._vrange_a = self._vrange_b = None
            if abs(b - a) > 5:
                ih = self._img_size[1]
                top = max(0, int(round(min(a, b))))
                bot = min(ih - 1, int(round(max(a, b))))
                self.vrange = (top, bot)
                self.vrangeChanged.emit(True)
            self.update()
            return
        if self.mode == "lane" and self._lane_a is not None and e.button() == Qt.LeftButton:
            a, b = self._lane_a, self._lane_b
            if abs(b - a) > 3:
                self.laneAdded.emit(min(a, b), max(a, b))
            self._lane_a = self._lane_b = None
            self.update()

    def _draw_guides(self, qp, r):
        """회전/펴기 보정 중 수평·수직이 맞는지 눈으로 확인하라고 겹쳐
        그리는 격자 + 중앙 십자선. 분석 결과와는 무관한 순수 시각 보조선이라
        저장/내보내기 이미지에는 절대 포함하지 않는다(화면 전용)."""
        grid_pen = QPen(QColor(255, 255, 255, 60), 1)
        qp.setPen(grid_pen)
        for i in range(1, 10):  # 10%마다 격자선(9개)
            x = r.left() + r.width() * i / 10
            qp.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            y = r.top() + r.height() * i / 10
            qp.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
        cross_pen = QPen(QColor(255, 60, 60, 200), 1.5)
        qp.setPen(cross_pen)
        cx = r.left() + r.width() / 2
        cy = r.top() + r.height() / 2
        qp.drawLine(QPointF(cx, r.top()), QPointF(cx, r.bottom()))
        qp.drawLine(QPointF(r.left(), cy), QPointF(r.right(), cy))

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.fillRect(self.rect(), QColor(INK1))

        if self._pm is None:
            qp.setPen(QColor(MUTE)); qp.setFont(QFont("DejaVu Sans", 13))
            qp.drawText(self.rect(), Qt.AlignCenter, tr("canvas_empty_hint"))
            return

        r = self._rect
        # 드래그 중에는 FastTransformation으로 가볍게 그리고(손을 떼면 다음
        # 일반 리페인트에서 Smooth로 한 번만 다시 그려짐), 그 외에는 고품질.
        # 크기·모드가 같으면 캐시된 스케일 픽스맵을 재사용해 재계산을 없앤다.
        dragging = (self._pan_drag is not None or self._lane_edge_drag is not None
                    or self._lane_move_drag is not None or self._corner_drag is not None
                    or self._vrange_edge_drag is not None or self._crop_a is not None)
        mode = Qt.FastTransformation if dragging else Qt.SmoothTransformation
        key = (r.width(), r.height(), mode)
        if self._scaled_cache is None or self._scaled_cache[0] != key:
            self._scaled_cache = (key, self._pm.scaled(r.size(), Qt.KeepAspectRatio, mode))
        qp.drawPixmap(r, self._scaled_cache[1])

        if self.show_guides:
            self._draw_guides(qp, r)

        for lane in self.lanes:
            if not self.show_overlay and self.mode != "lane":
                continue
            x1 = self._ix_to_wx(lane.x1); x2 = self._ix_to_wx(lane.x2)
            col = QColor(lane.color); col.setAlpha(40)
            qp.fillRect(QRectF(x1, r.top(), x2 - x1, r.height()), col)
            col.setAlpha(200); qp.setPen(QPen(col, 1.5))
            qp.drawRect(QRectF(x1, r.top(), x2 - x1, r.height()))
            if self.mode == "lane":
                # 레인 모드에서는 좌우 경계를 드래그 핸들처럼 두껍게 강조
                handle = QPen(QColor(255, 255, 255), 3)
                qp.setPen(handle)
                qp.drawLine(QPointF(x1, r.top()), QPointF(x1, r.bottom()))
                qp.drawLine(QPointF(x2, r.top()), QPointF(x2, r.bottom()))
            if not self.show_overlay:
                continue  # lane 모드에서도 경계만 보이고 라벨/밴드선/MW는 숨김
            if lane.peaks is not None:
                bounds = lane.peak_bounds if lane.peak_bounds else [
                    (max(0, int(py) - 5), int(py) + 5) for py in lane.peaks]
                if self.band_display_style == "line":
                    # 선 모드: 각 피크 위치에 가로 줄 하나만 — 촘촘한 밴드가
                    # 많을 때 영역 박스끼리 겹쳐 보이는 걸 피하고 싶을 때 사용.
                    for j, py in enumerate(lane.peaks):
                        wy = self._iy_to_wy(float(py))
                        is_sel = self.selected_band == (lane, j)
                        qp.setPen(QPen(QColor(lane.color), 4 if is_sel else 2))
                        qp.drawLine(QPointF(x1, wy), QPointF(x2, wy))
                else:
                    for j, (top, bot) in enumerate(bounds):
                        wtop = self._iy_to_wy(float(top)); wbot = self._iy_to_wy(float(bot))
                        is_sel = self.selected_band == (lane, j)
                        band_col = QColor(lane.color); band_col.setAlpha(90 if is_sel else 60)
                        qp.fillRect(QRectF(x1, wtop, x2 - x1, wbot - wtop), band_col)
                        qp.setPen(QPen(QColor(lane.color), 3 if is_sel else 1.4))
                        qp.drawLine(QPointF(x1, wtop), QPointF(x2, wtop))
                        qp.drawLine(QPointF(x1, wbot), QPointF(x2, wbot))
                        if is_sel:
                            # 결과 표에서 고른 밴드 — 위아래뿐 아니라 좌우 경계까지
                            # 굵은 흰 테두리로 감싸서 어느 레인 색이든 눈에 띄게 한다.
                            qp.setPen(QPen(QColor(255, 255, 255), 2))
                            qp.drawRect(QRectF(x1, wtop, x2 - x1, wbot - wtop))

        # 텍스트(레인 제목 + MW)는 모든 레인 박스를 다 그린 뒤 별도 패스로 그린다.
        # 한 루프 안에서 레인마다 박스→글자를 순서대로 그리면, 다음 레인의 박스가
        # 이전 레인의 글자를 덮어버리는 문제가 있어 분리했다.
        if self.show_overlay:
            for lane in self.lanes:
                x1 = self._ix_to_wx(lane.x1); x2 = self._ix_to_wx(lane.x2)
                tag = lane.name
                if lane.kind == "marker": tag += " [M]"
                elif lane.kind == "bsa":  tag += " [BSA]"
                qp.setPen(QColor(lane.color)); qp.setFont(QFont("DejaVu Sans", 8, QFont.Bold))
                name_w = max(40, x2 - x1)
                fm_name = qp.fontMetrics()
                # 레인 이름이 길면 최대 3줄까지 줄바꿈 허용 — 그 이상은 (드물게 아주
                # 긴 이름) 잘린다. 실제로 몇 줄 썼는지 알아야, 아래 MW 라벨 시작
                # 위치를 그 밑으로 밀어 겹침을 막을 수 있다(예: 마커 맨 위 밴드가
                # 250 이상이라 캔버스 맨 위에 가깝게 찍히면 이름과 겹치던 문제).
                natural = fm_name.boundingRect(QRect(0, 0, int(name_w), 10_000),
                                               Qt.TextWordWrap, tag)
                name_h = min(natural.height(), fm_name.lineSpacing() * 3)
                name_rect = QRectF(x1 + 2, r.top() + 2, name_w, name_h)
                qp.drawText(name_rect, Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, tag)
                if lane.peaks is None:
                    continue
                font_mw = QFont("DejaVu Sans Mono", 7, QFont.Bold)
                qp.setFont(font_mw)
                bounds = lane.peak_bounds if lane.peak_bounds else None
                # 첫 MW 라벨이 레인 이름(1~3줄)과 겹치지 않도록, 시작 기준선을
                # 이름 텍스트 바로 아래로 잡아둔다(그 아래 로직이 "직전 라벨보다
                # 11px 이상 아래" 규칙으로 자연스럽게 밀어준다).
                last_ty = r.top() + 2 + name_h + 2 - 11
                for j, py in enumerate(lane.peaks):
                    if j >= len(lane.mw) or lane.mw[j] is None or lane.mw[j] <= 0:
                        continue
                    if self.band_display_style == "line" or not bounds:
                        top_y = py  # 선 모드: 그 줄 바로 위에 라벨
                    else:
                        top_y = bounds[j][0]  # 영역 모드: 경계 위쪽 기준
                    wy = self._iy_to_wy(float(top_y))
                    txt = f"{lane.mw[j]:.1f}"
                    fm = qp.fontMetrics()
                    tw = fm.horizontalAdvance(txt) if hasattr(fm, "horizontalAdvance") else fm.width(txt)
                    tx = x1 + (x2 - x1 - tw) / 2  # 레인 폭 중앙
                    ty = wy - 3                    # 밴드 영역 위쪽 경계선 바로 위
                    # 라벨끼리 너무 가까우면(촘촘한 밴드) 아래로 밀어 글자 겹침 방지
                    if ty < last_ty + 11:
                        ty = last_ty + 11
                    last_ty = ty
                    # 투명 배경 + 검은 외곽선 효과(상하좌우로 살짝 오프셋해 검게 먼저
                    # 그린 뒤 흰 글자를 덮어 그림) — 어떤 밴드 색 위에서도 또렷이 보임
                    qp.setPen(QColor(0, 0, 0))
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        qp.drawText(QPointF(tx + dx, ty + dy), txt)
                    qp.setPen(QColor(255, 255, 255))
                    qp.drawText(QPointF(tx, ty), txt)

        if self.mode == "lane" and self._lane_a is not None and self._lane_b is not None:
            x1 = self._ix_to_wx(min(self._lane_a, self._lane_b))
            x2 = self._ix_to_wx(max(self._lane_a, self._lane_b))
            qp.setPen(QPen(QColor(CYAN), 2, Qt.DashLine))
            qp.setBrush(QColor(63, 180, 230, 35))
            qp.drawRect(QRectF(x1, r.top(), x2 - x1, r.height()))

        # 크롭: 자르기 모드일 때만 표시(다른 모드로 전환해도 어둡게 덮이지 않도록).
        # 선택 영역 자체는 모드를 바꿔도 보존되며, 자르기 모드로 돌아오면 다시 보인다.
        crop_live = (self.mode == "crop" and self._crop_a is not None and self._crop_b is not None)
        if self.mode == "crop" and (crop_live or self.crop_rect):
            if crop_live:
                (ix1, iy1), (ix2, iy2) = self._crop_a, self._crop_b
            else:
                ix1, iy1, ix2, iy2 = self.crop_rect
            x1, y1 = self._ix_to_wx(min(ix1, ix2)), self._iy_to_wy(min(iy1, iy2))
            x2, y2 = self._ix_to_wx(max(ix1, ix2)), self._iy_to_wy(max(iy1, iy2))
            # 선택 영역 밖을 어둡게 덮어 잘릴 영역을 직관적으로 표시
            full = QRectF(r)
            qp.setPen(Qt.NoPen); qp.setBrush(QColor(13, 18, 23, 140))
            qp.drawRect(QRectF(full.left(), full.top(), full.width(), y1 - full.top()))
            qp.drawRect(QRectF(full.left(), y2, full.width(), full.bottom() - y2))
            qp.drawRect(QRectF(full.left(), y1, x1 - full.left(), y2 - y1))
            qp.drawRect(QRectF(x2, y1, full.right() - x2, y2 - y1))
            qp.setPen(QPen(QColor(LIME), 2, Qt.DashLine if crop_live else Qt.SolidLine))
            qp.setBrush(Qt.NoBrush)
            qp.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))
            qp.setPen(QColor(LIME)); qp.setFont(QFont("DejaVu Sans Mono", 8, QFont.Bold))
            w_img = abs(ix2 - ix1); h_img = abs(iy2 - iy1)
            qp.drawText(QRectF(x1, max(0, y1 - 16), 130, 16), Qt.AlignLeft,
                        f"{w_img:.0f}×{h_img:.0f}px")

        # 세로 분석 범위: 범위 지정 모드일 때만 표시(자르기와 동일한 관례).
        # 다른 모드에서는 검출된 밴드 자체가 이미 이 범위 안에서만 나타나므로
        # 굳이 항상 겹쳐 그릴 필요가 없다.
        vrange_live = (self.mode == "vrange" and self._vrange_a is not None and self._vrange_b is not None)
        if self.mode == "vrange" and (vrange_live or self.vrange):
            iy1, iy2 = (self._vrange_a, self._vrange_b) if vrange_live else self.vrange
            y1, y2 = self._iy_to_wy(min(iy1, iy2)), self._iy_to_wy(max(iy1, iy2))
            full = QRectF(r)
            qp.setPen(Qt.NoPen); qp.setBrush(QColor(13, 18, 23, 140))
            qp.drawRect(QRectF(full.left(), full.top(), full.width(), y1 - full.top()))
            qp.drawRect(QRectF(full.left(), y2, full.width(), full.bottom() - y2))
            qp.setPen(QPen(QColor(LIME), 2, Qt.DashLine if vrange_live else Qt.SolidLine))
            qp.setBrush(Qt.NoBrush)
            qp.drawLine(QPointF(full.left(), y1), QPointF(full.right(), y1))
            qp.drawLine(QPointF(full.left(), y2), QPointF(full.right(), y2))
            qp.setPen(QColor(LIME)); qp.setFont(QFont("DejaVu Sans Mono", 8, QFont.Bold))
            h_img = abs(iy2 - iy1)
            qp.drawText(QRectF(full.left() + 4, max(0, y1 - 16), 130, 16), Qt.AlignLeft,
                        f"{h_img:.0f}px")

        if self.mode == "corner" and self._box_a is not None and self._box_b is not None:
            (ax, ay), (bx, by) = self._box_a, self._box_b
            bx1, by1 = self._ix_to_wx(min(ax, bx)), self._iy_to_wy(min(ay, by))
            bx2, by2 = self._ix_to_wx(max(ax, bx)), self._iy_to_wy(max(ay, by))
            qp.setPen(QPen(QColor(CYAN), 2, Qt.DashLine)); qp.setBrush(QColor(63, 180, 230, 35))
            qp.drawRect(QRectF(bx1, by1, bx2 - bx1, by2 - by1))

        if self.corners:
            wpts = [QPointF(self._ix_to_wx(ix), self._iy_to_wy(iy)) for ix, iy in self.corners]
            if len(wpts) == 4:
                qp.setPen(Qt.NoPen); qp.setBrush(QColor(63, 180, 230, 45))
                qp.drawPolygon(QPolygonF(wpts))
            if len(wpts) >= 2:
                qp.setPen(QPen(QColor(CYAN), 2))
                for i in range(len(wpts) - 1):
                    qp.drawLine(wpts[i], wpts[i + 1])
                if len(wpts) == 4:
                    qp.drawLine(wpts[3], wpts[0])
            names = [tr("corner_name_tl"), tr("corner_name_tr"), tr("corner_name_br"), tr("corner_name_bl")]
            for i, wp in enumerate(wpts):
                qp.setPen(QPen(QColor(255, 255, 255), 2)); qp.setBrush(QColor(CYAN))
                qp.drawEllipse(wp, 6, 6)
                qp.setFont(QFont("DejaVu Sans", 8, QFont.Bold))
                lx = wp.x() + 9; ly = wp.y() - 20
                if ly < r.top(): ly = wp.y() + 6
                if lx + 50 > r.right(): lx = wp.x() - 56
                chip = QRectF(lx, ly, 50, 17)
                qp.setPen(Qt.NoPen); qp.setBrush(QColor(13, 18, 23, 230))
                qp.drawRoundedRect(chip, 4, 4)
                qp.setPen(QColor(CYAN)); qp.drawText(chip, Qt.AlignCenter, names[i])

        qp.setPen(QPen(QColor(LINE), 1)); qp.setBrush(Qt.NoBrush); qp.drawRect(r)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            # load_image()로 직접 부르면 확장자를 안 가려 .bandwagon/.bwcomposite를
            # 끌어놔도 무조건 그림으로 열려던 문제가 있었다 — open_path_smart()를
            # 거쳐야 다른 진입점(메뉴/파일 연결)과 똑같이 확장자별로 분기되고
            # "최근 파일" 목록에도 기록된다.
            self.window().open_path_smart(urls[0].toLocalFile())


class ThumbView(QWidget):
    """작은 정사각형 썸네일 — 가시광/UV 원본을 클릭으로 확인하는 용도.
    폭이 고정돼 있어(setFixedSize) 좁은 좌측 패널 안에서 가로 스크롤을
    유발하지 않는다. 클릭하면 clicked 시그널을 보내 호출자가 원본을 큰
    다이얼로그로 띄우게 한다(실제 다이얼로그 표시는 Analyzer 쪽 책임)."""
    clicked = pyqtSignal()

    def __init__(self, side=96, parent=None):
        super().__init__(parent)
        self._side = side
        self.setFixedSize(side, side)
        self.setCursor(Qt.PointingHandCursor)
        self._img = None

    def set_image(self, pil_img):
        self._img = pil_img.convert("RGB") if pil_img else None
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.fillRect(self.rect(), QColor(INK3))
        qp.setPen(QPen(QColor(LINE), 1))
        qp.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if self._img is None:
            qp.setPen(QColor(MUTE)); qp.setFont(QFont("DejaVu Sans", 8))
            qp.drawText(self.rect(), Qt.AlignCenter, tr("wb_thumb_empty"))
            return
        pm = pil_to_pixmap(self._img).scaled(
            self._side - 4, self._side - 4, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (self.width() - pm.width()) // 2
        y = (self.height() - pm.height()) // 2
        qp.drawPixmap(x, y, pm)


class ProfileView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._lanes = []

    def set_lanes(self, lanes):
        self._lanes = [l for l in lanes if l.profile is not None]
        self.update()

    def paintEvent(self, _):
        qp = QPainter(self); qp.setRenderHint(QPainter.Antialiasing)
        qp.setPen(Qt.NoPen); qp.setBrush(QColor(INK2))
        qp.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 8, 8)
        qp.setPen(QColor(MUTE)); qp.setFont(QFont("DejaVu Sans", 9, QFont.Bold))
        qp.drawText(QRectF(14, 8, self.width() - 28, 16), Qt.AlignLeft, tr("profile_title"))

        if not self._lanes:
            qp.setPen(QColor(MUTE)); qp.setFont(QFont("DejaVu Sans", 10))
            qp.drawText(self.rect(), Qt.AlignCenter, tr("profile_empty_hint"))
            return

        pl, pt, pr, pb = 22, 28, 14, 16
        x0, y0 = pl, pt
        w = self.width() - pl - pr; h = self.height() - pt - pb
        n = len(self._lanes[0].profile)
        amax = max(l.profile.max() for l in self._lanes) or 1

        qp.setPen(QPen(QColor(GRIDC), 1))
        for i in range(1, 4):
            yy = y0 + i / 4 * h
            qp.drawLine(QPointF(x0, yy), QPointF(x0 + w, yy))

        for lane in self._lanes:
            col = QColor(lane.color); col.setAlpha(220)
            path = QPainterPath()
            for i, v in enumerate(lane.profile):
                x = x0 + i / n * w; y = y0 + h - (v / amax) * h
                path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
            qp.setPen(QPen(col, 1.5)); qp.drawPath(path)
            if lane.peaks is not None:
                for py in lane.peaks:
                    px = x0 + py / n * w; pv = y0 + h - (lane.profile[py] / amax) * h
                    qp.setPen(QPen(QColor(INK1), 1)); qp.setBrush(col)
                    qp.drawEllipse(QPointF(px, pv), 3, 3)

        qp.setPen(QPen(QColor(LINE2), 1))
        qp.drawLine(QPointF(x0, y0), QPointF(x0, y0 + h))
        qp.drawLine(QPointF(x0, y0 + h), QPointF(x0 + w, y0 + h))


# ═══════════════════════════════════════════════════════════════════
#  표준곡선 뷰
# ═══════════════════════════════════════════════════════════════════
class StdCurveView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self._xy = None; self._slope = 0; self._icept = 0; self._r2 = 0

    def set_fit(self, xs, ys, slope, icept, r2):
        self._xy = (xs, ys); self._slope = slope; self._icept = icept; self._r2 = r2
        self.update()

    def clear(self):
        self._xy = None; self.update()

    def paintEvent(self, _):
        qp = QPainter(self); qp.setRenderHint(QPainter.Antialiasing)
        qp.setPen(Qt.NoPen); qp.setBrush(QColor(INK2))
        qp.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 8, 8)
        if self._xy is None:
            qp.setPen(QColor(MUTE)); qp.setFont(QFont("DejaVu Sans", 10))
            qp.drawText(self.rect(), Qt.AlignCenter, tr("std_curve_empty_hint"))
            return
        pad = 34
        w = self.width() - 2 * pad; h = self.height() - 2 * pad
        xs, ys = self._xy
        xmin, xmax = min(xs), max(xs); ymin, ymax = min(ys), max(ys)
        if xmax == xmin: xmax = xmin + 1
        if ymax == ymin: ymax = ymin + 1
        def tx(v): return pad + (v - xmin) / (xmax - xmin) * w
        def ty(v): return pad + h - (v - ymin) / (ymax - ymin) * h

        qp.setPen(QPen(QColor(GRIDC), 1))
        for i in range(5):
            f = i / 4
            qp.drawLine(int(pad + f * w), pad, int(pad + f * w), pad + h)
            qp.drawLine(pad, int(pad + f * h), pad + w, int(pad + f * h))

        rx = np.linspace(xmin, xmax, 80); ry = self._slope * rx + self._icept
        path = QPainterPath()
        for i, (a, b) in enumerate(zip(rx, ry)):
            p = QPointF(tx(a), ty(b))
            path.moveTo(p) if i == 0 else path.lineTo(p)
        qp.setPen(QPen(QColor(CYAN), 1.8)); qp.drawPath(path)

        for a, b in zip(xs, ys):
            qp.setPen(QPen(QColor(INK1), 1.5)); qp.setBrush(QColor(LIME))
            qp.drawEllipse(QPointF(tx(a), ty(b)), 4.5, 4.5)

        qp.setPen(QPen(QColor(LINE2), 1))
        qp.drawLine(pad, pad, pad, pad + h)
        qp.drawLine(pad, pad + h, pad + w, pad + h)
        qp.setPen(QColor(LIME)); qp.setFont(QFont("DejaVu Sans Mono", 9, QFont.Bold))
        qp.drawText(QRectF(pad, 6, w, 16), Qt.AlignRight, f"R\u00b2 = {self._r2:.4f}")
        qp.setPen(QColor(MUTE)); qp.setFont(QFont("DejaVu Sans", 8))
        qp.drawText(QRectF(pad, pad + h + 4, w, 14), Qt.AlignCenter, "Band volume")


# ═══════════════════════════════════════════════════════════════════
#  슬라이더 행
# ═══════════════════════════════════════════════════════════════════
class SliderRow(QWidget):
    valueChanged = pyqtSignal(int)
    released = pyqtSignal()   # 슬라이더를 놓은 시점 — 되돌리기 커밋 지점으로 씀

    def __init__(self, label, lo, hi, default, parent=None):
        super().__init__(parent)
        self._default = default
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(8)
        lb = QLabel(label); lb.setFixedWidth(34); lb.setStyleSheet(f"color:{MUTE};font-size:11px;")
        lay.addWidget(lb)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(lo, hi); self.slider.setValue(default)
        self.slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{INK3};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:14px;height:14px;margin:-6px 0;"
            f"background:{INKT};border:2px solid {CYAN};border-radius:8px;}}"
            f"QSlider::handle:horizontal:hover{{background:{CYAN};}}"
            f"QSlider::sub-page:horizontal{{background:{CYAN};border-radius:2px;}}")
        lay.addWidget(self.slider, 1)
        self.val = QLabel(str(default)); self.val.setFixedWidth(34)
        self.val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.val.setStyleSheet(f"color:{INKT};font-size:11px;font-family:'DejaVu Sans Mono';")
        lay.addWidget(self.val)
        self.slider.valueChanged.connect(self._on)
        self.slider.sliderReleased.connect(self.released.emit)

    def _on(self, v):
        self.val.setText(str(v)); self.valueChanged.emit(v)

    def setValue(self, v): self.slider.setValue(v)
    def value(self): return self.slider.value()


# ═══════════════════════════════════════════════════════════════════
#  마커 MW 입력 다이얼로그
