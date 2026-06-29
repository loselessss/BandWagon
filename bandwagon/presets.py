"""bandwagon.presets

마커(분자량 사다리) 프리셋 로드/저장/기본값.

(BandWagon v1.1을 모듈로 분할한 것 — 동작은 원본과 동일.)
"""
import os, json
from pathlib import Path
from . import i18n


def _default_marker_presets():
    """최초 실행 시 자동 생성되는 기본 프리셋. 현재 언어(CURRENT_LANG)에 맞춰
    이름을 짓는다 — 사용자가 나중에 직접 바꾼 이름은 그대로 보존되므로,
    이 함수는 '파일이 아직 없을 때 1회'만 영향을 준다."""
    name = "기본 11밴드 (250–10 kDa)" if i18n.CURRENT_LANG == "ko" else "Default 11-band (250–10 kDa)"
    return [{"name": name, "mw": [250, 180, 130, 95, 70, 56, 43, 35, 28, 17, 10]}]

_MARKER_PRESET_PATH = Path(os.path.expanduser("~")) / ".bandwagon_markers.json"


def load_marker_presets():
    """저장된 프리셋 파일을 읽어온다. 없거나 손상됐으면 기본 프리셋으로 새로 만든다."""
    if _MARKER_PRESET_PATH.exists():
        try:
            data = json.loads(_MARKER_PRESET_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list) and all("name" in p and "mw" in p for p in data):
                return data
        except Exception:
            pass
    defaults = _default_marker_presets()
    save_marker_presets(defaults)
    return [dict(p) for p in defaults]


def save_marker_presets(presets):
    try:
        _MARKER_PRESET_PATH.write_text(json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # 저장 실패해도(권한 등) 앱 동작에는 영향 없음


