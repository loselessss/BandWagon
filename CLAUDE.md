# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

PyQt5 기반 젤 전기영동(gel electrophoresis) 분석 도구. 단일 이미지 밴드
검출·분자량(MW) 커브 피팅뿐 아니라, 웨스턴 블롯 채널 합성 기능까지
포함한다.

## 명령어

**의존성 설치** (requirements.txt 없음 — README.txt 기준):
```bash
pip install PyQt5 Pillow numpy scipy opencv-python
```
`opencv-python`(cv2)은 선택 사항 — 없어도 대부분 기능은 동작하지만 워프
(펴기) 등 일부 기능이 빠진다. `bandwagon/meta.py`의 `HAS_CV2` 플래그로
설치 여부를 감지한다.

**실행**:
```bash
python run.py              # 콘솔 표시 — 개발/디버그용
python run.py 이미지.png    # 이미지를 열면서 시작
python -m bandwagon         # 패키지 직접 실행
```
`run.pyw`는 콘솔 없이 더블클릭 실행용(배포 대상 사용자용, 디버그에는
`run.py` 사용).

**자동 테스트 스위트 없음.** 검증은 두 갈래:
1. PyQt5 GUI가 필요한 부분 → 실제로 `python run.py`를 실행해 화면에서 확인.
2. Qt 비의존 순수 로직(`imaging.py`의 변환 함수, `models.py`의 피크 검출
   등) → numpy 배열만으로 격리해서 빠르게 검증 (예: 인위적 평행사변형
   이미지로 `apply_shear_correction`이 직사각형에 가깝게 되돌리는지 확인).

**i18n 키 일치 검증** (커밋 전 필수 — `i18n.py`의 ko/en 딕셔너리가 항상
1:1 대응해야 함):
```bash
python3 -c "
import ast
src=open('bandwagon/i18n.py',encoding='utf-8').read()
dicts=[n for n in ast.walk(ast.parse(src)) if isinstance(n,ast.Dict) and len(n.keys)>50]
keysets=[]
for d in dicts:
    keys=[k.value for k in d.keys if isinstance(k,ast.Constant)]
    assert len(keys)==len(set(keys)), '중복 키 있음'
    keysets.append(set(keys))
assert keysets[0]==keysets[1], keysets[0]^keysets[1]
print('OK', len(keysets[0]), 'keys')
"
```

**배포 빌드** (Windows 기준, 세부 절차는 각 문서 참고):
```bash
build_exe.bat        # PyInstaller → dist\BandWagon.exe (자세한 내용: BUILD_EXE.txt)
build_installer.bat  # Inno Setup → Output\BandWagon_Setup_X.X.exe (BUILD_INSTALLER.txt)
```
macOS는 `./build_mac.sh` (실제 macOS에서만 가능 — PyInstaller는 크로스
컴파일 미지원, 자세한 내용: `BUILD_MAC.txt`).

## 아키텍처

`app.py`의 `Analyzer(QMainWindow)`가 여러 믹스인을 조립한 형태:
- `StyleMixin` (style.py) — 테마/CSS
- `GeometryMixin` (geometry.py) — 회전/기울기·곡률 보정/펴기(warp)/
  밝기·대비·톤커브, 되돌리기(undo/redo) 엔진(`_edit_ops`/`_replay_history`)
- `LanesMixin` (lanes.py) — 레인 구성·자동검출
- `FileIOMixin` (fileio.py) — 이미지/프로젝트 열기·저장, 합성 파일 임포트

`composite.py`(웨스턴 블롯 합성 스튜디오)는 **믹스인이 아니라 독립
QDialog**다. `Analyzer` 내부 상태를 전혀 참조하지 않고, 오직
`.bwcomposite` 파일(화면용 블렌드 PNG + 분석용 UV 그레이스케일 PNG를
묶은 zip)을 통해서만 메인 앱과 통신한다. 이 경계를 허물지 말 것 — 예전
`WesternMixin`(합성을 되돌리기 히스토리 안 특수 연산으로 넣던 방식)은
메모리 문제와 상태 결합 문제가 있어서 v1.3에서 이 구조로 교체했다.

