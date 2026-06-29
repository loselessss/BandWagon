"""bandwagon.models

CurveModel(톤커브)과 Lane(레인/밴드 분석). scipy는 지연 로딩.

(BandWagon v1.1을 모듈로 분할한 것 — 동작은 원본과 동일.)
"""
import numpy as np
from .theme import LANE_PALETTE


class CurveModel:
    def __init__(self):
        self.points = [(0, 0), (255, 255)]
        self._lut = np.arange(256, dtype=np.uint8)

    def reset(self):
        self.points = [(0, 0), (255, 255)]
        self._lut = np.arange(256, dtype=np.uint8)

    def add_point(self, x, y):
        x, y = int(np.clip(x, 0, 255)), int(np.clip(y, 0, 255))
        for i, (px, _) in enumerate(self.points):
            if abs(px - x) <= 3:
                self.points[i] = (x, y)
                self._rebuild()
                return self._index_of(x)
        self.points.append((x, y))
        self._rebuild()
        return self._index_of(x)

    def move_point(self, idx, x, y):
        x, y = int(np.clip(x, 0, 255)), int(np.clip(y, 0, 255))
        old_x = self.points[idx][0]
        if idx == 0 and old_x == 0:
            x = 0
        elif idx == len(self.points) - 1 and old_x == 255:
            x = 255
        else:
            if idx > 0:
                x = max(x, self.points[idx - 1][0] + 1)
            if idx < len(self.points) - 1:
                x = min(x, self.points[idx + 1][0] - 1)
        self.points[idx] = (x, y)
        self._rebuild()
        return x

    def remove_point(self, idx):
        if len(self.points) <= 2:
            return
        if self.points[idx][0] in (0, 255):
            return
        self.points.pop(idx)
        self._rebuild()

    def lut(self):
        return self._lut

    def to_dict(self):
        return {"points": [[int(x), int(y)] for x, y in self.points]}

    @classmethod
    def from_dict(cls, d):
        m = cls()
        pts = d.get("points") or [(0, 0), (255, 255)]
        m.points = [(int(x), int(y)) for x, y in pts]
        m._rebuild()
        return m

    def _index_of(self, x):
        for i, (px, _) in enumerate(self.points):
            if px == x:
                return i
        return 0

    def _rebuild(self):
        self.points.sort(key=lambda p: p[0])
        xs = np.array([p[0] for p in self.points], float)
        ys = np.array([p[1] for p in self.points], float)
        xi = np.arange(256, dtype=float)
        if len(xs) <= 2:
            yi = np.interp(xi, xs, ys)
        else:
            try:
                from scipy.interpolate import PchipInterpolator
                yi = PchipInterpolator(xs, ys)(xi)
            except Exception:
                yi = np.interp(xi, xs, ys)
        self._lut = np.clip(np.round(yi), 0, 255).astype(np.uint8)




