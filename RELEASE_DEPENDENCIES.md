# BandWagon 의존성·소스·빌드 정보

이 문서는 릴리스 `@VERSION@`에 포함된 소스와 Windows 배포 파일을 재현할 때
필요한 의존성의 출처와 빌드 순서를 기록합니다. 이 문서는 릴리스 Assets의
`BandWagon_Source_@VERSION@.zip` 안에 `DEPENDENCIES_BUILD.md`로 포함됩니다.

## 소스 기준

- 저장소: https://github.com/loselessss/BandWagon
- 릴리스 태그: `v@VERSION@`
- 대응 소스: 같은 태그에서 생성한 `BandWagon_Source_@VERSION@.zip`

## 런타임 의존성

| 패키지 | 용도 | 공식 출처 |
| --- | --- | --- |
| CPython 3.14.6 x64 | 실행 환경 | https://www.python.org/ |
| PyQt5 | 데스크톱 UI | https://pypi.org/project/PyQt5/ |
| Pillow | 이미지 입출력 | https://pypi.org/project/Pillow/ |
| NumPy | 배열·영상 계산 | https://pypi.org/project/numpy/ |
| SciPy | 피크 검출·수치 분석 | https://pypi.org/project/scipy/ |
| OpenCV Python | 원근 보정·자동 펴기 | https://pypi.org/project/opencv-python/ |

개발 환경에서는 저장소 루트에서 다음처럼 설치합니다.

```powershell
python -m pip install PyQt5 Pillow numpy scipy opencv-python
```

## Windows 배포 빌드 의존성

| 도구 | 용도 | 공식 출처 |
| --- | --- | --- |
| PyInstaller | `BandWagon.exe` onedir 빌드 | https://pypi.org/project/pyinstaller/ |
| Inno Setup 6 | Windows 설치 파일 생성 | https://jrsoftware.org/isinfo.php |

릴리스 자동화는 GitHub Actions의 `windows-latest`에서 실행되며, CPython 3.14.6과
`requirements-build.lock`에 고정된 패키지로 `scripts/build_windows.py`를 실행한 뒤 다음 순서로 빌드합니다.

1. PyInstaller로 `dist/BandWagon/`을 생성합니다.
2. Inno Setup으로 `BandWagon_Setup_@VERSION@.exe`를 생성합니다.
3. onedir 폴더를 `BandWagon_Portable_@VERSION@.zip`으로 압축합니다.
4. 설치 파일과 포터블 파일의 `latest` 별칭을 만듭니다.

정확한 명령은 `.github/workflows/release.yml`에 고정되어 있습니다. macOS 앱은
Windows 릴리스 잡과 별개로 실제 macOS 환경에서 `build_mac.sh`를 사용합니다.

## 라이선스

각 패키지의 라이선스와 고지 의무는 해당 공식 배포처의 정보를 따릅니다.
BandWagon 자체는 저장소의 [MIT License](LICENSE)를 따릅니다.
