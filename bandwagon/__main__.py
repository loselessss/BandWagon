"""bandwagon.__main__

진입점: HiDPI 설정 → 스플래시 → Analyzer 생성. `python -m bandwagon`.

(BandWagon v1.1을 모듈로 분할한 것 — 동작은 원본과 동일.)
"""
import sys, os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFileDialog, QSlider, QGroupBox, QStatusBar,
    QToolBar, QAction, QSizePolicy, QMessageBox, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget, QSpinBox, QDoubleSpinBox,
    QComboBox, QInputDialog, QDialog, QDialogButtonBox, QFormLayout,
    QScrollArea, QCheckBox,
)
from PyQt5.QtCore import Qt, QPoint, QPointF, QRectF, QRect, QSize, pyqtSignal, QTimer, QStandardPaths

from .meta import APP_NAME
from .app import Analyzer


def _install_crash_logger():
    """요청#4: 언제 어디서 터지는지 추적할 수 있게, 처리되지 않은 예외를
    홈 폴더의 bandwagon_crash.log 파일에 계속(append) 기록한다. 런처가 띄우는
    오류 팝업과는 별개로, 닫고 나서도 원인을 다시 확인할 수 있게 남겨둔다."""
    import traceback, datetime
    log_path = os.path.join(os.path.expanduser("~"), "bandwagon_crash.log")

    def _hook(exc_type, exc_value, exc_tb):
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("\n===== %s =====\n" % datetime.datetime.now().isoformat())
                traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        except Exception:
            pass  # 로그 기록 실패가 다시 예외를 던지지 않도록
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


def main():
    _install_crash_logger()
    # ── HiDPI(4K 등 고해상도 모니터) 지원 ──────────────────────────────
    # QApplication을 만들기 *전에* 설정해야 적용된다. 이 두 속성을 켜면 Qt가
    # OS의 디스플레이 배율(예: Windows 디스플레이 설정의 150%/200%)을 읽어서
    # 창 전체(폰트·아이콘·여백 포함)를 그 배율만큼 자동으로 키워준다.
    # AA_EnableHighDpiScaling: 레이아웃 좌표·폭/높이값을 배율에 맞게 스케일링
    # AA_UseHighDpiPixmaps: 아이콘/픽스맵도 흐려지지 않게 고해상도로 렌더링
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # 배율을 정수 단위(100%/200%)로만 반올림하지 않고 그 사이 값(125%, 150%
    # 등)도 그대로 따르게 한다 — 안 하면 Qt 5 일부 버전은 가장 가까운 정수
    # 배율로 강제 스냅해 4K 모니터에서 글자가 들쭉날쭉해질 수 있다.
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")

    # ── 부팅 스플래시 ──────────────────────────────────────────────
    # 개발 중(.py로 직접 실행)에는 스플래시를 띄우지 않는다. 스플래시는
    # PyInstaller로 만든 실행파일에서만 뜬다 — 빌드 시 --splash 로 넣은 PNG를
    # PyInstaller 네이티브 스플래시가 파이썬/Qt가 로드되기도 '전에' 즉시 띄우고,
    # 메인 창이 준비되면 여기서 닫는다(그래서 "스플래시가 늦게 뜨는" 문제도 없다).
    win = Analyzer(sys.argv[1] if len(sys.argv) > 1 else None, splash=None)
    win.show()
    try:
        import pyi_splash            # PyInstaller 번들 안에서만 존재하는 모듈
        pyi_splash.close()
    except Exception:
        pass                          # 번들이 아니면(개발 실행 등) 그냥 넘어감
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
