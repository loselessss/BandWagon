---
layout: policy
title: BandWagon Gel Analyzer — Privacy Policy
permalink: /privacy/
---

# BandWagon Gel Analyzer 개인정보처리방침 / Privacy Policy

시행일 / Effective date: **2026-10-28**

## 한국어

### 1. 적용 범위와 담당자

본 방침은 신상규가 제공하는 **BandWagon Gel Analyzer**(앱 내부 이름: BandWagon)의
Microsoft Store MSIX, Windows 설치본 및 포터블 버전에 적용됩니다.

- 개인정보 관련 담당자: **신상규**
- 문의 이메일: **[loseless@naver.com](mailto:loseless@naver.com)**

앱에는 개발자 계정 가입, 광고, 사용자 행동 추적 또는 분석 자료의 자동 업로드 기능이 없습니다.
파일은 기기에서 처리하며, 업데이트 확인·다운로드를 위해 외부 서비스와 통신합니다.

### 2. 기기에서 처리하는 정보

- 사용자가 선택한 이미지·프로젝트·웨스턴블롯 합성 파일을 열기, 보정, 분석, 저장 및
  내보내기에 사용합니다. 자료에는 레인 이름, 마커 값, 분석 결과·설정과 메모가 포함될 수 있습니다.
- 붙여넣기를 실행하면 클립보드의 이미지를 읽고, 복사를 실행하면 결과를 클립보드에 기록합니다.
- 다시 열기 편의를 위해 최근 파일의 이름과 전체 경로를 저장합니다.
  경로에는 Windows 사용자 이름이나 연구·샘플 이름이 포함될 수 있습니다.
- 언어, 창 배치, 표시·내보내기 옵션, 마커 프리셋, 건너뛴 업데이트 버전 등을 로컬에 저장합니다.
- 작업 복구를 위해 저장하지 않은 이미지와 프로젝트 상태의 사본을 약 30초 간격으로 저장합니다.
  이는 클라우드 백업이 아닙니다.
- 처리되지 않은 오류의 시각과 오류 내용을 로컬 로그에 기록할 수 있습니다.
  로그에는 파일 경로 등 오류 관련 정보가 포함될 수 있습니다.

앱은 이미지·프로젝트·메모·로컬 파일 경로·오류 로그를 개발자나 GitHub에 자동 업로드하지 않습니다.
개발자는 기기의 자료에 원격으로 접근할 수 없습니다. 분석에 불필요한 개인 식별 정보나
민감한 정보를 자료에 포함하지 않는 것을 권장합니다.

### 3. 업데이트 통신과 외부 서비스

배포본은 시작 후 GitHub의 `loselessss/BandWagon` 공개 릴리스 API에 최신 버전을 자동 확인합니다.
사용자가 업데이트 확인을 직접 실행할 수도 있습니다. 업데이트 파일은 GitHub 및 다운로드
전달 인프라에서 HTTPS로 받습니다.

이 과정에서 외부 서비스에는 IP 주소, 요청 시각, 요청한 릴리스·다운로드 주소와
현재 앱 버전을 포함한 `BandWagon/<버전>` User-Agent 등 통신 정보가 전달될 수 있습니다.
요청에 이미지·프로젝트·메모·로컬 파일 경로를 첨부하지 않습니다.
외부 서비스의 접속 기록 처리에는 [GitHub 개인정보처리방침](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement)이 적용됩니다.

