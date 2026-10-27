# 릴리스 구조와 절차

새 버전은 `vX.Y.Z` 태그를 `main`에 푸시하면 `.github/workflows/release.yml`이
자동으로 릴리스를 만듭니다.
일반 구현·커밋·푸시에서는 버전을 올리지 않습니다. 미배포 변경은 모아 두고
릴리스 시점에 한 번만 버전과 패치노트를 확정합니다.
Windows 빌드는 CPython 3.14.6과 `requirements-build.lock`의 고정된 의존성을
전용 가상환경에 설치해 진행합니다. GitHub push와 pull request에서는 Windows
자동 테스트와 의존성 검증을 실행합니다.

## 하나의 정식 릴리스

소스 준비가 먼저 끝나야 Windows 바이너리 빌드가 시작됩니다. 소스 ZIP 생성,
의존성·빌드 정보 문서 포함 또는 업로드가 실패하면 릴리스 게시도
실패합니다. 별도의 `-source` 태그나 source pre-release는 만들지 않습니다.

정식 버전 릴리스의 Assets에는 다음 파일이 함께 올라갑니다.

- 버전이 포함된 Windows 설치 파일: `BandWagon_Setup_<버전>.exe`
- 최신 버전 별칭 설치 파일: `BandWagon_Setup_latest.exe`
- 대응 포터블 패키지: `BandWagon_Portable_<버전>.zip`
- 포터블 최신 버전 별칭: `BandWagon_Portable_latest.zip`
- 같은 태그의 소스와 `DEPENDENCIES_BUILD.md`를 함께 담은 ZIP: `BandWagon_Source_<버전>.zip`
- 예약된 스토어 ID로 만든 제출용 MSIX: `BandWagon_<버전>_x64_unsigned.msix`

MSIX는 Partner Center 업로드용이며 일반 설치용 서명 파일이 아닙니다.
스토어 ID·이름과 준비 절차는 [MSIX 배포 안내](docs/MSIX.md)를 따릅니다.

설치 파일과 대응 소스는 별도 릴리스가 아니라 같은 버전 릴리스 페이지의
Assets에서 받을 수 있습니다. 버전별 소스 링크를 문서에 넣을 때는 다음처럼
일반 릴리스 페이지를 가리킵니다.
릴리스 본문은 해당 버전의 `CHANGELOG.md` 항목만 사용하며 Assets 파일명을
나열하지 않습니다.

`https://github.com/loselessss/BandWagon/releases/tag/vX.Y.Z`

`vX.Y.Z-source` 같은 별도 source 릴리스 주소는 사용하지 않습니다.

## 릴리스 전 확인

버전 변경 시 `bandwagon/meta.py`, `installer.iss`, `CHANGELOG.md`를 함께 갱신하고,
다음 검사를 통과시킵니다.

```powershell
python -m unittest discover -s tests -v
git diff --check
```

v2.4.0 Assets와 본문은 이 구조로 정리했습니다. v2.3.0 및 그 이전 릴리스는
기존 게시 상태를 유지합니다.
