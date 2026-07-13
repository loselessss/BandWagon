"""bandwagon.presets

마커(분자량 사다리) 프리셋 로드/저장/기본값.

(BandWagon v1.1을 모듈로 분할한 것 — 동작은 원본과 동일.)
"""
import os, json, csv
from pathlib import Path
from . import i18n


def _default_marker_presets():
    """최초 실행 시 자동 생성되는 기본 프리셋. 현재 언어(CURRENT_LANG)에 맞춰
    이름을 짓는다 — 사용자가 나중에 직접 바꾼 이름은 그대로 보존되므로,
    이 함수는 '파일이 아직 없을 때 1회'만 영향을 준다(그 이후엔
    load_marker_presets()가 이름으로 대조해 누락된 것만 추가로 채워준다).

    DNA 사다리 3종(1kb/100bp/λ-HindIII)은 실험실에서 흔히 쓰는 표준 참고값
    이지만, 제조사·카탈로그 번호에 따라 밴드 크기가 조금씩 다를 수 있으니
    정밀한 정량이 필요하면 실제 제품 설명서 값으로 바꿔 쓰는 걸 권장한다.
    기존 "기본 11밴드" 단백질 프리셋 이름은 바꾸지 않는다 — 이름이 바뀌면
    이미 이 프리셋을 쓰던 사용자에게 중복으로 다시 추가돼 버린다."""
    protein_name = "기본 11밴드 (250–10 kDa)" if i18n.CURRENT_LANG == "ko" else "Default 11-band (250–10 kDa)"
    protein = {"name": protein_name, "mw": [250, 180, 130, 95, 70, 56, 43, 35, 28, 17, 10]}
    if i18n.CURRENT_LANG == "ko":
        dna = [
            {"name": "1kb DNA 사다리 (NEB N3232, 10,000–500 bp)",
             "mw": [10000, 8000, 6000, 5000, 4000, 3000, 2000, 1500, 1000, 500]},
            {"name": "100bp DNA 사다리 (NEB N3231, 1500–100 bp)",
             "mw": [1500, 1200, 1000, 900, 800, 700, 600, 500, 400, 300, 200, 100]},
            {"name": "범용 DNA 마커 (λ/HindIII, 23130–125 bp)",
             "mw": [23130, 9416, 6557, 4361, 2322, 2027, 564, 125]},
        ]
    else:
        dna = [
            {"name": "1kb DNA Ladder (NEB N3232, 10,000–500 bp)",
             "mw": [10000, 8000, 6000, 5000, 4000, 3000, 2000, 1500, 1000, 500]},
            {"name": "100bp DNA Ladder (NEB N3231, 1500–100 bp)",
             "mw": [1500, 1200, 1000, 900, 800, 700, 600, 500, 400, 300, 200, 100]},
            {"name": "General DNA Marker (λ/HindIII, 23130–125 bp)",
             "mw": [23130, 9416, 6557, 4361, 2322, 2027, 564, 125]},
        ]
    return [protein] + dna

_MARKER_PRESET_PATH = Path(os.path.expanduser("~")) / ".bandwagon_markers.json"


def load_marker_presets():
    """저장된 프리셋 파일을 읽어온다. 없거나 손상됐으면 기본 프리셋으로 새로
    만든다. 파일이 있으면, 이름 기준으로 아직 없는 기본 프리셋만 채워
    넣는다(예: 이전 버전에서 만든 파일에 DNA 사다리 프리셋을 나중에
    추가하는 경우) — 사용자가 직접 추가/수정/삭제한 프리셋은 건드리지 않는다."""
    if _MARKER_PRESET_PATH.exists():
        try:
            data = json.loads(_MARKER_PRESET_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list) and all("name" in p and "mw" in p for p in data):
                names = {p["name"] for p in data}
                missing = [dict(d) for d in _default_marker_presets() if d["name"] not in names]
                if missing:
                    data = data + missing
                    save_marker_presets(data)
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


def export_marker_presets_csv(path, presets):
    """프리셋 하나당 한 줄(이름, MW...)로 CSV에 쓴다. 밴드 개수가 프리셋마다
    달라도 되므로 헤더 없이 가변 길이 행으로 저장한다. utf-8-sig(BOM)를 쓰는
    이유는 한글 이름이 든 CSV를 엑셀에서 열었을 때 깨지지 않게 하기 위함."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        for p in presets:
            writer.writerow([p["name"]] + [f"{v:g}" for v in p["mw"]])


def import_marker_presets_csv(path):
    """export_marker_presets_csv가 쓴 형식(이름, MW...)을 읽는다. 숫자가 아닌
    칸은 조용히 건너뛴다 — 사람이 엑셀에서 손으로 수정하다 생기는 실수를
    파일 전체 실패로 만들지 않기 위해."""
    presets = []
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip():
                continue
            mw = []
            for cell in row[1:]:
                cell = cell.strip()
                if not cell:
                    continue
                try:
                    mw.append(float(cell))
                except ValueError:
                    pass
            if mw:
                presets.append({"name": row[0].strip(), "mw": mw})
    return presets


