# BandWagon MSIX 배포

Windows 10 2004(빌드 19041) 이상·Windows 11 x64를 대상으로 합니다.
기존 EXE 설치본과 포터블 ZIP은 계속 지원합니다.

## Microsoft Store 제출용 (현재 릴리스)

스토어에 예약한 공개 정보는 `packaging/msix/store.json`에 고정합니다.

| 항목 | 값 |
| --- | --- |
| 제품 이름 | BandWagon Gel Analyzer |
| Package/Identity/Name | 8B91E56A.BandwagonGelanalyzer |
| Package/Identity/Publisher | CN=2F094A43-B9EE-4C1D-8DA7-69C507CA03A4 |
| Package/Properties/PublisherDisplayName | 신상규 |

```powershell
python scripts/build_windows.py
.venv-build\Scripts\python.exe scripts/build_msix.py --store
```

`--store`는 위 값으로 패키지·시작 메뉴 표시 이름을 설정하고,
서명 인증서 환경 변수가 있더라도 로컬 서명을 하지 않습니다.
앱 내부 제목·EXE 설치본·포터블 이름은 BandWagon으로 유지합니다.
버전 `2.10.0`의 패키지는 `2.10.0.0`, 파일은
`Output/BandWagon_2.10.0_x64_unsigned.msix`입니다.
Store는 제출 과정에서 서명하므로 Partner Center에는 이 서명 전 파일을 올립니다.
일반 PC에 직접 설치할 배포 파일로 취급하지 않습니다.

제출 전 확인:

1. Partner Center의 해당 제품에서 위 예약명·ID·게시자가 일치하는지 확인합니다.
2. 패키지 업로드 후 자동 검증 결과를 확인합니다. 빌드 성공은 스토어 심사 통과를 의미하지 않습니다.
3. 스토어 설명·스크린샷·개인정보 및 연령 등급 등 필수 항목을 채우고 제출합니다.
4. 스토어 설치본의 실행·파일 연결·프로젝트 저장·재열기·분석·출력을 확인합니다.

직접 설치본의 인증서 신뢰 등록이나 스토어 제출·게시 자체는 빌드 작업에 포함하지 않습니다.

## 직접 배포용 빌드 (선택)

CPython 3.14.6 x64와 Windows 10/11 SDK의 MakeAppx·SignTool이 필요합니다.

```powershell
python scripts/build_windows.py
.venv-build\Scripts\python.exe scripts/build_msix.py
```

버전은 `bandwagon/meta.py`의 `APP_VERSION`에서 읽습니다. 앱의 `x.y.z`는
MSIX에서 `x.y.z.0`으로 표시됩니다. 인증서 없이 빌드하면
`Output/BandWagon_<version>_x64_unsigned.msix`가 만들어집니다.
이는 서명 전 준비용 파일이며 더블클릭해서 일반 설치할 수 없습니다.
MakeAppx의 매니페스트 검증은 생략하지 않습니다.

다른 SDK 경로는 `--sdk-bin "C:\...\Windows Kits\10\bin\<SDK version>\x64"`,
빌드 결과물은 `--payload`, 출력 위치는 `--output`으로 지정할 수 있습니다.
기존 설치 폴더가 아닌 깨끗한 PyInstaller onedir 빌드를 사용하세요.

## 서명

인증서의 Subject와 패키지 Publisher가 정확히 일치해야 합니다.
패키지 Identity·Publisher는 설치 후 업데이트에서도 유지해야 합니다.
기본값은 `loselessss.BandWagon`과 `CN=BandWagon`이며 인증서에 맞게 설정하세요.
Store에 제출할 때는 Partner Center에서 받은 Identity·Publisher를 사용합니다.

```powershell
$env:MSIX_PFX_PATH = 'C:\private\bandwagon-signing.pfx'
$env:MSIX_PUBLISHER = 'CN=BandWagon'
# 암호는 MSIX_PFX_PASSWORD 환경 변수에 보안 관리 도구로 설정합니다.
.venv-build\Scripts\python.exe scripts/build_msix.py --require-signed
```

