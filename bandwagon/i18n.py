"""bandwagon.i18n

다국어 문자열(STRINGS, ko/en 키셋 일치) + tr() + 언어 전역 상태.
주의: 다른 모듈은 절대 'from .i18n import CURRENT_LANG'로 값을 스냅샷하지
말 것. 런타임에 바뀌므로 i18n.tr()/i18n.set_lang()/i18n.CURRENT_LANG으로
참조해야 언어 전환이 동작한다.

(BandWagon v1.1을 모듈로 분할한 것 — 동작은 원본과 동일.)
"""
import os, json
from pathlib import Path


_LANG_SETTING_PATH = Path(os.path.expanduser("~")) / ".bandwagon_lang.json"


def load_lang_setting():
    """저장된 언어 설정을 읽는다. 없으면 OS 로캘로 추정, 실패하면 'en'."""
    try:
        if _LANG_SETTING_PATH.exists():
            data = json.loads(_LANG_SETTING_PATH.read_text(encoding="utf-8"))
            if data.get("lang") in ("ko", "en"):
                return data["lang"]
    except Exception:
        pass
    try:
        import locale
        loc = (locale.getdefaultlocale()[0] or "").lower()
        return "ko" if loc.startswith("ko") else "en"
    except Exception:
        return "en"


def save_lang_setting(lang):
    try:
        _LANG_SETTING_PATH.write_text(json.dumps({"lang": lang}), encoding="utf-8")
    except Exception:
        pass  # 저장 실패해도(권한 등) 앱 동작에는 영향 없음


CURRENT_LANG = load_lang_setting()  # "ko" 또는 "en" — tr()이 참조하는 전역 상태


