"""bandwagon.imaging

이미지 변환/분석 보조: PIL<->QPixmap, 다운스케일, 분석 오버레이,
워프/블렌드/UV-only, 곡률보정, 그리고 되돌리기 재생 엔진이 쓰는
apply_edit_op(). 무거운 cv2/scipy는 함수 안에서 지연 로딩.

(BandWagon v1.1을 모듈로 분할한 것 — 동작은 원본과 동일.)
"""
import numpy as np
from PIL import Image, ImageOps, ImageDraw, ImageFont
from PyQt5.QtGui import QImage, QPixmap


def pil_to_pixmap(img):
    img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qi = QImage(data, img.width, img.height, QImage.Format_RGBA8888).copy()
    return QPixmap.fromImage(qi)


def downscale_for_preview(img, canvas_w, canvas_h, margin=1.5):
    """드래그 중인 라이브 미리보기 전용 — 무거운 연산(cv2 워프/remap) 앞에서
    캔버스 크기에 맞춰 미리 줄여 연산량을 캔버스 크기에 비례하게 만든다.
    margin(기본 1.5배)만큼 여유 있게 키워 줌인 시 또렷함이 바로 깨지지
    않게 한다. 원본이 이미 더 작으면 그대로 반환. canvas_w/h가 0 이하면
    (레이아웃 전 등) 안전하게 원본을 그대로 반환한다.

    반환: (축소된 PIL Image, scale) — scale은 원본→축소 좌표 배율(0~1)."""
    if canvas_w <= 0 or canvas_h <= 0:
        return img, 1.0
    target_w = max(1, int(canvas_w * margin))
    target_h = max(1, int(canvas_h * margin))
    w, h = img.size
    if w <= target_w and h <= target_h:
        return img, 1.0
    scale = min(target_w / w, target_h / h)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    return img.resize(new_size, Image.BILINEAR), scale


# ═══════════════════════════════════════════════════════════════════
#  커브 모델 (디스플레이 전용 LUT)
# ═══════════════════════════════════════════════════════════════════


