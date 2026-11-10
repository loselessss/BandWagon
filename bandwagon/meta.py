"""bandwagon.meta

릴리스 메타데이터, cv2 설치여부 플래그.

(BandWagon v1.1을 모듈로 분할한 것 — 동작은 원본과 동일.)
"""
import sys, os, importlib.util


HAS_CV2 = importlib.util.find_spec("cv2") is not None

# ── 릴리스 메타데이터 ────────────────────────────────────────────────
APP_NAME     = "BandWagon"
APP_VERSION  = "2.11.0"
RELEASE_DATE = "2026-11-09"
PRIVACY_POLICY_URL = "https://loselessss.github.io/BandWagon/privacy/"
GELPROJ_FORMAT_VERSION = 3   # v3: 정량용 원본 및 기하변환 기록. v2: memo 필드.

def resource_path(name):
    """빌드/개발 양쪽에서 저장소 루트에 있는 리소스 파일(예: bandwagon.ico)을
    찾는다. 프로즌(exe) 상태면 PyInstaller가 풀어둔 임시 폴더(_MEIPASS)를,
    개발 중이면 이 파일(bandwagon/meta.py)의 부모의 부모, 즉 저장소 루트를
    기준으로 삼는다."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)
