# 릴리스 구조와 절차

새 버전은 `vX.Y.Z` 태그를 `main`에 푸시하면 `.github/workflows/release.yml`이
자동으로 릴리스를 만듭니다.

## 하나의 정식 릴리스

소스 준비가 먼저 끝나야 Windows 바이너리 빌드가 시작됩니다. 소스 ZIP 생성,
체크섬 생성, 의존성·빌드 정보 문서 준비 또는 업로드가 실패하면 릴리스 게시도
실패합니다. 별도의 `-source` 태그나 source pre-release는 만들지 않습니다.

정식 버전 릴리스의 Assets에는 다음 파일이 함께 올라갑니다.

- 버전이 포함된 Windows 설치 파일: `BandWagon_Setup_<버전>.exe`
- 최신 버전 별칭 설치 파일: `BandWagon_Setup_latest.exe`
- 대응 포터블 패키지: `BandWagon_Portable_<버전>.zip`
- 포터블 최신 버전 별칭: `BandWagon_Portable_latest.zip`
- 같은 태그에서 만든 대응 소스: `BandWagon_Source_<버전>.zip`
- 소스 ZIP SHA-256 체크섬: `BandWagon_Source_<버전>.zip.sha256`
- 의존성·소스·빌드 정보: `BandWagon_Dependencies_Build_<버전>.md`

설치 파일과 대응 소스는 별도 릴리스가 아니라 같은 버전 릴리스 페이지의
Assets에서 받을 수 있습니다. 버전별 소스 링크를 문서에 넣을 때는 다음처럼
일반 릴리스 페이지를 가리킵니다.

`https://github.com/loselessss/BandWagon/releases/tag/vX.Y.Z`

`vX.Y.Z-source` 같은 별도 source 릴리스 주소는 사용하지 않습니다.

## 릴리스 전 확인

버전 변경 시 `bandwagon/meta.py`, `installer.iss`, `CHANGELOG.md`를 함께 갱신하고,
다음 검사를 통과시킵니다.

```powershell
python -m unittest discover -s tests -v
git diff --check
```

이 구조 변경은 앞으로 생성되는 릴리스에만 적용됩니다. 기존 릴리스와 Assets는
삭제하거나 다시 작성하지 않습니다.