Microsoft Store의 설치·업데이트·계정 등 스토어 서비스에서 Microsoft가 처리하는 정보에는
[Microsoft 개인정보처리방침](https://privacy.microsoft.com/privacystatement)이 적용됩니다.
앱 자체는 Microsoft 계정 로그인 정보나 결제 정보를 요구·수집하는 기능을 제공하지 않습니다.

이미지 분석 자체는 인터넷 없이 가능합니다. 현재 자동 업데이트 확인만 끄는 별도 앱 설정은 없으며,
네트워크 연결은 Windows 방화벽·연결 설정으로 관리할 수 있습니다.
‘이 버전 건너뛰기’는 알림을 숨기는 기능이지 네트워크 통신을 중지하는 기능은 아닙니다.
앱에서 본 방침을 열면 기본 브라우저로 GitHub Pages에 접속합니다.
이 페이지에는 별도 광고·추적 스크립트를 넣지 않으며, 호스팅 접속 기록에는 GitHub의 방침이 적용됩니다.

### 4. 보관과 삭제

- 직접 저장한 이미지·프로젝트·CSV는 사용자가 선택한 폴더에 사용자가 삭제할 때까지 남습니다.
  앱 제거가 별도로 저장한 자료까지 삭제한다는 뜻은 아닙니다.
- 최근 파일·마커·언어는 사용자 홈 폴더의 `.bandwagon_recent.json`, `.bandwagon_markers.json`,
  `.bandwagon_lang.json` 등에, 다른 설정은 Windows 사용자 설정 폴더에 보관합니다.
  앱의 최근 파일 목록 지우기는 목록만 지우며 원본 파일을 삭제하지 않습니다.
- 복구 사본은 보통 `%LOCALAPPDATA%\BandWagon\recovery` 아래에 보관합니다.
  해당 작업의 정상 저장·종료 시 삭제를 시도합니다. 비정상 종료 후 남은 사본은 복구 안내에서
  삭제하거나 앱을 닫은 뒤 직접 삭제할 수 있습니다.
- 오류 로그는 보통 사용자 홈 폴더의 `bandwagon_crash.log`에 누적되며 자동 보관 기간은 없습니다.
  앱을 닫은 뒤 직접 삭제할 수 있습니다.
- 업데이트 파일은 Windows 임시 폴더의 `BandWagon\updates` 등에 남을 수 있습니다.
  포터블 업데이트의 임시·백업 폴더도 남을 수 있으며 업데이트와 앱·설치 프로그램 종료 후
  더 이상 필요하지 않은 사본을 삭제할 수 있습니다.

MSIX에서는 Windows 파일·설정 가상화로 실제 위치가 달라질 수 있습니다.
설정·복구 파일을 직접 삭제하기 전 앱을 닫고 필요한 작업을 보관하세요.
파일 삭제가 백업·동기화 서비스·운영체제 기록이나 복구 가능한 저장 장치 사본까지
완전히 삭제함을 보장하지는 않습니다.

### 5. 공유와 보안

개발자는 로컬 분석 자료를 수집하여 판매하거나 광고·추적 목적으로 공유하지 않습니다.
사용자가 파일 공유·내보내기·클립보드 복사·문의 첨부를 선택하면 이후의 저장·공유에는
선택한 서비스나 Windows 기능의 설정이 적용됩니다. 클립보드 기록·기기 간 동기화,
동기화 폴더에 저장하는 경우도 포함됩니다.

프로젝트·설정·복구 사본·로그는 앱 차원에서 별도로 암호화하지 않습니다.
공유 PC에서는 사용자 계정·파일 권한·장치 암호화 등 적절한 보호 수단을 사용하고,
자료를 전달하기 전 개인정보와 불필요한 내용을 확인하세요.

### 6. 문의 정보와 이용자의 선택

이메일로 직접 제공한 정보는 문의 확인·답변 및 관련 후속 대응에 사용합니다.
불필요해진 문의 정보는 삭제하되, 법령상 보관 의무 등 필요한 사유가 있으면 해당 기간 보관합니다.
문의 정보의 열람·정정·삭제 요청은 **loseless@naver.com**으로 보내 주세요.
이메일 서비스 사업자의 보관·처리에는 해당 사업자의 방침도 적용됩니다.

사용자는 로컬 자료를 열거나 수정·삭제하고, 최근 파일 목록과 복구 사본을 지우며,
내보내기·공유 여부를 선택할 수 있습니다. 개발자가 보유하지 않는 기기 내 자료는
개발자가 대신 열거나 삭제할 수 없습니다.
공개 GitHub 이슈에는 이미지·프로젝트·로그·개인정보를 첨부하지 말고 이메일로 먼저 문의하세요.

### 7. 어린이와 방침 변경

앱은 어린이 대상 서비스가 아니며 연령·아동 계정·아동 개인정보를 수집하는 기능을 제공하지 않습니다.
데이터 처리 방식이 바뀌면 본 방침과 시행일을 갱신합니다.

---

## English

### 1. Scope and contact

This policy applies to **BandWagon Gel Analyzer** (BandWagon inside the app), provided by
**Sangkyu Shin (신상규)**, including Microsoft Store MSIX, Windows installer and portable editions.
Privacy contact: **[loseless@naver.com](mailto:loseless@naver.com)**.

The app has no developer-account registration, advertising, behavioral tracking or automatic upload
of analysis materials. Files are processed on your device; external services are contacted for updates.

### 2. Information processed on your device

- Selected images, projects and Western blot composites are used for opening, adjustment, analysis,
  saving and export. Materials may include lane names, marker values, results, settings and notes.
- Invoking Paste reads an image from the clipboard; invoking Copy writes the result to it.
- Recent file names and full paths are retained for reopening. Paths may contain Windows user names
  or research/sample identifiers.
- Preferences such as language, layout, display/export choices, marker presets and skipped update
  versions are stored locally.
- Images and project state from unsaved work are copied locally at approximately 30-second intervals
  for crash recovery. This is not a cloud backup.
- Unhandled errors may be logged locally with their time and details, which may include file paths.

The app does not automatically upload images, projects, notes, local file paths or logs to the developer
or GitHub. The developer cannot remotely access your local materials. Avoid including unnecessary
identifying or sensitive information in your materials.

### 3. Updates and external services

Distributed builds automatically check the public `loselessss/BandWagon` GitHub Releases API after
launch. You may also check manually. Updates are downloaded over HTTPS from GitHub and its delivery
infrastructure.

These services may receive connection information including your IP address, request time, requested
release/download URL and the `BandWagon/<version>` User-Agent containing the current app version.
Requests do not attach images, projects, notes or local file paths. GitHub's processing is governed by
the [GitHub Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).

Microsoft's processing when you install, update or use Microsoft Store services is governed by the
[Microsoft Privacy Statement](https://privacy.microsoft.com/privacystatement). The app itself has no
feature that requests or collects Microsoft-account credentials or payment information.

Image analysis works offline. There is currently no separate app switch to disable automatic update
checks; connections can be managed using Windows firewall or network settings. “Skip this version”
hides a notification; it does not stop network requests.
Opening this policy from the app launches your default browser and contacts GitHub Pages.
The page includes no additional advertising or tracking scripts; GitHub's policy applies to hosting access records.

### 4. Retention and deletion

- Saved images, projects and CSV files remain in your chosen folders until you delete them.
  Uninstalling does not imply deletion of separately saved materials.
- Recent files, markers and language preferences use files including `.bandwagon_recent.json`,
  `.bandwagon_markers.json` and `.bandwagon_lang.json` in your user home folder. Other preferences
  use Windows user-settings storage. Clearing Recent Files deletes the list, not the original files.
- Recovery copies are normally under `%LOCALAPPDATA%\BandWagon\recovery`. The app attempts to
  remove a session's copy after normal saving/closing. Copies left after a crash can be removed
  through the recovery prompt or manually after closing the app.
- Error logs normally accumulate in `bandwagon_crash.log` in your user home folder without an
  automatic retention limit. You can delete the log after closing the app.
- Downloaded updates may remain in `BandWagon\updates` under Windows temporary storage.
  Portable updates may leave staging/backup folders. Unneeded copies can be removed once updating
  finishes and the app and installer have closed.

MSIX virtualization may change actual locations. Close the app and preserve needed work before
deleting settings or recovery files. Deleting files does not guarantee removal from backups,
synchronization services, operating-system records or recoverable storage.

### 5. Sharing and security

The developer does not collect local analysis materials to sell them or share them for advertising
or tracking. If you choose to share/export files, copy results or attach support materials, subsequent
storage/sharing depends on the chosen service or Windows feature, including clipboard history,
cross-device synchronization and synchronized folders.

Projects, preferences, recovery copies and logs are not separately encrypted by the app.
Use appropriate user accounts, file permissions and device encryption, especially on shared computers.
Review materials for personal and unnecessary information before sharing them.

### 6. Support information and your choices

Information you voluntarily email is used to review and respond to your inquiry and related follow-up.
Support information is deleted when no longer needed, except where retention is required, such as by law.
Send requests to access, correct or delete support information to **loseless@naver.com**.
Email-service providers' own policies also apply to their processing and retention.

You can access, edit or delete local files, clear recent files, remove recovery copies and choose
whether to export/share. The developer cannot access or delete local data the developer does not hold.
Do not post images, projects, logs or personal information in public GitHub issues; contact us by email first.

### 7. Children and changes

The app is not directed at children and has no feature for collecting ages, child accounts or children's
personal information. If data practices change, this policy and its effective date will be updated.
