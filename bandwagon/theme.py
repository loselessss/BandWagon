"""bandwagon.theme

디자인 토큰(색상)과 채널/레인 팔레트.

(BandWagon v1.1을 모듈로 분할한 것 — 동작은 원본과 동일.)
"""
from PyQt5.QtGui import QColor

__all__ = [
    "INK0", "INK1", "INK2", "INK3", "INK4", "CYAN", "ROSE", "LIME",
    "INKT", "MUTE", "LINE", "LINE2", "GRIDC", "CH_COLOR", "LANE_PALETTE",
]

# ── Fluent 스타일: 중립 다크 표면 + 밝은 파란색 강조 ───────────────
INK0 = "#191919"
INK1 = "#202020"
INK2 = "#272727"
INK3 = "#323232"
INK4 = "#3d3d3d"
CYAN = "#60cdff"
ROSE = "#f4737f"
LIME = "#5ad19a"
INKT = "#f3f3f3"
MUTE = "#b0b0b0"
LINE = "#383838"
LINE2 = "#606060"
GRIDC = "#303030"

CH_COLOR = {
    "RGB":   QColor(238, 242, 247),
    "Red":   QColor(244, 115, 127),
    "Green": QColor(90, 209, 154),
    "Blue":  QColor(63, 180, 230),
}

LANE_PALETTE = [
    QColor(63, 180, 230), QColor(244, 115, 127), QColor(90, 209, 154),
    QColor(240, 190, 90), QColor(180, 140, 240), QColor(80, 200, 200),
    QColor(240, 150, 90), QColor(150, 210, 90),
]