STRINGS = {
    "ko": {
        # MarkerDialog
        "marker_dialog_title": "마커 MW 입력 (kDa)",
        "preset_label": "프리셋:",
        "preset_manual_entry": "직접 입력",
        "preset_manage_btn": "관리…",
        "marker_hint_default": "검출된 밴드 {n}개. 위에서 아래 순서로 분자량을 입력하세요 (kDa).",
        "marker_hint_matched": "'{name}' 적용 — 밴드 {n}개가 일치해 자동으로 채웠습니다. 필요하면 값을 직접 수정할 수 있습니다.",
        "marker_hint_mismatch": "'{name}'은 밴드 {preset_n}개인데 검출된 밴드는 {n}개입니다. 각 밴드가 프리셋의 몇 번째 값에 해당하는지 직접 골라주세요.",
        "preset_match_row_label": "  매칭:",
        # MarkerPresetManager
        "preset_manager_title": "마커 프리셋 관리",
        "preset_col_name": "이름",
        "preset_col_bands": "밴드(kDa, 큰->작은 순)",
        "preset_add_btn": "추가…",
        "preset_remove_btn": "선택 삭제",
        "preset_add_title": "프리셋 추가",
        "preset_add_name_label": "프리셋 이름:",
        "preset_add_mw_label": "분자량을 큰 것부터 작은 것 순서로, 쉼표로 구분해 입력 (예: 250,130,95,70,55,35,25,15):",
        "input_error_title": "입력 오류",
        "preset_mw_parse_error": "숫자를 쉼표로 구분해 입력해주세요.",
        # GelView / ProfileView / StdCurveView
        "canvas_empty_hint": "이미지를 열거나  Ctrl+V 로 붙여넣으세요\n(드래그 앤 드롭도 됩니다)",
        "profile_title": "밀도 프로파일 (원본 기준)",
        "profile_empty_hint": "밴드 분석을 실행하면 레인별 곡선이 표시됩니다",
        "std_curve_empty_hint": "BSA 표준 레인 2개 이상에서 표준곡선이 생성됩니다",
        # 툴바
        "toolbar_open": "열기",
        "toolbar_paste": "붙여넣기",
        "toolbar_project_open": "프로젝트 열기",
        "toolbar_project_open_tip": "저장된 .bandwagon 프로젝트(원본 이미지 + 오버레이/분석 상태)를 불러옵니다. (Ctrl+Shift+O)",
        "toolbar_project_save": "프로젝트 저장",
        "toolbar_project_save_tip": "현재 이미지와 모든 조정·레인·분석 상태를 .bandwagon 파일 하나로 저장합니다.\n나중에 '프로젝트 열기'로 다시 불러와 이어서 작업할 수 있습니다. (Ctrl+S)",
        "toolbar_composite_studio": "합성 스튜디오",
        "toolbar_composite_studio_tip": "가시광+UV 사진을 정렬해 합성하는 별도 창을 엽니다.\n합성 결과를 .bwcomposite 파일로 내보낸 뒤 '합성 불러오기'로 분석할 수 있습니다.",
        "toolbar_composite_import": "합성 불러오기",
        "toolbar_composite_import_tip": "합성 스튜디오에서 내보낸 .bwcomposite 파일을 열어 밴드 분석을 시작합니다.",
        "toolbar_copy_result": "결과 이미지 복사",
        "toolbar_copy_result_tip": "현재 이미지를 클립보드로 복사합니다(분석 결과 있으면 포함 여부를 물어봄).",
        "toolbar_save_result": "결과 이미지 저장",
        "toolbar_save_result_tip": "현재 이미지를 파일로 저장합니다(분석 결과 있으면 포함 여부를 물어봄).",
        "toolbar_export_csv": "CSV 내보내기",
        "toolbar_reset_all": "전체 초기화",
        "toolbar_undo": "되돌리기",
        "toolbar_undo_tip": "마지막 회전/반전/자르기/펴기를 되돌립니다 (Ctrl+Z)",
        "toolbar_redo": "다시하기",
        "toolbar_redo_tip": "되돌리기를 취소하고 다시 적용합니다 (Ctrl+Y)",
        "status_nothing_to_redo": "다시 적용할 작업이 없습니다.",
        "status_redo_done": "다시하기 완료.",
        "toolbar_help": "사용법",
        "toolbar_about": "정보",
        "toolbar_lang_switch": "English",   # 한국어 모드에서는 전환할 대상 언어명을 보여줌
        "toolbar_lang_switch_tip": "프로그램 언어를 영어로 전환합니다 (재시작 필요)",
        "zoom_out": "축소",
        "zoom_in": "확대",
        "zoom_reset_tip": "화면에 맞춤으로 되돌리기",
        # 언어 전환 / 정보
        "lang_switch_title": "언어 변경",
        "lang_switch_restart_msg": "언어 설정이 변경되었습니다.\n프로그램을 다시 시작하면 적용됩니다.",
        "about_title": "{app} 정보",
        "about_version": "버전 v{version}   ·   릴리스 {date}",
        "about_author": "제작자: 신상규 with Claude\nGitHub: https://github.com/loselessss/BandWagon",
        "about_license_notice": "오픈소스 라이브러리 사용 — 자세한 라이선스 고지는 '사용법' 창 맨 아래를 참고하세요.",
        "zoom_hint": "마우스 휠로 확대/축소 · 드래그(좌클릭/휠버튼)로 이동",
        "chk_show_overlay": "분석 오버레이 표시",
        "chk_show_overlay_tip": "레인 박스·밴드 위치선·MW 값을 화면에서만 켜고 끕니다.\n저장/복사 시에는 그때 다시 묻습니다.",
        "status_ready": "이미지를 열어 시작하세요.   정량은 항상 원본 기준으로 계산됩니다.",
        # 보정 탭
        "group_rotate_flip": "회전 / 반전",
        "rotate_left90": "왼쪽 90°",
        "rotate_right90": "오른쪽 90°",
        "flip_h": "좌우 뒤집기",
        "flip_v": "상하 뒤집기",
        "fine_rotate_label": "정밀",
        "btn_reset": "초기화",
        "fine_rotate_note": "정밀 회전은 보간이 들어가 강도값이 미세하게 바뀌고 모서리가 살짝\n잘릴 수 있습니다 (90°/180°는 무손실). 손을 떼면 그 자리에서 적용되고\n슬라이더 값은 유지됩니다 — '초기화'로 0°로 되돌릴 수 있습니다.",
        "group_crop": "자르기",
        "crop_mode_off": "자르기 모드: 꺼짐",
        "crop_mode_on": "자르기 모드: 켜짐",
        "crop_hint": "이미지 위에서 드래그해 잘라낼 영역을 지정하세요.",
        "crop_no_selection": "선택 영역 없음",
        "crop_apply": "자르기 적용",
        "crop_clear_selection": "선택 초기화",
        "slider_brightness": "밝기",
        "slider_contrast": "대비",
        "btn_invert_colors": "색상 반전",
        "invert_hint": "밝기/대비와 달리 원본에 직접 적용됩니다(밴드 검출에도 영향).",
        "btn_reset_curve": "커브 리셋",
        "btn_reset_adjust_all": "보정 전체 리셋",
        # 레인 탭
        "group_lane_assign": "레인 지정",
        "chk_lane_count": "예상 레인 개수 지정",
        "lane_count_hint": "개수를 알고 있으면 지정하세요 — 농도차가 큰 레인이 섞여 있어도 더 정확히 나뉩니다.",
        "btn_auto_detect_lanes": "레인 자동 검출",
        "section_geometry": "기하 보정 (회전·펴기·곡률·자르기)",
        "section_color": "색감 보정 (밝기·대비·반전·커브)",
        "btn_manual_lane_on": "레인 수동 조정: 켜짐",
        "btn_manual_lane_off": "레인 수동 조정: 꺼짐",
        "lane_manual_hint": "자동 검출이 빗나가면 이미지 위에서 좌우로 드래그해 직접 지정",
        "btn_clear_all_lanes": "레인 전체 삭제",
        "btn_manage_marker_presets": "마커 프리셋 관리",
        "marker_preset_btn_tip": "자주 쓰는 단백질 마커(밴드별 분자량)를 등록/삭제합니다.\n등록해두면 마커 레인의 'MW' 버튼에서 바로 선택할 수 있습니다.",
        "group_vrange": "세로 분석 범위",
        "vrange_intro": "분석할 세로(이동거리) 구간을 지정합니다. 웰이나 염료 전선(dye front)처럼 정량에서 빼고 싶은 위/아래 구간을 제외할 때 씁니다.",
        "btn_vrange_mode_off": "범위 지정: 꺼짐",
        "btn_vrange_mode_on": "범위 지정: 켜짐",
        "vrange_drag_hint": "이미지 위에서 위→아래로 드래그해 범위를 지정하세요. 이미 그려진 줄을 다시 잡으면 그 줄만 따로 미세조정할 수 있습니다.",
        "btn_reset_vrange": "범위 초기화",
        "vrange_label_full": "범위: 전체 ({h}px)",
        "vrange_label_set": "범위: {top}px ~ {bot}px (전체 {h}px 중 {pct}%)",
        "group_band_detect": "밴드 검출",
        "sensitivity_tip": "값이 클수록 더 약한 밴드까지 잡아냅니다(더 민감해짐).",
        "label_sensitivity": "민감도",
        "label_min_band_spacing": "밴드 최소간격(px)",
        "label_band_threshold": "경계 임계값",
        "band_threshold_tip": "밴드 경계(=정량 적분 범위)를 정합니다.\n값이 클수록 피크에 더 가깝게 끊어 경계가 좁아지고,\n작을수록 옆 밴드 쪽으로 더 넓게 잡힙니다.\n밴드가 촘촘해 영역이 서로 겹쳐 보이면 값을 올려보세요.",
        "label_smear_thresh": "최대 밴드 길이",
        "smear_thresh_tip": "밴드 경계 폭(위~아래 길이, px)이 이 값을 넘는 피크는\nsmear(폭 넓게 퍼진 신호)로 보아 결과(표/정량값/MW 계산)에서\n통째로 뺍니다. 0(기본값)이면 끔 — 정상 밴드 폭보다 한참 넓게\n잡아야 진짜 밴드가 같이 잘리지 않습니다.",
        "label_band_display": "밴드 표시 방식",
        "band_style_area": "영역 (경계 박스)",
        "band_style_line": "선 (피크 위치)",
        "btn_run_analysis": "밴드 분석 실행",
        "run_analysis_hint": "레인을 지정한 뒤 분석을 실행하면 이 화면에서 바로 마커 MW를 입력할 수 있습니다.",
        "lane_col_name": "이름",
        "lane_col_type": "유형",
        "lane_col_order_delete": "순서/삭제",
        "tab_lanes": "레인",
        # 분석 탭
        "analysis_tab_note": "정량은 보정 전 원본에서 계산합니다.\n커브·밝기·대비는 결과에 영향을 주지 않습니다.\n밴드 검출/분석 실행은 '레인' 탭으로 옮겼습니다.",
        "mw_regression_placeholder": "MW 회귀: 마커 레인 2개 이상 + MW 입력 필요",
        "col_lane": "레인",
        "col_band": "밴드",
        "col_mw_kda": "MW(kDa)",
        "col_intensity": "강도",
        "col_volume": "Volume",
        "tab_analysis": "분석",
        # 탭 이름
        "tab_adjust": "보정",
        "tab_warp": "펴기",
        "tab_std": "정량",
        # 보정 탭 마무리
        "adjust_display_only_note": "보정은 화면 표시용입니다. 분석값은 바뀌지 않습니다.",
        # 펴기 탭
        "warp_intro": "기울어지거나 구겨진 젤을 직사각형으로 폅니다. 똑바로 찍힌 젤이면 남길 영역의 네 모서리만 찍어 잘라낼 수도 있습니다(자르기 = 직사각형 펴기).\n기하 변환이라 정량값에는 영향이 거의 없습니다.",
        "btn_auto_warp": "젤 영역 자동 인식 후 펴기",
        "warp_or_manual_corners": "또는 직접 코너 지정",
        "btn_corner_mode_off": "젤 영역 지정: 꺼짐",
        "btn_corner_mode_on": "젤 영역 지정: 켜짐",
        "corner_click_order": "이미지 위에서 드래그해 사각형을 만든 뒤, 네 모서리를 끌어 맞추고 '변환 실행'을 누르세요.\n(똑바른 젤이면 그대로 자르기, 기울었으면 펴집니다)",
        "corner_count": "코너 {n}/4",
        "corner_count_auto": "코너 4/4 (자동)",
        "btn_apply_warp": "변환 실행",
        "btn_reset_corners": "코너 초기화",
        "group_region": "자르기 / 펴기",
        "group_bow_correction": "부채꼴(곡률) 보정",
        "bow_correction_info": "그래디언트 젤에서 가운데 레인이 위/아래로 처지는(부채꼴) 휨을 보정합니다.\n슬라이더를 움직이며 밴드 줄이 수평이 되는 지점을 찾으세요.",
        "label_curvature": "곡률",
        "bow_sign_hint": "양수: 가운데가 아래로 처진(웃는 모양) 경우  /  음수: 가운데가 위로 솟은 경우",
        "group_shear_correction": "기울기(전단) 보정",
        "shear_correction_info": "사진이 평행사변형으로 비스듬히 찍혀 위/아래 변의 좌우 위치가 어긋난 경우를 보정합니다.\n슬라이더를 움직이며 레인 경계선이 수직이 되는 지점을 찾으세요.",
        "label_shear": "기울기",
        "shear_sign_hint": "양수: 위쪽이 오른쪽으로 치우친 경우  /  음수: 위쪽이 왼쪽으로 치우친 경우",
        "corner_insufficient_title": "코너 부족",
        "corner_insufficient_msg": "코너 4개가 필요합니다. 현재 {n}개.\n",
        "corner_done_msg": "코너 4개 완료 — 점을 드래그해 조정하거나 '변환 실행'",
        "warp_detect_fail_title": "인식 실패",
        "warp_detect_fail_msg": "젤 영역을 찾지 못했습니다.\n",
        "opencv_required_title": "OpenCV 필요",
        "opencv_required_warp_msg": "펴기 기능은 OpenCV가 필요합니다.\npip install opencv-python",
        "opencv_required_autodetect_msg": "자동 인식은 OpenCV가 필요합니다.\npip install opencv-python",
        "no_image_title": "이미지 없음",
        "no_image_msg": "먼저 이미지를 불러오세요.",
        "std_label_placeholder": "BSA 표준 레인을 지정하고 밴드 분석을 실행하세요.",
        "status_lane_added": "{name} 추가 ({x1}–{x2}px)",
        "status_lane_changed_reanalyze": "레인 위치/폭이 변경되었습니다 — 밴드 분석을 다시 실행하세요.",
        "detect_fail_title": "검출 실패",
        "detect_fail_no_signal": "레인을 구분할 만한 신호가 없습니다. 직접 드래그해 지정하세요.",
        "detect_fail_count_msg": "{n}개로 나눌 만한 신호 굴곡을 찾지 못했습니다. 직접 드래그해 지정하세요.",
        "detect_fail_no_boundary": "레인 경계를 찾지 못했습니다. 직접 드래그해 지정하세요.",
        "status_auto_lane_done": "레인 자동 검출 완료 — {n}개",
        "lane_kind_sample": "일반",
        "lane_kind_marker": "마커",
        "lane_kind_bsa": "BSA",
        "btn_delete": "삭제",
        "delete_this_lane_tip": "이 레인 삭제",
        "status_lane_reordered": "레인 순서를 변경했습니다.",
        "status_lane_deleted": "{name} 삭제됨 — 남은 레인 {n}개",
        "status_lanes_cleared": "레인을 전부 삭제했습니다.",
        "bsa_conc_title": "BSA 농도",
        "bsa_conc_label": "{name}의 BSA 양 (μg):",
        "no_bands_title": "밴드 없음",
        "no_bands_run_analysis_msg": "먼저 '분석' 탭에서 밴드 분석을 실행하세요.",
        "status_presets_saved": "마커 프리셋 {n}개 저장됨.",
        "no_lanes_title": "레인 없음",
        "no_lanes_msg": "'레인' 탭에서 레인을 먼저 지정하세요.",
        "status_analysis_done": "분석 완료 — 밴드 {n}개 검출 (원본 기준)",
        "status_analysis_done_smear": "분석 완료 — 밴드 {n}개 검출 (원본 기준, smear {s}개 제외)",
        "mw_interp_result": "MW 보간(PCHIP)  참고 R²(선형 기준) = {r2:.4f}   (마커 {n_markers}레인, 기준점 {n_points}개)",
        "status_mw_interp_done": "MW 보간 완료  참고 R²={r2:.4f}  (마커 {n_markers}레인)",
        "std_need_more_lanes": "BSA 표준 레인 2개 이상 + 밴드 분석이 필요합니다.",
        "std_sample_est_line": "{name}: {est:.2f} μg",
        "std_curve_summary": "표준곡선 (volume 기준)\nR² = {r2:.4f}\n농도 = {slope:.4g}×volume + {icept:.3g}",
        "std_sample_est_header": "[샘플 추정 농도]",
        "crop_selected_size": "선택: {w:.0f}×{h:.0f}px",
        "crop_select_first_msg": "이미지 위에서 드래그해 자를 영역을 먼저 지정하세요.",
        "crop_too_small_title": "영역이 너무 작음",
        "crop_too_small_msg": "잘라낼 영역이 너무 작습니다. 다시 지정해 주세요.",
        "status_crop_done": "자르기 완료 — {w:.0f}×{h:.0f}px",
        "auto_detect_done_title": "자동 인식 완료",
        "auto_detect_done_msg": "젤 영역을 인식했습니다. 표시된 코너로 펴시겠습니까?\n아니요를 누르면 코너를 드래그해 조정할 수 있습니다.",
        "status_warp_done": "펴기 완료 — {w}×{h}px",
        "dlg_open_image_title": "이미지 열기",
        "clipboard_source_name": "클립보드",
        "clipboard_empty_msg": "클립보드에 이미지가 없습니다.",
        "open_failed_title": "열기 실패",
        "export_image_title": "이미지 내보내기",
        "export_image_question": "어떤 이미지를 내보낼까요?",
        "export_plain": "사진만",
        "export_with_overlay": "분석 포함(합성)",
        "btn_cancel": "취소",
        "nothing_to_copy_msg": "복사할 이미지가 없습니다.",
        "status_copied_to_clipboard": "결과를 클립보드에 복사했습니다.",
        "status_table_copied": "선택한 표 내용을 복사했습니다.",
        "overlay_included_suffix": " (분석 포함)",
        "nothing_to_save_msg": "저장할 이미지가 없습니다.",
        "default_filename_with_overlay": "gel_result_분석포함.png",
        "status_saved": "저장됨: {path}",
        "gelproj_filter": "BandWagon 프로젝트 (*.bandwagon)",
        "status_project_saved": "프로젝트 저장됨: {path}",
        "project_save_failed_title": "프로젝트 저장 실패",
        "version_warning_title": "버전 경고",
        "version_warning_msg": "이 프로젝트 파일은 더 최신 버전의 프로그램에서 저장되었습니다.\n일부 정보가 무시될 수 있습니다.",
        "status_project_loaded": "프로젝트 불러옴: {path}  (레인 {n}개)",
        "gelproj_invalid_msg": "올바른 .bandwagon 파일이 아닙니다(필수 항목 누락).",
        "project_open_failed_title": "프로젝트 열기 실패",
        "run_analysis_first_msg": "먼저 밴드 분석을 실행하세요.",
        "status_csv_saved": "CSV 저장됨: {path}",
        "status_reset_to_loaded": "불러온 이미지를 기준으로 모든 편집을 초기화했습니다.",
        "status_reset_done": "초기화되었습니다.",
        # 부팅 스플래시
        "splash_loading_ui": "화면을 그리는 중...",
        "splash_loading_tabs": "탭 구성 중...",
        "splash_tab_adjust": "보정 도구 불러오는 중...",
        "splash_tab_warp": "펴기 도구 불러오는 중...",
        "splash_tab_lanes": "레인 도구 불러오는 중...",
        "splash_tab_analysis": "분석 도구 불러오는 중...",
        "splash_tab_std": "표준곡선 도구 불러오는 중...",
        "splash_almost_done": "거의 다 됐습니다...",
        # 합성 탭
        "composite_studio_title": "웨스턴 블롯 합성 스튜디오",
        "composite_intro": "가시광 사진(마커가 보이는 일반 사진)과 UV 사진(밴드가 보이는 형광 사진)을 코너 4점으로 정렬해 합성합니다.\n합성 결과를 .bwcomposite 파일로 내보낸 뒤, 메인 창의 '합성 불러오기'로 열어 밴드 분석을 합니다.",
        "composite_btn_export": "합성 내보내기 (.bwcomposite)",
        "composite_export_hint": "화면용 블렌드와 분석용 UV 그레이스케일이 한 파일에 함께 저장됩니다.",
        "composite_file_filter": "BandWagon 합성 파일 (*.bwcomposite)",
        "composite_import_title": "합성 파일 불러오기",
        "composite_import_failed_title": "합성 파일 열기 실패",
        "composite_open_now_title": "지금 분석할까요?",
        "composite_open_now_msg": "방금 내보낸 합성 파일을 바로 불러와 밴드 분석을 시작할까요?",
        "status_composite_imported": "합성 불러오기 완료: {path} — 분석은 UV 신호 기준입니다.",
        "wb_group_load": "1. 사진 불러오기",
        "wb_caption_visible": "가시광",
        "wb_caption_uv": "UV",
        "wb_thumb_click_hint": "빈 썸네일을 클릭해 불러오거나 붙여넣으세요. 이미 불러온 썸네일을 클릭하면 원본을 크게 볼 수 있습니다.",
        "wb_thumb_empty": "없음",
        "wb_pick_source_title": "사진 불러오기",
        "wb_pick_source_msg": "어떻게 불러올까요?",
        "wb_pick_source_file": "파일에서 열기",
        "wb_pick_source_paste": "클립보드에서 붙여넣기",
        "wb_btn_load_visible": "가시광 사진 열기",
        "wb_btn_load_uv": "UV 사진 열기",
        "wb_group_align": "2. 정렬 (UV 코너 지정)",
        "wb_corner_hint": "UV 사진 위에서 드래그해 사각형을 만든 뒤 네 모서리를 끌어 맞추세요. 가시광 사진이 그 영역에 어떻게 겹쳐지는지 이 화면에서 바로 보입니다.",
        "wb_opacity_label": "가시광 투명도",
        "wb_opacity_hint": "슬라이더를 움직이면 위 캔버스에 겹쳐 보이는 가시광 사진의 투명도가 바로 바뀝니다.",
        "wb_need_visible_title": "가시광 사진 필요",
        "wb_need_visible_msg": "먼저 가시광 사진을 불러오세요.",
        "wb_need_uv_corners_title": "UV 코너 필요",
        "wb_need_uv_corners_msg": "UV 사진을 불러오고 코너 4점을 지정하세요.",
        "wb_apply_failed_title": "합성 실패",
        "wb_reference_dialog_title": "가시광 원본",
        "wb_uv_reference_dialog_title": "UV 원본",
        "btn_yes": "예",
        "btn_no": "아니요",
        "status_image_info": "{w}×{h}px   밝기 {bright:+d}  대비 {contrast:+d}   |  정량은 원본 기준",
        "status_color_inverted": "색상을 반전했습니다 — 밴드 검출 결과에 영향이 있을 수 있습니다.",
        "status_fine_rotation_applied": "정밀 회전 적용 — 보간으로 강도값이 미세하게 변하고 모서리가 살짝 잘릴 수 있습니다.",
        "status_fine_rotation_reset": "정밀 회전을 초기화했습니다.",
        "status_bow_applied": "부채꼴 보정 적용 — 보간으로 강도값이 미세하게 변할 수 있습니다.",
        "status_bow_reset": "부채꼴 보정을 초기화했습니다.",
        "status_shear_applied": "기울기 보정 적용 — 보간으로 강도값이 미세하게 변할 수 있습니다.",
        "status_shear_reset": "기울기 보정을 초기화했습니다.",
        "status_nothing_to_undo": "되돌릴 작업이 없습니다.",
        "status_undo_done": "되돌리기 완료 — 남은 단계 {n}",
        "curve_io_label": "입력 {ix:>3}   출력 {iy:>3}",
        "corner_name_tl": "1 좌상",
        "corner_name_tr": "2 우상",
        "corner_name_br": "3 우하",
        "corner_name_bl": "4 좌하",
        "help_html":
            "<h3>기본 흐름</h3>"
            "<p>이미지 열기 -> (필요시) <b>보정/펴기</b>로 다듬기 -> <b>레인</b>에서 레인 지정 후 분석 "
            "-> 마커 MW 입력 -> <b>정량</b>·<b>분석</b> 탭에서 결과 확인 -> 저장</p>"

            "<h3>이미지 불러오기 / 저장</h3>"
            "<p>"
            "· <b>열기</b>: 파일 선택, <b>붙여넣기</b>: 클립보드 이미지 그대로 사용(Ctrl+V도 가능)<br>"
            "· <b>결과 이미지 복사 / 결과 이미지 저장</b>: 분석 결과가 있으면 '사진만' / '분석 포함(합성)' 중 선택<br>"
            "· <b>CSV 내보내기</b>: 밴드별 MW·강도·Volume 표 저장<br>"
            "· <b>되돌리기(Ctrl+Z)</b>: 회전·반전·자르기·펴기·색상반전·곡률보정을 한 단계씩 취소"
            "</p>"

            "<h3>프로젝트 저장 / 불러오기 (.bandwagon)</h3>"
            "<p>"
            "· <b>프로젝트 저장(Ctrl+S)</b>: 현재 이미지 + 밝기/대비/톤커브 + 레인 구성 + "
            "분석 파라미터를 파일 하나(.bandwagon)에 통째로 저장<br>"
            "· <b>프로젝트 열기(Ctrl+Shift+O)</b>: 저장된 .bandwagon 파일을 불러와 그 상태에서 이어서 작업<br>"
            "· '결과 이미지 저장'(PNG)과는 다릅니다 — PNG는 보기용 최종 이미지 한 장이고, "
            ".bandwagon은 다시 열어 레인·커브·분석을 수정할 수 있는 작업 파일입니다."
            "</p>"

            "<h3>화면 보기</h3>"
            "<p>"
            "· 마우스 휠: 확대/축소 (커서 위치 기준)<br>"
            "· 좌클릭 드래그(기본 상태) 또는 휠버튼 드래그: 화면 이동<br>"
            "· '분석 오버레이 표시' 체크: 레인 박스·밴드선·MW 표시를 화면에서만 켜고 끄기"
            "</p>"

            "<h3>펴기 탭</h3>"
            "<p>기울어지거나 사다리꼴로 찍힌 젤을 직사각형으로 폅니다. "
            "자동 인식이 안 맞으면 코너 지정 모드를 켜고 이미지 위에서 드래그해 "
            "사각형을 만든 뒤 <b>네 모서리를 끌어</b> 맞추세요.<br>"
            "그래디언트 젤 특유의 부채꼴(가운데가 처지거나 솟는) 휨은 "
            "'부채꼴(곡률) 보정' 슬라이더로 라이브 미리보기를 보며 조정합니다.</p>"

            "<h3>보정 탭</h3>"
            "<p>회전(90°/180°/정밀회전) · 좌우·상하 반전 · 자르기 · 색상 반전 · 밝기/대비.<br>"
            "밝기·대비는 화면 표시용일 뿐 분석 결과에는 영향을 주지 않습니다. "
            "나머지(회전·반전·자르기·색상반전)는 원본 자체를 바꾸므로 분석에도 반영됩니다.</p>"

            "<h3>합성 탭</h3>"
            "<p>가시광 사진(마커가 보이는 일반 사진)과 UV 사진(밴드가 보이는 형광 사진)을 "
            "정렬해 하나로 합칩니다. 빈 썸네일을 클릭해 파일에서 열거나 클립보드에서 "
            "붙여넣어 두 사진을 불러오세요. 이미 불러온 썸네일을 클릭하면 원본을 크게 "
            "볼 수 있습니다.<br>"
            "두 사진을 모두 불러왔으면, 아래 캔버스에서 <b>UV 사진 위에</b> 드래그해 "
            "사각형을 만든 뒤 네 모서리를 끌어 맞추세요. 그 즉시 같은 화면에 가시광 사진이 "
            "그 영역에 어떻게 겹쳐지는지 실시간으로 함께 보입니다. '가시광 투명도' "
            "슬라이더로 겹쳐 보이는 정도를 조절하며 정렬을 맞추다가, 맞으면 '합성 결과를 "
            "메인 이미지로 적용'을 누르세요.<br>"
            "적용 후에는 화면에 두 사진을 섞은 합성 이미지가 보이지만, "
            "<b>실제 밴드 분석은 UV 신호만으로 계산</b>됩니다 — 가시광 사진의 마커 글자나 "
            "종이 배경이 밴드로 오검출되는 것을 막기 위함입니다. "
            "가시광/UV 원본은 각 썸네일을 다시 클릭해 언제든 확인할 수 있습니다.</p>"

            "<h3>레인 탭</h3>"
            "<p>"
            "· <b>레인 자동 검출</b>: 레인 개수를 알면 체크박스로 지정 시 더 정확합니다<br>"
            "· <b>레인 수동 조정</b> 켜고 이미지 위에서 좌우 드래그 = 레인 추가<br>"
            "· 레인 경계선 드래그 = 폭 조정, 레인 이름(라벨) 드래그 = 레인 통째로 이동<br>"
            "· 테이블에서 유형을 '마커'로 바꾸면 MW 입력창이 바로 열립니다(다시 선택하면 재오픈)<br>"
            "· 민감도는 <b>값이 클수록 더 약한 밴드까지</b> 검출합니다<br>"
            "· <b>경계 임계값</b>: 밴드 경계(=정량 적분 범위)를 조절합니다. 값이 클수록 "
            "피크에 더 가깝게 끊어 경계가 좁아지고, 밴드가 촘촘해 경계 영역이 서로 "
            "겹쳐 보이면 값을 올리면 해결됩니다. 정량값(강도·Volume)도 이 값에 따라 "
            "함께 바뀝니다<br>"
            "· <b>밴드 표시 방식</b>: '영역'(경계 박스, 기본)과 '선'(피크 위치 한 줄) 중 "
            "고를 수 있습니다 — 표시만 바뀌고 정량값에는 영향이 없습니다<br>"
            "· '밴드 분석 실행'으로 검출 후 Up/Dn/삭제로 레인 순서·구성 조정"
            "</p>"

            "<h3>분석 / 정량 탭</h3>"
            "<p>검출된 밴드의 MW·강도·Volume 표를 보여줍니다. "
            "MW는 마커 레인에 입력한 값을 기준으로 곡선 보간하여 계산되며, "
            "정량 계산은 항상 보정 전 원본 데이터를 사용합니다.</p>"

            "<h3>마커 프리셋</h3>"
            "<p>자주 쓰는 마커(밴드별 분자량)를 등록해두면 다음에 같은 마커를 쓸 때 "
            "'관리…'에서 선택만으로 자동 입력됩니다. 밴드 개수가 다르면 수동으로 매칭할 수 있습니다.</p>"

            "<h3>오픈소스 라이선스 고지</h3>"
            "<p style='font-size:11px;'>"
            "{app}은 다음 오픈소스 라이브러리를 사용합니다:<br>"
            "· <b>PyQt5</b> — GPL v3 (이 프로그램 또한 소스코드를 공개하여 호환성을 유지합니다)<br>"
            "· <b>NumPy</b>, <b>SciPy</b>, <b>Pillow</b> — BSD 계열 허가형 라이선스<br>"
            "· <b>OpenCV</b> — Apache License 2.0<br>"
            "각 라이브러리는 해당 프로젝트의 저작권자에게 권리가 있으며, "
            "이 프로그램은 그 라이브러리들을 비수정 상태로 활용만 합니다."
            "</p>",
    },
    "en": {
        # MarkerDialog
        "marker_dialog_title": "Enter Marker MW (kDa)",
        "preset_label": "Preset:",
        "preset_manual_entry": "Manual entry",
        "preset_manage_btn": "Manage…",
        "marker_hint_default": "{n} band(s) detected. Enter molecular weight (kDa) top to bottom.",
        "marker_hint_matched": "Applied '{name}' — {n} band(s) matched and filled in automatically. You can still edit the values.",
        "marker_hint_mismatch": "'{name}' has {preset_n} band(s), but {n} were detected. Please match each detected band to a preset value.",
        "preset_match_row_label": "  Match:",
        # MarkerPresetManager
        "preset_manager_title": "Manage Marker Presets",
        "preset_col_name": "Name",
        "preset_col_bands": "Bands (kDa, high->low)",
        "preset_add_btn": "Add…",
        "preset_remove_btn": "Remove Selected",
        "preset_add_title": "Add Preset",
        "preset_add_name_label": "Preset name:",
        "preset_add_mw_label": "Enter molecular weights from highest to lowest, comma-separated (e.g. 250,130,95,70,55,35,25,15):",
        "input_error_title": "Input Error",
        "preset_mw_parse_error": "Please enter numbers separated by commas.",
        # GelView / ProfileView / StdCurveView
        "canvas_empty_hint": "Open an image or paste with Ctrl+V\n(drag & drop also works)",
        "profile_title": "Density Profile (raw image)",
        "profile_empty_hint": "Run band analysis to see per-lane curves here",
        "std_curve_empty_hint": "A standard curve appears once 2+ BSA standard lanes are analyzed",
        # Toolbar
        "toolbar_open": "Open",
        "toolbar_paste": "Paste",
        "toolbar_project_open": "Open Project",
        "toolbar_project_open_tip": "Load a saved .bandwagon project (original image + overlay/analysis state). (Ctrl+Shift+O)",
        "toolbar_project_save": "Save Project",
        "toolbar_project_save_tip": "Save the current image plus all adjustments, lanes, and analysis state into one .bandwagon file.\nReopen it later with 'Open Project' to keep working. (Ctrl+S)",
        "toolbar_composite_studio": "Composite Studio",
        "toolbar_composite_studio_tip": "Open a separate window to align and blend a visible-light + UV photo.\nExport the result as a .bwcomposite file, then use 'Import Composite' to analyze it.",
        "toolbar_composite_import": "Import Composite",
        "toolbar_composite_import_tip": "Open a .bwcomposite file exported from Composite Studio and start band analysis.",
        "toolbar_copy_result": "Copy Result Image",
        "toolbar_copy_result_tip": "Copy the current image to the clipboard (asks whether to include analysis overlay, if any).",
        "toolbar_save_result": "Save Result Image",
        "toolbar_save_result_tip": "Save the current image to a file (asks whether to include analysis overlay, if any).",
        "toolbar_export_csv": "Export CSV",
        "toolbar_reset_all": "Reset All",
        "toolbar_undo": "Undo",
        "toolbar_undo_tip": "Undo the last rotate/flip/crop/warp (Ctrl+Z)",
        "toolbar_redo": "Redo",
        "toolbar_redo_tip": "Cancel the undo and reapply it (Ctrl+Y)",
        "status_nothing_to_redo": "Nothing to redo.",
        "status_redo_done": "Redo complete.",
        "toolbar_help": "Help",
        "toolbar_about": "About",
        "toolbar_lang_switch": "한국어",   # In English mode, show the target language name to switch to
        "toolbar_lang_switch_tip": "Switch the app language to Korean (restart required)",
        "zoom_out": "Out",
        "zoom_in": "In",
        "zoom_reset_tip": "Reset to fit screen",
        # Language switch / About
        "lang_switch_title": "Language Changed",
        "lang_switch_restart_msg": "The language setting has changed.\nRestart the program for it to take effect.",
        "about_title": "About {app}",
        "about_version": "Version v{version}   ·   Released {date}",
        "about_author": "Author: Sangkyu Shin with Claude\nGitHub: https://github.com/loselessss/BandWagon",
        "about_license_notice": "Uses open-source libraries — see the bottom of the 'Help' window for full license notices.",
        "zoom_hint": "Mouse wheel to zoom · drag (left-click or middle button) to pan",
        "chk_show_overlay": "Show analysis overlay",
        "chk_show_overlay_tip": "Toggles lane boxes/band lines/MW labels on screen only.\nYou'll be asked again when saving/copying.",
        "status_ready": "Open an image to get started.   Quantification is always computed from the raw image.",
        # Adjust tab
        "group_rotate_flip": "Rotate / Flip",
        "rotate_left90": "Rotate Left 90°",
        "rotate_right90": "Rotate Right 90°",
        "flip_h": "Flip Horizontal",
        "flip_v": "Flip Vertical",
        "fine_rotate_label": "Fine",
        "btn_reset": "Reset",
        "fine_rotate_note": "Fine rotation uses interpolation, so intensity values shift slightly and\ncorners may be slightly cropped (90°/180° are lossless). Releasing the\nslider applies it immediately and the value is kept — use 'Reset' to\nreturn to 0°.",
        "group_crop": "Crop",
        "crop_mode_off": "Crop Mode: Off",
        "crop_mode_on": "Crop Mode: On",
        "crop_hint": "Drag on the image to select the area to crop.",
        "crop_no_selection": "No selection",
        "crop_apply": "Apply Crop",
        "crop_clear_selection": "Clear Selection",
        "slider_brightness": "Brightness",
        "slider_contrast": "Contrast",
        "btn_invert_colors": "Invert Colors",
        "invert_hint": "Unlike brightness/contrast, this is applied to the original image (affects band detection too).",
        "btn_reset_curve": "Reset Curve",
        "btn_reset_adjust_all": "Reset All Adjustments",
        # Lanes tab
        "group_lane_assign": "Lane Assignment",
        "chk_lane_count": "Specify expected lane count",
        "lane_count_hint": "If you know the count, set it — splitting is more accurate even when lane intensities vary a lot.",
        "btn_auto_detect_lanes": "Auto-Detect Lanes",
        "section_geometry": "Geometry (rotate, straighten, curvature, crop)",
        "section_color": "Color (brightness, contrast, invert, curve)",
        "btn_manual_lane_on": "Manual Lane Mode: On",
        "btn_manual_lane_off": "Manual Lane Mode: Off",
        "lane_manual_hint": "If auto-detection misses, drag left-right on the image to add lanes manually",
        "btn_clear_all_lanes": "Clear All Lanes",
        "btn_manage_marker_presets": "Manage Marker Presets",
        "marker_preset_btn_tip": "Add/remove frequently-used protein markers (molecular weight per band).\nOnce saved, you can select them directly from the 'MW' button on a marker lane.",
        "group_vrange": "Vertical Analysis Range",
        "vrange_intro": "Restrict band detection to a vertical (migration-distance) window — e.g. to exclude the wells or the dye front from quantification.",
        "btn_vrange_mode_off": "Range Mode: Off",
        "btn_vrange_mode_on": "Range Mode: On",
        "vrange_drag_hint": "Drag top-to-bottom on the image to set the range. Grab an existing line again to fine-tune just that one.",
        "btn_reset_vrange": "Reset Range",
        "vrange_label_full": "Range: Full ({h}px)",
        "vrange_label_set": "Range: {top}px - {bot}px ({pct}% of {h}px)",
        "group_band_detect": "Band Detection",
        "sensitivity_tip": "Higher values detect even weaker bands (more sensitive).",
        "label_sensitivity": "Sensitivity",
        "label_min_band_spacing": "Min. band spacing (px)",
        "label_band_threshold": "Boundary Threshold",
        "band_threshold_tip": "Sets the band boundary (= quantification integration range).\nHigher values cut closer to the peak (narrower boundary);\nlower values extend further toward neighboring bands.\nIf bands are crowded and areas overlap visually, try raising this.",
        "label_smear_thresh": "Max Band Length",
        "smear_thresh_tip": "Any peak whose boundary width (top-to-bottom length, px) exceeds\nthis value is treated as smear (a broadly spread signal) and removed\nentirely from the results (table/quantification/MW calculation).\n0 (default) disables this — set it well above a normal band's width\nso real bands aren't cut along with the smear.",
        "label_band_display": "Band Display Style",
        "band_style_area": "Area (boundary box)",
        "band_style_line": "Line (peak position)",
        "btn_run_analysis": "Run Band Analysis",
        "run_analysis_hint": "After assigning lanes, run analysis to enter marker MW values right here.",
        "lane_col_name": "Name",
        "lane_col_type": "Type",
        "lane_col_order_delete": "Order/Delete",
        "tab_lanes": "Lanes",
        # Analysis tab
        "analysis_tab_note": "Quantification is always computed from the raw image, before adjustments.\nCurve/brightness/contrast do not affect results.\nBand detection/analysis now lives in the 'Lanes' tab.",
        "mw_regression_placeholder": "MW regression: needs 2+ marker lanes with MW values entered",
        "col_lane": "Lane",
        "col_band": "Band",
        "col_mw_kda": "MW (kDa)",
        "col_intensity": "Intensity",
        "col_volume": "Volume",
        "tab_analysis": "Analysis",
        # Tab names
        "tab_adjust": "Adjust",
        "tab_warp": "Warp",
        "tab_std": "Standard Curve",
        # Adjust tab wrap-up
        "adjust_display_only_note": "Adjustments are for on-screen display only. Analysis values are unaffected.",
        # Warp tab
        "warp_intro": "Straighten a tilted or skewed gel into a rectangle. For an already-straight gel, just place the 4 corners of the area you want to keep to crop it (cropping = warping a rectangle).\nThis is a geometric transform, so it barely affects quantification.",
        "btn_auto_warp": "Auto-Detect Gel Area & Warp",
        "warp_or_manual_corners": "Or set corners manually",
        "btn_corner_mode_off": "Gel Area Mode: Off",
        "btn_corner_mode_on": "Gel Area Mode: On",
        "corner_click_order": "Drag a rectangle on the image, then drag the 4 corners to fit and press 'Apply Warp'.\n(A straight gel is simply cropped; a tilted one is straightened.)",
        "corner_count": "Corners {n}/4",
        "corner_count_auto": "Corners 4/4 (auto)",
        "btn_apply_warp": "Apply Warp",
        "btn_reset_corners": "Reset Corners",
        "group_region": "Crop / Warp",
        "group_bow_correction": "Bow (Curvature) Correction",
        "bow_correction_info": "Corrects the bow where the center lane sags up/down on gradient gels.\nMove the slider until the band rows look horizontal.",
        "label_curvature": "Bow",
        "bow_sign_hint": "Positive: center sags downward (smile shape)  /  Negative: center rises upward",
        "group_shear_correction": "Shear (Skew) Correction",
        "shear_correction_info": "Corrects a parallelogram-shaped photo where the top and bottom edges are horizontally offset.\nMove the slider until the lane boundaries look vertical.",
        "label_shear": "Shear",
        "shear_sign_hint": "Positive: top shifted right  /  Negative: top shifted left",
        "corner_insufficient_title": "Not Enough Corners",
        "corner_insufficient_msg": "4 corners are required. Currently have {n}.\n",
        "corner_done_msg": "4 corners set — drag points to adjust, or click 'Apply Warp'",
        "warp_detect_fail_title": "Detection Failed",
        "warp_detect_fail_msg": "Couldn't find the gel area.\n",
        "opencv_required_title": "OpenCV Required",
        "opencv_required_warp_msg": "Warp requires OpenCV.\npip install opencv-python",
        "opencv_required_autodetect_msg": "Auto-detection requires OpenCV.\npip install opencv-python",
        "no_image_title": "No Image",
        "no_image_msg": "Please open an image first.",
        "std_label_placeholder": "Assign BSA standard lanes and run band analysis.",
        "status_lane_added": "Added {name} ({x1}–{x2}px)",
        "status_lane_changed_reanalyze": "Lane position/width changed — please run band analysis again.",
        "detect_fail_title": "Detection Failed",
        "detect_fail_no_signal": "No clear signal to separate lanes. Please drag to assign lanes manually.",
        "detect_fail_count_msg": "Couldn't find enough signal dips to split into {n} lanes. Please drag to assign lanes manually.",
        "detect_fail_no_boundary": "Couldn't find lane boundaries. Please drag to assign lanes manually.",
        "status_auto_lane_done": "Auto lane detection complete — {n} lane(s)",
        "lane_kind_sample": "Sample",
        "lane_kind_marker": "Marker",
        "lane_kind_bsa": "BSA",
        "btn_delete": "Delete",
        "delete_this_lane_tip": "Delete this lane",
        "status_lane_reordered": "Lane order changed.",
        "status_lane_deleted": "Deleted {name} — {n} lane(s) remaining",
        "status_lanes_cleared": "All lanes cleared.",
        "bsa_conc_title": "BSA Concentration",
        "bsa_conc_label": "BSA amount for {name} (μg):",
        "no_bands_title": "No Bands",
        "no_bands_run_analysis_msg": "Please run band analysis in the 'Analysis' tab first.",
        "status_presets_saved": "Saved {n} marker preset(s).",
        "no_lanes_title": "No Lanes",
        "no_lanes_msg": "Please assign lanes in the 'Lanes' tab first.",
        "status_analysis_done": "Analysis complete — {n} band(s) detected (raw image)",
        "status_analysis_done_smear": "Analysis complete — {n} band(s) detected (raw image, {s} smear excluded)",
        "mw_interp_result": "MW interpolation (PCHIP)  ref. R² (linear) = {r2:.4f}   ({n_markers} marker lane(s), {n_points} reference point(s))",
        "status_mw_interp_done": "MW interpolation done  ref. R²={r2:.4f}  ({n_markers} marker lane(s))",
        "std_need_more_lanes": "Need 2+ BSA standard lanes plus band analysis.",
        "std_sample_est_line": "{name}: {est:.2f} μg",
        "std_curve_summary": "Standard Curve (by volume)\nR² = {r2:.4f}\nConcentration = {slope:.4g}×volume + {icept:.3g}",
        "std_sample_est_header": "[Estimated Sample Concentrations]",
        "crop_selected_size": "Selected: {w:.0f}×{h:.0f}px",
        "crop_select_first_msg": "Please drag on the image to select an area to crop first.",
        "crop_too_small_title": "Selection Too Small",
        "crop_too_small_msg": "The selected area is too small. Please select again.",
        "status_crop_done": "Crop complete — {w:.0f}×{h:.0f}px",
        "auto_detect_done_title": "Auto-Detection Complete",
        "auto_detect_done_msg": "Detected the gel area. Warp using the shown corners?\nChoose No to drag the corners and adjust them first.",
        "status_warp_done": "Warp complete — {w}×{h}px",
        "dlg_open_image_title": "Open Image",
        "clipboard_source_name": "Clipboard",
        "clipboard_empty_msg": "No image found on the clipboard.",
        "open_failed_title": "Failed to Open",
        "export_image_title": "Export Image",
        "export_image_question": "Which image would you like to export?",
        "export_plain": "Image Only",
        "export_with_overlay": "With Analysis Overlay",
        "btn_cancel": "Cancel",
        "nothing_to_copy_msg": "No image to copy.",
        "status_copied_to_clipboard": "Result copied to clipboard.",
        "status_table_copied": "Copied selected cells.",
        "overlay_included_suffix": " (with overlay)",
        "nothing_to_save_msg": "No image to save.",
        "default_filename_with_overlay": "gel_result_with_overlay.png",
        "status_saved": "Saved: {path}",
        "gelproj_filter": "BandWagon Project (*.bandwagon)",
        "status_project_saved": "Project saved: {path}",
        "project_save_failed_title": "Failed to Save Project",
        "version_warning_title": "Version Warning",
        "version_warning_msg": "This project file was saved by a newer version of the program.\nSome information may be ignored.",
        "status_project_loaded": "Project loaded: {path}  ({n} lane(s))",
        "gelproj_invalid_msg": "Not a valid .bandwagon file (missing required entries).",
        "project_open_failed_title": "Failed to Open Project",
        "run_analysis_first_msg": "Please run band analysis first.",
        "status_csv_saved": "CSV saved: {path}",
        "status_reset_to_loaded": "Reset all edits back to the originally loaded image.",
        "status_reset_done": "Reset complete.",
        # Boot splash
        "splash_loading_ui": "Drawing the screen...",
        "splash_loading_tabs": "Building tabs...",
        "splash_tab_adjust": "Loading adjust tools...",
        "splash_tab_warp": "Loading warp tools...",
        "splash_tab_lanes": "Loading lane tools...",
        "splash_tab_analysis": "Loading analysis tools...",
        "splash_tab_std": "Loading standard curve tools...",
        "splash_almost_done": "Almost done...",
        # Composite tab
        "composite_studio_title": "Western Blot Composite Studio",
        "composite_intro": "Align a visible-light photo (showing markers) with a UV photo (showing fluorescent bands) using 4 corner points, then blend them.\nExport the result as a .bwcomposite file, then open it with 'Import Composite' in the main window to run band analysis.",
        "composite_btn_export": "Export Composite (.bwcomposite)",
        "composite_export_hint": "The display blend and the analysis-only UV grayscale are saved together in one file.",
        "composite_file_filter": "BandWagon Composite (*.bwcomposite)",
        "composite_import_title": "Import Composite File",
        "composite_import_failed_title": "Failed to Open Composite File",
        "composite_open_now_title": "Analyze Now?",
        "composite_open_now_msg": "Open the composite file you just exported and start band analysis right away?",
        "status_composite_imported": "Composite imported: {path} — analysis is based on UV signal.",
        "wb_group_load": "1. Load Photos",
        "wb_caption_visible": "Visible",
        "wb_caption_uv": "UV",
        "wb_thumb_click_hint": "Click an empty thumbnail to load or paste a photo. Click a loaded thumbnail to view the original larger.",
        "wb_thumb_empty": "None",
        "wb_pick_source_title": "Load Photo",
        "wb_pick_source_msg": "How would you like to load it?",
        "wb_pick_source_file": "Open from File",
        "wb_pick_source_paste": "Paste from Clipboard",
        "wb_btn_load_visible": "Open Visible-Light Photo",
        "wb_btn_load_uv": "Open UV Photo",
        "wb_group_align": "2. Align (Set UV Corners)",
        "wb_corner_hint": "Drag a rectangle on the UV photo, then drag the 4 corners to fit. You'll see right here how the visible-light photo overlays that area.",
        "wb_opacity_label": "Visible-Light Opacity",
        "wb_opacity_hint": "Moving the slider instantly changes how transparent the overlaid visible-light photo is in the canvas above.",
        "wb_need_visible_title": "Visible-Light Photo Needed",
        "wb_need_visible_msg": "Please load a visible-light photo first.",
        "wb_need_uv_corners_title": "UV Corners Needed",
        "wb_need_uv_corners_msg": "Please load a UV photo and set 4 corner points.",
        "wb_apply_failed_title": "Composite Failed",
        "wb_reference_dialog_title": "Original Visible-Light Photo",
        "wb_uv_reference_dialog_title": "Original UV Photo",
        "btn_yes": "Yes",
        "btn_no": "No",
        "status_image_info": "{w}×{h}px   brightness {bright:+d}  contrast {contrast:+d}   |  quantification uses raw image",
        "status_color_inverted": "Colors inverted — this may affect band detection results.",
        "status_fine_rotation_applied": "Fine rotation applied — interpolation slightly shifts intensity values and corners may be slightly cropped.",
        "status_fine_rotation_reset": "Fine rotation reset.",
        "status_bow_applied": "Bow correction applied — interpolation may slightly shift intensity values.",
        "status_bow_reset": "Bow correction reset.",
        "status_shear_applied": "Shear correction applied — interpolation may slightly shift intensity values.",
        "status_shear_reset": "Shear correction reset.",
        "status_nothing_to_undo": "Nothing to undo.",
        "status_undo_done": "Undo complete — {n} step(s) remaining",
        "curve_io_label": "in {ix:>3}   out {iy:>3}",
        "corner_name_tl": "1 TL",
        "corner_name_tr": "2 TR",
        "corner_name_br": "3 BR",
        "corner_name_bl": "4 BL",
        "help_html":
            "<h3>Basic Workflow</h3>"
            "<p>Open an image -> (if needed) clean up in <b>Adjust/Warp</b> -> assign lanes in <b>Lanes</b> and run analysis "
            "-> enter marker MW -> check results in <b>Standard Curve</b>/<b>Analysis</b> -> save</p>"

            "<h3>Opening / Saving Images</h3>"
            "<p>"
            "· <b>Open</b>: choose a file. <b>Paste</b>: use a clipboard image directly (Ctrl+V works too)<br>"
            "· <b>Copy Result Image / Save Result Image</b>: if there are analysis results, choose 'image only' or 'with overlay'<br>"
            "· <b>Export CSV</b>: save a table of MW/intensity/volume per band<br>"
            "· <b>Undo (Ctrl+Z)</b>: undo rotate/flip/crop/warp/invert/bow-correction one step at a time"
            "</p>"

            "<h3>Save / Open Project (.bandwagon)</h3>"
            "<p>"
            "· <b>Save Project (Ctrl+S)</b>: save the current image plus brightness/contrast/tone curve/lane setup/"
            "analysis parameters into one .bandwagon file<br>"
            "· <b>Open Project (Ctrl+Shift+O)</b>: reload a saved .bandwagon and keep working from that state<br>"
            "· This differs from 'Save Result Image' (PNG) — a PNG is one final image for viewing, while "
            ".bandwagon is a working file you can reopen to edit lanes/curves/analysis again."
            "</p>"

            "<h3>Viewing the Canvas</h3>"
            "<p>"
            "· Mouse wheel: zoom in/out (centered on the cursor)<br>"
            "· Left-click drag (default) or middle-button drag: pan<br>"
            "· 'Show analysis overlay' checkbox: toggles lane boxes/band lines/MW labels on screen only"
            "</p>"

            "<h3>Warp Tab</h3>"
            "<p>Straightens a tilted or trapezoidal gel photo into a rectangle. "
            "If auto-detection misses, turn on Corner Mode, drag a rectangle on the image, "
            "then <b>drag the 4 corners</b> to fit.<br>"
            "The bow (sag) typical of gradient gels — where the center dips or rises — can be corrected "
            "live with the 'Bow Correction' slider.</p>"

            "<h3>Adjust Tab</h3>"
            "<p>Rotate (90°/180°/fine) · flip horizontal/vertical · crop · invert colors · brightness/contrast.<br>"
            "Brightness/contrast are display-only and don't affect analysis results. "
            "The rest (rotate/flip/crop/invert) modify the original image and do affect analysis.</p>"

            "<h3>Composite Tab</h3>"
            "<p>Aligns and merges a visible-light photo (showing markers) with a UV photo "
            "(showing fluorescent bands) into one. Click an empty thumbnail to load each photo, "
            "either by opening a file or pasting from the clipboard. Click a thumbnail that already "
            "has a photo to view the original larger.<br>"
            "Once both photos are loaded, drag a rectangle <b>on the UV photo</b> in the canvas below, "
            "then drag the 4 corners to fit. The same canvas immediately "
            "shows how the visible-light photo overlays that area, live. Use the 'Visible-Light "
            "Opacity' slider to adjust how strongly it shows through while you fine-tune the alignment, "
            "then click 'Apply Composite as Main Image' once it looks right.<br>"
            "After applying, the screen shows the blended composite, but "
            "<b>actual band analysis is computed from UV signal only</b> — this prevents marker text "
            "or paper background from the visible-light photo being mistaken for bands. "
            "You can always check either original photo again by clicking its thumbnail.</p>"

            "<h3>Lanes Tab</h3>"
            "<p>"
            "· <b>Auto-Detect Lanes</b>: more accurate if you check the box and specify the expected lane count<br>"
            "· Turn on <b>Manual Lane Mode</b> and drag left-right on the image to add a lane<br>"
            "· Drag a lane edge to resize it; drag a lane's name label to move the whole lane<br>"
            "· Switching a lane's type to 'Marker' opens the MW entry dialog right away (reselecting reopens it)<br>"
            "· Higher sensitivity detects <b>even weaker bands</b><br>"
            "· <b>Boundary Threshold</b>: sets the band boundary (= quantification integration "
            "range). Higher values cut closer to the peak (narrower boundary) — raise this if "
            "boundary areas overlap visually when bands are crowded. Quantification values "
            "(intensity/volume) change along with this setting too<br>"
            "· <b>Band Display Style</b>: choose 'Area' (boundary box, default) or 'Line' (peak "
            "position only) — this only changes what's drawn, not the quantification<br>"
            "· After 'Run Band Analysis', use Up/Dn/Delete to reorder or adjust lanes"
            "</p>"

            "<h3>Analysis / Standard Curve Tabs</h3>"
            "<p>Shows a table of MW/intensity/volume for detected bands. "
            "MW is computed by curve interpolation from the values you entered on marker lanes, and "
            "quantification always uses the raw image data, before any adjustments.</p>"

            "<h3>Marker Presets</h3>"
            "<p>Save frequently-used markers (molecular weight per band) so you can fill them in automatically "
            "next time via 'Manage…'. If the band count differs, you can match them manually.</p>"

            "<h3>Open-Source License Notice</h3>"
            "<p style='font-size:11px;'>"
            "{app} uses the following open-source libraries:<br>"
            "· <b>PyQt5</b> — GPL v3 (this program also publishes its source to remain compatible)<br>"
            "· <b>NumPy</b>, <b>SciPy</b>, <b>Pillow</b> — permissive BSD-family licenses<br>"
            "· <b>OpenCV</b> — Apache License 2.0<br>"
            "Each library's rights belong to its respective project; "
            "this program uses them unmodified."
            "</p>",
    },
}




def tr(key, **kwargs):
    """현재 언어(CURRENT_LANG)에 맞는 문구를 반환한다.
    동적인 부분은 .format(**kwargs)로 채운다 (예: tr("lane_deleted", name=x, count=3)).
    키가 어느 사전에도 없으면 키 자체를 그대로 보여줘서(조용히 죽지 않고)
    누락을 눈에 띄게 한다 — 이게 i18n 버그를 빨리 발견하는 가장 싼 방법이다."""
    table = STRINGS.get(CURRENT_LANG, STRINGS["en"])
    s = table.get(key)
    if s is None:
        s = STRINGS["en"].get(key, f"[[{key}]]")
    try:
        return s.format(**kwargs) if kwargs else s
    except Exception:
        return s




def set_lang(lang):
    """언어 전역을 바꾸고 디스크에도 저장한다(다음 실행부터 적용).
    분할 전 _toggle_language의 `global CURRENT_LANG` 대입을 대체한다."""
    global CURRENT_LANG
    CURRENT_LANG = lang
    save_lang_setting(lang)
