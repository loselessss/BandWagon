# 소스 실행과 배포 빌드

소스 실행과 테스트 방법은 [README](../README.md#소스에서-실행)를 참고하세요.
`run.py`, `run.pyw`, `bandwagon/`은 같은 소스 폴더에 유지합니다.
실행 문제가 있으면 `python run.py`로 실행해 오류 출력을 확인하세요.

## Windows

### 실행 파일

CPython 3.14.6 x64를 설치하고 저장소 루트에서 실행합니다.

```powershell
.\build_exe.bat
```

이 스크립트는 `scripts/build_windows.py`를 실행합니다. 전용 `.venv-build`
환경을 만들고 `requirements-build.lock`의 고정 의존성을 설치·검증합니다.
최초 설치에는 인터넷 연결이 필요하며, 다른 Python 버전이나 예상 밖의
패키지가 포함된 환경에서는 빌드를 중단합니다. 기존 환경이 맞지 않으면
`.venv-build`를 다른 이름으로 옮긴 후 다시 실행하세요.

결과는 `dist/BandWagon/BandWagon.exe`입니다. 실행 파일만 떼어 옮기지 말고
`dist/BandWagon/` 전체를 함께 배포해야 합니다(`--onedir` 방식).
빌드에는 앱·합성 스튜디오 아이콘, Windows 매니페스트, SciPy·OpenCV와
`bandwagon_splash.png`가 포함됩니다. 스플래시는 배포 실행에만 표시됩니다.

### 설치 프로그램

Inno Setup 6을 설치한 뒤, 실행 파일 빌드가 성공한 상태에서 실행합니다.

```powershell
.\build_installer.bat
```

스크립트는 기본 Program Files 경로에서 Inno Setup 6의 `ISCC.exe`를 찾아
`installer.iss`를 컴파일합니다. 결과는
`Output/BandWagon_Setup_<version>.exe`입니다.
설치 프로그램은 `dist/BandWagon/` 전체를 포함합니다. 기본 설치는 사용자
계정 단위이며, 시작 메뉴와 선택 가능한 바탕화면 바로가기를 제공합니다.

## macOS

실제 macOS 환경에서 앱 실행 의존성과 PyInstaller를 설치한 뒤 실행합니다.
Windows용 고정 빌드 환경을 macOS에 그대로 적용하지 않습니다.

```bash
python3 -m pip install PyQt5 Pillow numpy scipy opencv-python pyinstaller
chmod +x build_mac.sh
./build_mac.sh
```

결과는 `dist/BandWagon.app`입니다. 현재 스크립트에는 macOS용 스플래시,
전용 `.icns` 아이콘, 코드 서명·공증 또는 DMG 생성 단계가 없습니다.
Windows 설치 프로그램은 macOS 배포에 사용하지 않습니다.

## 버전과 GitHub 릴리스

버전 규칙은 [AGENTS.md](../AGENTS.md)를 따릅니다. 버전을 올릴 때는
`bandwagon/meta.py`의 `APP_VERSION`·`RELEASE_DATE`, `installer.iss`의
`MyAppVersion`, `CHANGELOG.md`를 함께 갱신합니다.

GitHub의 설치본·포터블·대응 소스 ZIP 게시 절차는
[릴리스 안내](../RELEASE_PROCESS.md), 의존성 출처와 소스·빌드 정보는
[의존성 안내](../RELEASE_DEPENDENCIES.md)를 참고하세요.
로컬 빌드는 GitHub 릴리스를 자동 게시하지 않습니다.
