"""bandwagon.meta

릴리스 메타데이터, cv2 설치여부 플래그, 소스 무결성 해시.

(BandWagon v1.1을 모듈로 분할한 것 — 동작은 원본과 동일.)
"""
import sys, os, importlib.util


HAS_CV2 = importlib.util.find_spec("cv2") is not None

# ── 릴리스 메타데이터 ────────────────────────────────────────────────
APP_NAME     = "BandWagon"
APP_VERSION  = "1.3.1"
RELEASE_DATE = "2026-07-06"
GELPROJ_FORMAT_VERSION = 1   # .bandwagon 내부 JSON 스키마 버전 (구조 바꾸면 올릴 것)

def _source_audit():
    """실행 중인 산출물의 SHA-256 지문을 반환한다(앞자리만 표시용).
    배포본을 받은 사람이 '정보' 창의 값과 원본 해시를 대조해, 코드/실행파일이
    변조·손상되지 않았는지 검증(audit)할 수 있게 한다.
      - 그냥 .pyw로 실행:  그 스크립트 파일을 해싱 → 소스 지문
      - PyInstaller exe:   실행 파일(sys.executable)을 해싱 → 빌드 지문
    어떤 이유로든 해싱이 안 되면 'unavailable'을 돌려준다(기능엔 영향 없음)."""
    try:
        import hashlib
        target = sys.executable if getattr(sys, "frozen", False) \
                 else os.path.abspath(__file__)
        with open(target, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return "unavailable"
