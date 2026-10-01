"""Theme-independent check marks, including packaged Windows builds."""
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QColor, QPainter, QPen, QPainterPath
from PyQt5.QtWidgets import QCheckBox, QStyle, QStyleOptionButton


class TickCheckBox(QCheckBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isChecked():
            return
        option = QStyleOptionButton()
        self.initStyleOption(option)
        rect = self.style().subElementRect(QStyle.SE_CheckBoxIndicator, option, self)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#ffffff"), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        path = QPainterPath()
        path.moveTo(QPointF(rect.x() + rect.width() * .23, rect.y() + rect.height() * .52))
        path.lineTo(QPointF(rect.x() + rect.width() * .43, rect.y() + rect.height() * .73))
        path.lineTo(QPointF(rect.x() + rect.width() * .79, rect.y() + rect.height() * .28))
        painter.drawPath(path)