기반 모듈:
- `models.py` — 밴드 검출/피크 적분/MW 커브 피팅
- `imaging.py` — 순수 이미지 변환 함수(Qt 의존 없음)
- `widgets.py` — GelView/ThumbView 등 재사용 위젯
- `theme.py` — 색상 디자인 토큰, 채널/레인 팔레트
- `presets.py` — 마커(분자량 사다리) 프리셋 로드/저장 (`~/.bandwagon_markers.json`)
- `dialogs.py` — 마커 입력/프리셋 관리 다이얼로그
- `i18n.py` — 다국어 문자열(ko/en) + `tr()`

`i18n.CURRENT_LANG`은 런타임에 바뀌는 전역 상태다. 다른 모듈에서
`from .i18n import CURRENT_LANG`으로 값을 스냅샷하지 말 것 — 언어 전환이
반영되지 않는다. 항상 `i18n.tr()` / `i18n.CURRENT_LANG` / `i18n.set_lang()`
형태로 모듈을 통해 참조해야 한다.

## 핵심 불변식 (건드릴 때 반드시 유지)

- **`self._orig`은 항상 "재생 결과"**: `_edit_pristine` + `_edit_ops[:_edit_pos+1]`를
  처음부터 재적용한 것과 항상 같아야 한다. 직접 `self._orig`을 수정하지
  말고 `_record_op()`를 거칠 것.
- **분석용 그레이스케일 오버라이드**: 합성 파일을 임포트한 세션에서는
  `self._wb_gray_override`(현재 값)와 `self._edit_gray_pristine`(재생
  시작점)가 UV 단독 강도를 담고 있다. 기하 연산(`rotate`/`crop`/`warp`
  등)을 `apply_edit_op`에 새로 추가할 때 이 오버라이드도 이미지와
  **똑같이 변환**해야 한다 — 안 그러면 가시광 마커 글자가 다시 가짜
  밴드로 잡히는 회귀가 생긴다(v1.3에서 한 번 고친 버그).
- **`_GEOMETRY_OPS`**: 새 기하 연산(예: shear_correct)을 추가하면 이
  frozenset에도 추가해야 한다 — 그래야 그 연산을 만났을 때 레인 구성이
  자동으로 초기화된다(좌표가 안 맞게 되므로).
- **i18n.py는 ko/en 두 딕셔너리가 항상 1:1 대응**해야 한다. 키를
  추가/삭제하면 양쪽에 똑같이 반영하고, 커밋 전에 위 "명령어" 섹션의
  검증 스크립트로 확인.

## 버전 올리기

`BUILD_INSTALLER.txt`에 적힌 절차를 따를 것 — 아래 두 곳을 **같이**
맞춘다(자동 동기화 안 됨):
- `bandwagon/meta.py`의 `APP_VERSION`, `RELEASE_DATE`
- `installer.iss`의 `MyAppVersion`(CRLF/BOM 유지 — 텍스트 에디터로 열 것)

`CHANGELOG.md`는 최신 버전을 맨 위에 추가(기존 버전은 아래로 밀림).
섹션 구성: `## 새 기능` → `## 개선` → `## 성능 개선` → `## 버그 수정` →
`## 기타`(해당 없는 섹션은 생략). 기능 성격이 다르면 버전을 분리한다
(예: 성능 개선은 patch 버전, 새 독립 모듈 추가는 minor 버전).

## 코드 스타일

- 주석은 **"무엇"이 아니라 "왜"** 위주(한글). 특히 되돌리기 엔진, 레인
  좌표계, 오버라이드 처리처럼 다시 읽을 때 헷갈리는 부분은 의도를 남길 것.
- `QAction.triggered`/`valueChanged(int)` 시그널을 슬롯에 바로 연결하면
  Qt가 넘기는 `checked`/`value` 인자가 함수의 첫 인자에 잘못 꽂히는 경우가
  있다 — 인자를 받는 슬롯에 연결할 땐 람다로 감쌀 것
  (`lambda _checked=False: self.foo()`).

## 참고

- GitHub: https://github.com/loselessss/BandWagon
- 라이선스: MIT