class Lane:
    def __init__(self, idx, x1, x2):
        self.idx = idx
        self.x1, self.x2 = min(x1, x2), max(x1, x2)
        self.name = f"Lane {idx + 1}"
        self.kind = "sample"
        self.marker_mw = []
        self.bsa_amount = 0.0
        self.profile = None
        self.peaks = None
        self.peak_area = None       # 밴드별 면적(강도 적분)
        self.peak_volume = None     # 밴드별 부피(면적×레인폭)
        self.peak_prom = None       # 밴드별 prominence
        self.peak_bounds = None     # 밴드별 (위경계_y, 아래경계_y) — 오버레이에 영역으로 표시
        self.n_smear = 0            # 이번 analyze()에서 smear로 판정돼 제외된 피크 수
        self.mw = []

    @property
    def color(self):
        return LANE_PALETTE[self.idx % len(LANE_PALETTE)]

    def to_dict(self):
        """프로젝트 저장용 — 분석 '입력'만 저장한다(검출 결과는 저장 안 함).
        불러온 뒤 run_analysis()를 다시 돌리면 같은 입력에서 100% 동일한
        결과가 나오므로 numpy 배열을 JSON에 끼워 넣을 필요가 없다."""
        return {
            "idx": self.idx, "x1": self.x1, "x2": self.x2,
            "name": self.name, "kind": self.kind,
            "marker_mw": list(self.marker_mw), "bsa_amount": self.bsa_amount,
        }

    @classmethod
    def from_dict(cls, d):
        lane = cls(d["idx"], d["x1"], d["x2"])
        lane.name = d.get("name", lane.name)
        lane.kind = d.get("kind", "sample")
        lane.marker_mw = list(d.get("marker_mw", []))
        lane.bsa_amount = float(d.get("bsa_amount", 0.0))
        return lane

    def analyze(self, gray_orig, prominence, distance, threshold_pct=40,
                y_top=None, y_bot=None, smear_max_px=0):
        """원본 그레이스케일에서 프로파일·밴드·volume 계산(보정 무시).
        volume = 밴드 피크 아래 면적(배경 차감 적분), 정량의 기준값.

        threshold_pct: 밴드 경계(=적분 범위) 기준 — '피크 높이에서 로컬
        배경을 뺀 순신호가 threshold_pct%로 떨어지는 지점'을 골짜기 범위
        안에서 찾아 경계로 쓴다(find_peaks의 left/right_bases를 그대로
        쓰면 촘촘한 밴드의 영역이 서로 이어져 보임). 값을 올리면 경계가
        좁아지고, 적분 범위 자체이므로 정량값도 같이 바뀐다.

        y_top/y_bot: 세로 분석 범위를 원본 이미지 행 인덱스로 제한
        (None=제한 없음). 웰·염료전선 등을 잘라낼 때 쓴다. self.profile은
        항상 원본 전체 높이로 계산해(오버레이·MW 회귀가 행 인덱스를 그대로
        쓰므로) find_peaks와 경계 탐색만 [y_top, y_bot] 안으로 제한한다.

        smear_max_px: 밴드 경계 폭(px) 상한선, 0=제한 없음(기본값). 넘는
        피크는 smear로 보아 결과에서 뺀다. 제외 개수는 self.n_smear."""
        strip = gray_orig[:, self.x1:self.x2 + 1].astype(float)
        width = strip.shape[1]                       # 레인 폭(px)
        self.profile = 255.0 - strip.mean(axis=1)    # 밴드가 어두울수록 높은 값
        prof = self.profile
        H = len(prof)
        y0 = 0 if y_top is None else int(np.clip(y_top, 0, H - 1))
        y1 = (H - 1) if y_bot is None else int(np.clip(y_bot, y0, H - 1))
        from scipy.signal import find_peaks
        peaks_local, props = find_peaks(prof[y0:y1 + 1], prominence=prominence, distance=distance)
        peaks = peaks_local + y0                      # 원본 이미지 행 좌표로 환산
        self.peak_prom = props.get("prominences", np.zeros(len(peaks)))

        # 밴드 volume: 피크 좌우 경계 사이를 적분하고 국소 배경을 차감
        peak_area = np.zeros(len(peaks))        # 평균 강도(높이) 기준
        peak_volume = np.zeros(len(peaks))      # 면적×폭 = 부피
        peak_bounds = []                         # 밴드별 (위_y, 아래_y) 경계
        lb = props.get("left_bases", np.zeros(len(peaks_local), int)) + y0
        rb = props.get("right_bases", np.zeros(len(peaks_local), int)) + y0
        thr = max(0.0, min(99.0, float(threshold_pct))) / 100.0
        # 인접 피크 사이 골(최저점)을 경계 한계로 삼는다 — find_peaks의
        # left/right_bases는 더 먼 골까지 뻗어 옆 밴드 박스와 겹쳐 보일 수
        # 있는데, 양옆 골 안쪽으로 가두면 절대 안 겹친다(맞닿을 뿐). 양 끝
        # 피크는 [y0, y1]로도 같이 가둬 범위 밖으로 새지 않게 한다.
        valleys = []
        for j in range(len(peaks) - 1):
            a, b = int(peaks[j]), int(peaks[j + 1])
            valleys.append(a + int(np.argmin(prof[a:b + 1])))
        for i, py in enumerate(peaks):
            lo_lim = max(valleys[i - 1] if i > 0 else y0, y0)
            hi_lim = min(valleys[i] if i < len(peaks) - 1 else y1, y1)
            l0 = max(int(lb[i]), lo_lim); r0 = min(int(rb[i]), hi_lim)
            if r0 <= l0:
                l0, r0 = max(lo_lim, py - 5), min(hi_lim, py + 5)
            # [l0, r0] 안에서 순신호가 thr 이하로 떨어지는 가장 가까운
            # 지점을 좌우로 찾는다(못 찾으면 골짜기 끝까지 그대로).
            local_base = min(prof[l0], prof[r0])
            peak_h = max(prof[py] - local_base, 1e-9)
            target = local_base + peak_h * thr
            l = l0
            for x in range(py, l0 - 1, -1):
                if prof[x] <= target:
                    l = x; break
            r = r0
            for x in range(py, r0 + 1):
                if prof[x] <= target:
                    r = x; break
            peak_bounds.append((l, r))
            seg = prof[l:r + 1]
            # 경계 두 점을 잇는 직선을 국소 배경으로 보고 차감
            base = np.linspace(prof[l], prof[r], len(seg))
            net = np.clip(seg - base, 0, None)
            area = float(net.sum())                  # 세로 적분 (강도·px)
            peak_area[i] = area
            peak_volume[i] = area * width        # 레인 폭을 곱해 부피화

        # smear(폭 넓게 퍼진 피크) 자동 제외. smear_max_px=0(기본값)이면
        # 제외 없음(기존 동작과 동일). 경계 폭(l~r)이 이 값을 넘는지만
        # 보는 절대 길이 제한이라 결과를 예측하기 쉽다.
        self.n_smear = 0
        smear_max_px = max(0, int(smear_max_px))
        if len(peaks) > 0 and smear_max_px > 0:
            bound_w = np.array([(r - l) for (l, r) in peak_bounds], dtype=int)
            keep = bound_w <= smear_max_px
            self.n_smear = int(keep.size - int(keep.sum()))
            if self.n_smear > 0:
                peaks = peaks[keep]
                self.peak_prom = self.peak_prom[keep]
                peak_area = peak_area[keep]
                peak_volume = peak_volume[keep]
                peak_bounds = [b for b, k in zip(peak_bounds, keep) if k]

        self.peaks = peaks
        self.peak_area = peak_area
        self.peak_volume = peak_volume
        self.peak_bounds = peak_bounds
        self.mw = []
