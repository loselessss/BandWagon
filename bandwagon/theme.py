"""bandwagon.theme

디자인 토큰(색상)과 채널/레인 팔레트.

(BandWagon v1.1을 모듈로 분할한 것 — 동작은 원본과 동일.)
"""
from PyQt5.QtGui import QColor

__all__ = [
    "INK0", "INK1", "INK2", "INK3", "INK4", "CYAN", "ROSE", "LIME",
    "INKT", "MUTE", "LINE", "LINE2", "GRIDC", "CH_COLOR", "LANE_PALETTE",
]

# ── 디자인 토큰 (실험실 계측기: 슬레이트 배경 + 시안 액센트) ────────
INK0 = "#0d1217"
INK1 = "#121922"
INK2 = "#19222d"
INK3 = "#23303d"
INK4 = "#314250"
CYAN = "#3fb4e6"
ROSE = "#f4737f"
LIME = "#5ad19a"
INKT = "#eaf2f7"
MUTE = "#7f93a3"
LINE = "#28333f"
LINE2 = "#415262"
GRIDC = "#1f2a35"

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
