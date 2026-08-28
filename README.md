# BandWagon

BandWagon은 젤 전기영동(gel electrophoresis) 이미지에서 레인과 밴드를
검출하고, 분자량(MW)을 계산하며, 분석 결과를 이미지와 CSV로 내보내는
데스크톱 분석 도구입니다. 가시광 이미지와 UV 이미지를 정렬해 합성하는
웨스턴 블롯 작업도 함께 지원합니다.

최신 Windows 설치본과 포터블 버전은
[GitHub Releases](https://github.com/loselessss/BandWagon/releases/latest)에서
받을 수 있습니다.

## 만든 이유

젤 이미지를 분석하려면 이미지 방향과 기울기를 바로잡고, 레인 범위를 정한
뒤, 밴드 위치와 강도를 읽고, 마커를 기준으로 분자량 곡선을 맞춰야 합니다.
이 과정을 여러 프로그램과 수작업으로 나누면 같은 조건으로 다시 분석하기
어렵고 결과를 재현하기도 번거롭습니다.

BandWagon은 이 흐름을 한곳에 모읍니다.

- 젤 이미지의 방향, 기울기, 곡률, 원근을 보정합니다.
- 레인을 자동 검출하거나 직접 추가하고 범위를 조정합니다.
- 밴드를 검출하고 피크 면적과 상대 강도를 계산합니다.
- 분자량 마커를 바탕으로 MW 보정 곡선을 맞춥니다.
- 이미지, 레인, 보정값, 분석 설정과 메모를 프로젝트 하나에 저장합니다.
- 가시광·UV 채널을 별도 스튜디오에서 정렬하고 합성합니다.

## 주요 기능

### 이미지 보정

- 90도 회전, 좌우·상하 반전
- 정밀 회전과 기울기(shear) 보정
- 휘어진 젤의 곡률 보정
- 네 모서리 지정 원근 보정과 자동 펴기
- 밝기, 대비, 채널별 톤 커브 조정
- RGB 및 개별 Red·Green·Blue 채널 분석

### 레인과 밴드 분석

- 레인 자동 검출 및 수동 추가·삭제·정렬
- 레인 이름, 유형, 표시 순서 관리
- 분석 범위와 최소 밴드 간격 조정
- 밴드 민감도와 스미어 허용 범위 조정
- 밴드 경계 영역 또는 피크 선 표시
- 피크 면적, 상대 강도와 분자량 결과 표 제공

### 분자량 보정

- 마커 레인과 기준 분자량 입력
- 사용자 마커 프리셋 저장 및 재사용
- 분자량 커브 피팅과 미지 밴드 MW 계산

### 웨스턴 블롯 합성

- 가시광 이미지와 UV 이미지 불러오기
- 두 채널의 위치·회전·크기 정렬
- 화면용 합성 이미지와 분석용 UV 그레이스케일을 함께 보존
- `.bwcomposite` 파일로 내보낸 뒤 메인 분석 화면에서 불러오기

### 작업 보존과 내보내기

- 이미지와 모든 분석 상태를 `.bandwagon` 프로젝트 하나로 저장
- 이미지·레인·분석 설정·메모를 포함한 최대 200단계 실행 취소/다시 실행
- 분석 오버레이 포함 여부를 선택해 결과 이미지 저장 또는 복사
- 레인·밴드 결과 CSV 내보내기
- 한국어·영어 UI

## 설치

[최신 릴리스](https://github.com/loselessss/BandWagon/releases/latest)에서
사용 방식에 맞는 파일을 받으세요.

- `BandWagon_Setup_<version>.exe`: 시작 메뉴, 바탕화면 바로가기와 제거
  기능을 제공하는 Windows 설치본
- `BandWagon_Portable_<version>.zip`: 압축을 푼 폴더에서 바로 실행하는
  포터블 버전

설치본과 포터블 모두 앱 안에서 새 버전을 확인할 수 있습니다. 설치본은 다음
Setup EXE를 받고, 포터블은 다음 Portable ZIP을 받아 기존 폴더를 교체합니다.
포터블 교체 후 새 버전이 정상적으로 시작하지 못하면 이전 폴더를 복구합니다.

## 기본 사용 흐름

1. 젤 이미지를 열거나 클립보드에서 붙여넣습니다.
2. 회전·기울기·곡률·원근과 밝기·대비를 필요한 만큼 보정합니다.
3. 레인을 자동 검출하거나 직접 배치합니다.
4. 마커 레인을 지정하고 기준 분자량을 입력합니다.
5. 밴드 검출 조건을 조정한 뒤 분석을 실행합니다.
6. 결과 이미지와 CSV를 내보내거나 `.bandwagon` 프로젝트로 저장합니다.

가시광·UV 합성이 필요하면 먼저 **웨스턴블롯 → 만들기**에서 합성 파일을
만든 다음, `.bwcomposite`를 메인 분석 화면으로 가져오면 됩니다.

## 파일 형식

- `.bandwagon`: 원본 이미지, 편집 기록, 레인, 분석 설정, 분자량 보정과
  메모를 담는 BandWagon 프로젝트
- `.bwcomposite`: 화면용 합성 PNG와 분석용 UV 그레이스케일 PNG를 함께
  담는 웨스턴 블롯 합성 파일

두 형식 모두 다른 프로그램의 임시 상태에 의존하지 않고 나중에 다시 열어
분석을 이어갈 수 있도록 설계되어 있습니다.

## 소스에서 실행

Python 환경에서 다음 의존성을 설치합니다. OpenCV는 원근 보정과 자동 펴기
등 일부 기하 기능에 사용됩니다.

```powershell
python -m pip install PyQt5 Pillow numpy scipy opencv-python
```

실행 방법:

```powershell
python run.py
python run.py "image.png"
python -m bandwagon
```

Windows에서 콘솔 없이 실행하려면 `run.pyw`를 더블클릭할 수 있습니다.

## 개발과 검증

자동 테스트:

```powershell
python -m unittest discover -s tests -v
git diff --check
```

일부 GUI 동작은 실제 앱을 실행해 확인해야 합니다.

```powershell
python run.py
```

## 배포 빌드

Windows에서는 PyInstaller로 앱 폴더를 만든 다음 Inno Setup으로 설치 파일을
생성합니다.

```powershell
build_exe.bat
build_installer.bat
```

결과 설치 파일은 `Output/BandWagon_Setup_<version>.exe`에 생성됩니다.
자세한 절차는 [BUILD_EXE.txt](BUILD_EXE.txt)와
[BUILD_INSTALLER.txt](BUILD_INSTALLER.txt)를 참고하세요.

macOS 앱은 실제 macOS 환경에서만 빌드할 수 있습니다.

```bash
./build_mac.sh
```

자세한 내용은 [BUILD_MAC.txt](BUILD_MAC.txt)를 참고하세요.

## 문서

- [CHANGELOG.md](CHANGELOG.md): 버전별 변경 기록
- [README.txt](README.txt): 소스 폴더에서 빠르게 실행하는 방법
- [BUILD_EXE.txt](BUILD_EXE.txt): Windows 실행 파일 빌드
- [BUILD_INSTALLER.txt](BUILD_INSTALLER.txt): Windows 설치 프로그램 빌드
- [BUILD_MAC.txt](BUILD_MAC.txt): macOS 앱 빌드

## 로컬 처리

이미지 분석과 프로젝트 저장은 사용자 PC에서 처리됩니다. 업데이트 확인을
선택하거나 배포본의 자동 확인이 실행될 때만 GitHub Releases에 최신 버전
정보를 요청합니다.

## 라이선스

BandWagon은 [MIT License](LICENSE)로 배포됩니다.