def render_analysis_overlay(base_img, lanes, band_style="area"):
    """원본 해상도의 base_img 위에 레인 경계·검출 밴드·MW 라벨을 그려 합성한
    새 이미지를 반환한다(화면 캡처가 아니라 원본 좌표 기준으로 직접 그림 —
    저장 해상도가 화면 크기에 좌우되지 않음).

    band_style: "area"(경계 영역, 반투명 박스) 또는 "line"(피크 위치 한 줄).
    화면 캔버스(GelView)와 항상 같은 방식으로 호출돼야 한다.

    2-패스로 그린다: 레인 박스/밴드선을 먼저 다 그리고 텍스트(제목/MW)는
    나중에 — 한 패스로 그리면 다음 레인 박스가 이전 레인 글자를 덮는다."""
    img = base_img.convert("RGB").copy()
    draw = ImageDraw.Draw(img)

    def _font_to_fit(text, max_width, base_size=14, min_size=7):
        """텍스트가 max_width(px) 안에 들어가는 가장 큰 폰트 크기를 찾는다.
        레인 폭이 좁아 제목이 옆 레인을 침범하는 가독성 문제를 막기 위함."""
        size = base_size
        while size > min_size:
            try:
                f = ImageFont.truetype("DejaVuSans-Bold.ttf", size)
            except Exception:
                return ImageFont.load_default(), len(text) * size * 0.6
            bbox = draw.textbbox((0, 0), text, font=f)
            w = bbox[2] - bbox[0]
            if w <= max_width:
                return f, w
            size -= 1
        try:
            f = ImageFont.truetype("DejaVuSans-Bold.ttf", min_size)
            bbox = draw.textbbox((0, 0), text, font=f)
            return f, bbox[2] - bbox[0]
        except Exception:
            return ImageFont.load_default(), len(text) * min_size * 0.6

    try:
        font_small = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 11)
    except Exception:
        try:
            font_small = ImageFont.truetype("DejaVuSansMono.ttf", 11)
        except Exception:
            font_small = ImageFont.load_default()
    H = img.height

    # ── 1패스: 레인 박스 + 밴드 표시 (텍스트보다 먼저, 즉 아래 레이어) ──
    # band_style="area": 위경계~아래경계 영역을 반투명 박스로 — '여기서부터
    # 여기까지를 한 밴드로 본다(=적분 범위)'가 한눈에 들어온다.
    # band_style="line": 피크 위치에 한 줄만 — 밴드가 촘촘해 영역들이 서로
    # 겹쳐 보일 때 더 깔끔하게 보고 싶은 경우를 위한 대안.
    # RGBA 오버레이를 따로 그려 알파 블렌딩한 뒤 합성한다(PIL의 기본 Draw는
    # 알파 블렌딩을 지원하지 않음).
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for lane in lanes:
        col = (lane.color.red(), lane.color.green(), lane.color.blue())
        draw.rectangle([lane.x1, 0, lane.x2, H - 1], outline=col, width=2)
        if lane.peaks is not None:
            if band_style == "line":
                for py in lane.peaks:
                    py = int(py)
                    odraw.line([(lane.x1, py), (lane.x2, py)], fill=col + (255,), width=2)
            else:
                bounds = lane.peak_bounds if lane.peak_bounds else [
                    (max(0, int(py) - 5), min(H - 1, int(py) + 5)) for py in lane.peaks]
                for (top, bot) in bounds:
                    # 영역을 옅은 반투명 채우기로, 위/아래 경계는 또렷한 선으로
                    odraw.rectangle([lane.x1, top, lane.x2, bot], fill=col + (55,))
                    odraw.line([(lane.x1, top), (lane.x2, top)], fill=col + (255,), width=1)
                    odraw.line([(lane.x1, bot), (lane.x2, bot)], fill=col + (255,), width=1)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)  # 합성 후 이미지가 바뀌었으니 Draw 핸들도 새로 받음

    # ── 2패스: 텍스트(레인 제목 + MW 값) — 항상 레인 박스 위에 그려짐 ──
    for lane in lanes:
        col = (lane.color.red(), lane.color.green(), lane.color.blue())
        label = lane.name
        if lane.kind == "marker": label += " [M]"
        elif lane.kind == "bsa": label += " [BSA]"
        lane_w = max(1, lane.x2 - lane.x1)
        font, text_w = _font_to_fit(label, lane_w - 8)
        draw.rectangle([lane.x1 + 2, 2, lane.x1 + 2 + text_w + 6, 2 + font.size + 4],
                       fill=(13, 18, 23))
        draw.text((lane.x1 + 5, 3), label, fill=col, font=font)
        if lane.peaks is not None:
            bounds = lane.peak_bounds if lane.peak_bounds else None
            last_ty = -1e9   # 같은 레인 라벨 겹침 방지(직전 라벨 y 추적)
            for j, py in enumerate(lane.peaks):
                py = int(py)
                if band_style == "line" or not bounds:
                    top = py                    # 선 모드: 그 줄 바로 위
                else:
                    top = bounds[j][0]          # 영역 모드: 경계 위쪽 기준
                if j < len(lane.mw) and lane.mw[j] is not None and lane.mw[j] > 0:
                    txt = f"{lane.mw[j]:.1f}"
                    # 밴드 영역 위(상단 경계선보다 살짝 위)에 투명 배경으로, 흰 글자+검은
                    # 외곽선을 입혀 어떤 배경색(밴드의 진한 파란색 등) 위에서도 또렷하게
                    # 보이게 함. 옆으로 빼지 않으므로 인접 레인과 안 겹친다.
                    bbox = draw.textbbox((0, 0), txt, font=font_small)
                    tw = bbox[2] - bbox[0]
                    tx = lane.x1 + (lane_w - tw) / 2  # 레인 폭 중앙에 배치
                    ty = top - bbox[3] - 2             # 밴드 영역 위쪽 경계선 바로 위
                    if ty < last_ty + 12:             # 너무 가까우면 아래로 밀어 겹침 방지
                        ty = last_ty + 12
                    last_ty = ty
                    draw.text((tx, ty), txt, font=font_small,
                              fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    return img


# ═══════════════════════════════════════════════════════════════════
#  젤 영역 자동 인식 (펴기 탭의 '자동 인식' 버튼)
# ═══════════════════════════════════════════════════════════════════
def _flatten_illumination(channel):
    """채널(2D uint8 배열)의 전역 조명 불균일을 평탄화한다. 채널 자신을
    크게 블러한 '배경 추정치'로 나눠서, 조명처럼 천천히 변하는 큰 기울기는
    지우고 국소적 명암 차이(=젤 vs 배경 경계)는 살린다. 커널을 이미지
    크기의 1/8 정도로 크게 잡는 게 핵심 — 작으면 젤 내부의 밴드 같은
    국소 디테일까지 같이 지워버려 경계가 무뎌진다."""
    import cv2
    h, w = channel.shape
    k = max(31, (min(h, w) // 8) | 1)   # 홀수 보장
    bg = cv2.GaussianBlur(channel, (k, k), 0).astype(np.float32)
    flat = channel.astype(np.float32) / (bg + 1e-3) * 128.0
    return np.clip(flat, 0, 255).astype(np.uint8)


def _best_quad_from_channel(channel, w, h):
    """단일 채널에서 가장 그럴듯한 젤 사각형을 찾는다.
    반환: (quad(4,2) 또는 None, 그 컨투어의 면적(px², 실패 시 0)).

    기존 방식보다 두 가지를 더 신경 쓴다:
      1) 닫기(closing) 커널을 이미지 크기에 비례해 훨씬 크게 잡는다 —
         젤 안의 밴드들이 어두운/밝은 얼룩으로 마스크에 구멍을 내면서
         컨투어가 여러 조각으로 쪼개지는 게 실패의 흔한 원인이었다.
      2) 가장 큰 컨투어 '하나만' 보지 않는다. 마커 레인이 본체와 눈에
         띄게 떨어져 찍힌 사진(흔한 배치)에서는 닫기로도 안 이어질 만큼
         틈이 넓어, 마커가 별도의(더 작은) 컨투어가 돼 버린다. 그래서
         가장 큰 컨투어를 기준으로 두고, 그것과 세로로 많이 겹치면서
         (같은 '레인들의 줄'에 있다는 뜻) 충분히 큰 다른 컨투어가 있으면
         그 점들까지 합쳐서 전체를 감싸는 사각형을 구한다 — 세로로
         겹치지 않는 컨투어(예: 사진 모서리의 작은 얼룩, 별개의 라벨지)는
         같은 젤의 일부가 아닐 가능성이 높으므로 포함하지 않는다.
      3) 4점 다각형 근사(approxPolyDP)가 실제 컨투어 면적과 많이
         다르면(찌그러진 근사) 그 결과를 버리고 회전된 바운딩 사각형
         (minAreaRect)으로 대체한다 — 라벨지·기포 등으로 한쪽 모서리가
         깎여 나가 다각형 근사가 비뚤어지는 경우의 안전망."""
    import cv2
    blur = cv2.GaussianBlur(channel, (5, 5), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    border = np.concatenate([th[0, :], th[-1, :], th[:, 0], th[:, -1]])
    if (border == 255).mean() > 0.5:
        th = cv2.bitwise_not(th)
    k = max(15, (min(w, h) // 40) | 1)   # 기존 5x5보다 훨씬 크게, 해상도에 비례
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8), iterations=2)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), iterations=1)
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None, 0.0
    main = max(cnts, key=cv2.contourArea)
    main_area = cv2.contourArea(main)
    if main_area < 0.1 * w * h:
        return None, 0.0
    mx, my, mw_, mh_ = cv2.boundingRect(main)

    # 마커처럼 별도 컨투어가 된 영역을 같이 모은다. 기준: 면적이 충분히
    # 크고(주 컨투어 면적의 5% 이상 — 너무 작은 잡음은 거름), 주 컨투어와
    # 세로로 절반 이상 겹친다(=비슷한 높이 범위에 있다 = 같은 레인 줄).
    points = [main.reshape(-1, 2)]
    for c in cnts:
        if c is main:
            continue
        a = cv2.contourArea(c)
        if a < 0.05 * main_area:
            continue
        x, y, cw, ch = cv2.boundingRect(c)
        overlap = max(0, min(my + mh_, y + ch) - max(my, y))
        if overlap >= 0.5 * min(mh_, ch):
            points.append(c.reshape(-1, 2))
    all_pts = np.concatenate(points, axis=0)
    area = float(cv2.contourArea(cv2.convexHull(all_pts))) if len(points) > 1 else main_area

    rect_quad = cv2.boxPoints(cv2.minAreaRect(all_pts)).astype(np.float32)
    if len(points) > 1:
        # 컨투어 여러 개를 합친 경우, 그 합집합은 임의의 모양일 수 있어
        # approxPolyDP로 4점을 안정적으로 뽑기 어렵다 — 바운딩 사각형으로
        # 충분하고 더 안전하다.
        return rect_quad, area
    peri = cv2.arcLength(main, True)
    approx = cv2.approxPolyDP(main, 0.02 * peri, True)
    if len(approx) == 4:
        poly_quad = approx.reshape(4, 2).astype(np.float32)
        if cv2.contourArea(poly_quad) > 0.7 * main_area:   # 근사가 컨투어를 잘 따라갔을 때만 채택
            return poly_quad, float(main_area)
    return rect_quad, float(main_area)


def find_gel_quad(img_rgb):
    """사진(np.ndarray, RGB)에서 젤 영역의 네 모서리를 자동으로 찾는다.
    반환: 4점(np.ndarray, (4,2), 순서 무관 — 호출부가 정렬) 또는 실패 시 None.

    그레이스케일 하나만으로는 조명이 한쪽으로 기운 사진(젤 촬영장비에서
    흔함)이나 어두운/밝은 배경이 뒤섞인 경우(UV 형광 사진 vs 라이트박스
    사진) 둘 다에 안정적으로 맞추기 어렵다. 그래서 조명보정 채널을 먼저
    시도하고, 원본 채널은 그게 실패했을 때만 보조로 쓴다.

    채널들을 전부 시도해서 '성공한 것 중 면적이 가장 큰 것'을 고르는
    방식을 처음에 썼었는데, 그건 틀렸다 — 조명이 기울면 보정 안 된
    원본 채널의 threshold가 배경 일부까지 같이 삼켜서 실제 젤보다 더
    넓은(하지만 틀린) 영역을 만들어내는 경우가 있고, 그게 '면적이 크다'는
    이유로 올바른 결과보다 우선 선택돼 버렸다(합성 데이터로 직접 확인한
    문제). 그래서 지금은 면적 비교 없이, 조명 불균일을 직접 상쇄하는
    채널을 항상 먼저 믿고, 그게 아예 실패(면적 10% 미만)할 때만 다음
    순위로 넘어간다."""
    import cv2
    h, w = img_rgb.shape[:2]
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    # 우선순위: 조명보정 채널(그레이/명도) 먼저, 원본 그레이스케일·채도는
    # 그게 실패했을 때만 쓰는 보조 수단.
    channels_in_priority = [
        _flatten_illumination(gray),
        _flatten_illumination(hsv[:, :, 2]),
        gray,
        hsv[:, :, 1],
    ]
    for ch in channels_in_priority:
        quad, _area = _best_quad_from_channel(ch, w, h)
        if quad is not None:
            return quad
    return None


# ═══════════════════════════════════════════════════════════════════
#  웨스턴 블롯 합성 (가시광 사진 + UV 사진 정합)
# ═══════════════════════════════════════════════════════════════════
# 가시광이 기준(고정), UV가 변형 대상. UV 위에서 찍은 4개 코너를 가시광
# 캔버스 전체에 퍼스펙티브 변환으로 맞춘다. 화면/저장용은 둘을 섞은 블렌드,
# 실제 밴드 검출(analyze())엔 UV 단독 그레이스케일을 쓴다 — 가시광의 밝은
# 종이/마커 글자가 가짜 밴드로 오검출되는 것을 막기 위함.
def warp_uv_to_visible(uv_img, uv_corners, vis_size):
    """UV 이미지를 4개 코너 기준으로 가시광 이미지 크기(vis_size)에 맞게 편다.
    uv_corners: [(x,y) x4] 순서는 좌상→우상→우하→좌하 (기존 펴기 탭과 동일 규약).
    반환: vis_size 크기로 변환된 PIL RGB 이미지."""
    import cv2
    w, h = vis_size
    src = np.array(uv_corners, dtype=np.float32)
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    arr = np.array(uv_img.convert("RGB"))
    out = cv2.warpPerspective(arr, M, (w, h), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    return Image.fromarray(out, "RGB")


def warp_visible_to_uv(vis_img, uv_corners, uv_size):
    """warp_uv_to_visible의 역방향 — 가시광 이미지를 같은 매핑으로 거꾸로
    적용해 UV 캔버스 크기(uv_size)에 맞춘다. UV 배경에 가시광을 참고용으로
    겹쳐 보여주는 라이브 미리보기에 쓴다."""
    import cv2
    w, h = uv_size
    vw, vh = vis_img.size
    dst = np.array(uv_corners, dtype=np.float32)
    src = np.array([[0, 0], [vw - 1, 0], [vw - 1, vh - 1], [0, vh - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    arr = np.array(vis_img.convert("RGB"))
    out = cv2.warpPerspective(arr, M, (w, h), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    return Image.fromarray(out, "RGB")


def blend_visible_uv(vis_img, uv_warped, uv_opacity=0.6):
    """화면/저장용 블렌드. UV가 어두운(=신호 없는) 영역일수록 가시광이 더
    비쳐 보이도록, UV 밝기를 알파값으로도 같이 써서 자연스러운 합성을 만든다.
    uv_opacity: UV 레이어 전체의 최대 불투명도(0~1) — 슬라이더로 조절."""
    vis = np.array(vis_img.convert("RGB"), dtype=np.float32)
    uv = np.array(uv_warped.convert("RGB"), dtype=np.float32)
    uv_gray = uv.mean(axis=2, keepdims=True) / 255.0   # UV 밝기를 0~1 알파로
    alpha = np.clip(uv_gray * uv_opacity, 0, 1)
    out = vis * (1 - alpha) + uv * alpha
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def blend_for_uv_canvas(uv_img, vis_warped_to_uv, vis_opacity=0.6):
    """코너 지정 캔버스(좌표계=UV)용 라이브 블렌드. UV는 또렷하게, 가시광은
    vis_opacity만큼만 얹는다(여긴 UV가 메인이라 단순 선형 블렌드면 충분 —
    blend_visible_uv처럼 UV 밝기를 알파로 쓰지 않음)."""
    uv = np.array(uv_img.convert("RGB"), dtype=np.float32)
    vis = np.array(vis_warped_to_uv.convert("RGB"), dtype=np.float32)
    out = uv * (1 - vis_opacity) + vis * vis_opacity
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def uv_only_grayscale(uv_warped):
    """분석(밴드 검출)에 쓸 그레이스케일 — UV 강도만, 가시광 정보는 전혀 섞지
    않는다. analyze()가 기대하는 형태(np.uint8 2D 배열)와 동일하게 만든다."""
    return np.array(uv_warped.convert("L"), dtype=np.uint8)


# ═══════════════════════════════════════════════════════════════════
#  편집 연산 재생(replay) 엔진 — 되돌리기/다시하기
# ═══════════════════════════════════════════════════════════════════
# 이미지 스냅샷을 단계마다 쌓지 않고, '연산 기록만 가볍게 들고 있다가
# 필요할 때 처음부터 다시 계산'한다.
#   - pristine_orig: 마지막 '새 원본' 시점 이미지(로드 시/합성 임포트 시)
#   - edit_ops: pristine 이후 순서대로 적용된 (연산이름, 파라미터) 목록
# 화면용 _orig = pristine + edit_ops를 처음부터 재적용한 결과. 되돌리기/
# 다시하기는 리스트를 지우지 않고 '몇 개까지 재생할지' 포인터만 옮긴다.
#
# 합성 임포트 세션에서는 재생 시작 그레이스케일 오버라이드(UV 단독 강도)가
# _edit_gray_pristine에 고정돼 있어, 회전/자르기/펴기 같은 기하 연산이
# 이미지와 함께 이 오버라이드도 변환하며 분석용 좌표계 정렬을 유지한다.
def apply_bow_correction(img, amount):
    """img(PIL Image)에 곡률 보정을 적용한다. 각 열(x)을 중심에서 멀수록
    0에 가깝고 중앙에서 amount(px)만큼 큰 포물선 모양으로 수직 이동시킨다
    (cv2.remap, BORDER_REFLECT). amount>0: 처진 모양을 위로 당겨 편다,
    amount<0: 솟은 모양을 아래로 당겨 편다.

    가장자리는 BORDER_REPLICATE(가장자리 픽셀을 그대로 늘여씀)이 아니라
    BORDER_REFLECT(거울처럼 반사)를 쓴다 — 실제 원본 픽셀은 아니지만(그건
    이 시점까지의 회전·자르기 전체를 누적 계산해 pristine에서 역매핑해야
    해서 훨씬 큰 작업), 밋밋하게 늘어나 보이는 것보다 자연스럽다(실사용
    피드백으로 교체).

    모듈 레벨 함수인 이유: apply_edit_op()가 Analyzer 클래스 정의보다
    앞에서 이 함수를 참조해야 한다(클래스 내부 staticmethod로 두면
    순환 의존이 생김)."""
    if amount == 0:
        return img
    arr = np.array(img.convert("RGB"))
    h, w = arr.shape[:2]
    cx = w / 2.0
    xs = np.arange(w, dtype=np.float32)
    shift = float(amount) * ((xs - cx) / cx) ** 2
    map_x, map_y = np.meshgrid(np.arange(w, dtype=np.float32),
                                np.arange(h, dtype=np.float32))
    map_y = map_y - shift[np.newaxis, :]
    import cv2
    out = cv2.remap(arr, map_x, map_y, interpolation=cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REFLECT)
    return Image.fromarray(out, "RGB")


def apply_shear_correction(img, amount):
    """img(PIL Image)에 기울기(전단) 보정을 적용한다. bow_correct가 열(x)
    기준 '세로' 포물선 이동인 것과 달리, 이건 행(y) 기준 '가로' 선형 이동
    이다 — 사진이 평행사변형으로 기울어져 찍혔을 때(젤 본체는 직사각형인데
    카메라/스캐너가 비스듬해 위아래 변의 x가 서로 어긋난 경우) 각 행을
    세로 위치에 비례해 좌우로 밀어 직사각형으로 되돌린다.

    amount(px): 이미지 위쪽(y=0)과 아래쪽(y=h-1) 사이의 총 가로 이동량.
    중심 행(h/2)은 이동 없음, 위쪽 절반은 -amount/2 ~ 0, 아래쪽 절반은
    0 ~ +amount/2로 선형 이동한다(부호는 위쪽 기준 오른쪽으로 치우친
    사진을 왼쪽으로 당겨 펴는 방향). cv2.remap, BORDER_REFLECT로 빈
    가장자리를 거울처럼 반사해 채운다(apply_bow_correction과 동일한
    이유로 BORDER_REPLICATE에서 교체).

    bow_correct처럼 모듈 레벨 함수 — apply_edit_op()가 참조해야 하므로
    클래스 안에 두면 순환 의존이 생긴다."""
    if amount == 0:
        return img
    arr = np.array(img.convert("RGB"))
    h, w = arr.shape[:2]
    cy = h / 2.0
    ys = np.arange(h, dtype=np.float32)
    shift = float(amount) * ((ys - cy) / max(h - 1, 1))  # 위(-)~아래(+) 선형
    map_x, map_y = np.meshgrid(np.arange(w, dtype=np.float32),
                                np.arange(h, dtype=np.float32))
    map_x = map_x - shift[:, np.newaxis]
    import cv2
    out = cv2.remap(arr, map_x, map_y, interpolation=cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REFLECT)
    return Image.fromarray(out, "RGB")


def apply_edit_op(img, gray_override, op_name, params):
    """단일 편집 연산을 img(PIL RGB)에 적용해 (새 이미지, 새 gray_override)를
    반환한다. gray_override는 WB 합성 적용 중일 때만 None이 아니며, 보통의
    기하 연산(회전/자르기 등)은 입력으로 받은 gray_override를 그대로 통과
    시킨다 — WB 합성 이후 추가된 회전/자르기는 화면(_orig)뿐 아니라 분석용
    그레이스케일에도 동일하게 적용되어야 같은 좌표계를 유지하기 때문이다."""
    if op_name == "rotate":
        deg = params["deg"]
        out = img.rotate(-deg, expand=True)
        return out, _reapply_gray_geom(gray_override, lambda a: _np_rotate90(a, deg))
    if op_name == "flip":
        d = params["dir"]
        out = ImageOps.mirror(img) if d == "h" else ImageOps.flip(img)
        return out, _reapply_gray_geom(gray_override, lambda a: (np.fliplr(a) if d == "h" else np.flipud(a)))
    if op_name == "invert_colors":
        out = ImageOps.invert(img.convert("RGB"))
        return out, gray_override  # 색상 반전은 화면용 RGB만 바꿈(그레이스케일 오버라이드는 UV 신호이므로 무관)
    if op_name == "fine_rotate":
        deg = params["deg"]
        out = img.rotate(-deg, resample=Image.BICUBIC, expand=False, fillcolor=(255, 255, 255))
        return out, gray_override  # 정밀회전은 미세 보간이라 그레이스케일 오버라이드까지 재계산하지 않음(근사 허용)
    if op_name == "bow_correct":
        out = apply_bow_correction(img, params["amount"])
        return out, gray_override
    if op_name == "shear_correct":
        out = apply_shear_correction(img, params["amount"])
        return out, gray_override  # bow_correct와 동일하게 gray_override는 그대로 통과(기존 관례 유지)
    if op_name == "adjust":
        # 밝기/대비/톤커브는 화면 표시용 파라미터일 뿐 픽셀 자체를 바꾸지
        # 않으므로 그대로 통과시킨다. 이 op가 되돌리기 기록에 남는 이유는
        # _replay_history()가 재생 중 만난 가장 최근 'adjust'의 params를
        # 읽어 슬라이더/커브 위젯에 되돌려 놓기 위함뿐이다.
        return img, gray_override
    if op_name == "lanes":
        # 레인 구성(개수/경계/이름/종류/마커)도 'adjust'와 같은 이유로
        # 패스스루 — 픽셀은 안 바꾸고, _replay_history()가 가장 최근
        # 'lanes'의 params를 읽어 레인 목록을 복원하는 데만 쓰인다.
        return img, gray_override
    if op_name == "crop":
        x1, y1, x2, y2 = params["box"]
        out = img.crop((x1, y1, x2, y2))
        new_gray = gray_override[y1:y2, x1:x2] if gray_override is not None else None
        return out, new_gray
    if op_name == "warp":
        import cv2
        src = np.array(params["corners"], dtype=np.float32)
        tl, tr_, br, bl = src
        wt = np.linalg.norm(tr_ - tl); wb = np.linalg.norm(br - bl)
        hl = np.linalg.norm(bl - tl); hr = np.linalg.norm(br - tr_)
        ow = max(int(round(max(wt, wb))), 10); oh = max(int(round(max(hl, hr))), 10)
        dst = np.array([[0, 0], [ow - 1, 0], [ow - 1, oh - 1], [0, oh - 1]], dtype=np.float32)
        M = cv2.getPerspectiveTransform(src, dst)
        out_arr = cv2.warpPerspective(np.array(img.convert("RGB")), M, (ow, oh),
                                      flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                      borderValue=(255, 255, 255))
        new_gray = None
        if gray_override is not None:
            gray_rgb = np.stack([gray_override] * 3, axis=-1).astype(np.uint8)
            warped_gray = cv2.warpPerspective(gray_rgb, M, (ow, oh), flags=cv2.INTER_LINEAR,
                                              borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
            new_gray = warped_gray[:, :, 0]
        return Image.fromarray(out_arr, "RGB"), new_gray
    raise ValueError(f"알 수 없는 편집 연산: {op_name}")


def _np_rotate90(arr, deg):
    """90/180/-90도 회전을 그레이스케일 numpy 배열(분석용 오버라이드)에
    적용한다. PIL의 Image.rotate(expand=True)와 동일한 의미가 되도록
    np.rot90을 쓴다(반시계 기준이라 부호를 PIL과 맞춰 보정)."""
    k = {90: 1, -90: -1, 180: 2, -180: 2}.get(deg, 0)
    if k == 0:
        return arr
    return np.rot90(arr, k=k)


def _reapply_gray_geom(gray_override, fn):
    """gray_override가 있을 때만 기하 변환 함수를 적용하고, 없으면 그대로
    None을 통과시키는 공용 헬퍼 — 매 분기마다 'if gray_override is not None'을
    반복 쓰지 않기 위함."""
    if gray_override is None:
        return None
    return fn(gray_override)