정상적으로 서명·검증되면 `Output/BandWagon_<version>_x64.msix`를 생성합니다.
SignTool 검증에서 실패하면 배포용 이름으로 출력하지 않습니다.
RFC 3161 타임스탬프 서버를 사용할 경우 `MSIX_TIMESTAMP_URL` 또는
`--timestamp-url`을 지정하세요. 인증서와 암호는 저장소에 올리지 마세요.

외부 직접 배포에는 설치 PC가 신뢰하는 인증서가 필요합니다. 자체 서명 테스트
인증서는 빌드 PC 및 테스트 PC에 별도로 신뢰 등록해야 합니다. 빌드 스크립트는
인증서를 만들거나 신뢰 저장소를 변경하지 않습니다. Store 배포는 Store가 서명합니다.

## GitHub Actions

Actions의 **MSIX package → Run workflow**로 릴리스 없이 패키지를 만들어
`BandWagon-MSIX` artifact에서 받을 수 있습니다. 태그 릴리스 자동화에도
같은 `--store` 패키징 단계가 포함됩니다. 둘 다 예약된 ID의 서명 전 제출용 파일입니다.

직접 배포용으로 `--store` 없이 서명할 때만 다음 설정을 사용합니다.

- Secrets `MSIX_PFX_BASE64`: PFX 파일의 Base64(줄바꿈 없는 값)
- Secrets `MSIX_PFX_PASSWORD`: PFX 암호
- Variables `MSIX_PUBLISHER`: 인증서 Subject와 일치하는 Publisher
- 선택 Variables `MSIX_IDENTITY`, `MSIX_TIMESTAMP_URL`

현재 스토어 워크플로에서는 이 인증서 설정을 사용하지 않습니다.
직접 배포용 빌드에서 인증서가 없으면 이름에 `_unsigned`가 포함된 준비용 패키지가 생성됩니다.
개인키는 일시적인 빌드 폴더에만 풀고 작업 후 제거합니다. 서명 오류가 발생하면
서명되지 않은 파일을 정상 배포용 이름으로 내보내지 않습니다.

## 앱 업데이트

앱은 Windows 패키지 Identity로 MSIX 실행 여부를 확인합니다. MSIX 설치본은
릴리스의 정확한 버전 `BandWagon_<version>_x64.msix`만 선택하며 SHA-256을
검증한 뒤 Windows 앱 설치 관리자로 엽니다. EXE 설치·포터블 폴더 교체는
실행하지 않습니다. Windows가 서명과 Publisher·Identity를 확인하고 업데이트합니다.

서명된 MSIX가 릴리스에 없으면 앱은 릴리스 페이지 안내만 표시합니다.
`_unsigned.msix`는 자동 업데이트 대상에서 제외합니다. 다운로드 이름만으로
인증서를 신뢰하지 않으며 최종 서명 검사는 Windows에 맡깁니다.

## 설치 후 확인할 항목

- 시작 메뉴에서 실행하고 이미지·클립보드 입력, 분석, 내보내기를 확인합니다.
- 공백·한글이 포함된 경로의 `.bandwagon`·`.bwcomposite` 파일을 더블클릭해 엽니다.
- 설정·마커 프리셋·자동 복구가 다음 실행과 MSIX 업데이트 후에도 유지되는지 확인합니다.
- 동일한 Identity·Publisher의 상위 버전으로 업데이트한 뒤 다시 실행합니다.
- 설정의 설치된 앱에서 제거할 수 있는지 확인합니다.

설정은 Windows의 패키지별 파일·레지스트리 가상화 영향을 받을 수 있으므로,
EXE 설치본과의 설정 공유·이전은 아직 보장하지 않습니다. 기존 프로젝트 파일은
MSIX 설치 전에 별도로 보관하고 직접 열어 사용할 수 있습니다.
회사 PC의 설치 정책에 따라 MSIX·인증서 등록이 제한될 수 있습니다.

## 공식 자료

- [MakeAppx 패키징](https://learn.microsoft.com/en-us/windows/msix/package/create-app-package-with-makeappx-tool)
- [MSIX 서명](https://learn.microsoft.com/en-us/windows/msix/package/sign-msix-package-guide)
- [데스크톱 앱 파일 연결](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/desktop-to-uwp-extensions)
- [MSIX 파일·레지스트리 동작](https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-behind-the-scenes)
