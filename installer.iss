; ============================================================
;  BandWagon 인스톨러 (Inno Setup 스크립트)
; ============================================================
; 전제: build_exe.bat을 먼저 실행해 dist\BandWagon\ 폴더(exe + 지원파일)가
; 이미 만들어져 있어야 한다(이 스크립트는 그 결과물만 패키징한다).
;
; 컴파일 방법(둘 중 하나):
;   1) Inno Setup Compiler에서 이 파일을 열고 Build > Compile
;   2) 명령줄: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
;
; 결과물: Output\BandWagon_Setup_<버전>.exe — 이 파일 하나를 배포하면
; 받는 사람이 더블클릭해서 평범한 설치 마법사(시작 메뉴/바탕화면 바로가기,
; 제어판 "프로그램 추가/제거"에 제거 항목까지)로 설치할 수 있다.
;
; 버전을 올릴 때는 아래 MyAppVersion과 bandwagon/meta.py의 APP_VERSION을
; 같이 맞춰 주세요(서로 자동 동기화되지 않음).
#define MyAppName "BandWagon"
#define MyAppVersion "2.0.4"
#define MyAppPublisher "BandWagon"
#define MyAppExeName "BandWagon.exe"
#define MyAppIcon "bandwagon.ico"

[Setup]
AppId={{B4A1D7E0-3F6C-4B8A-9C2D-A1B2C3D4E5F6}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={userpf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; dist\BandWagon\ 폴더가 없으면 컴파일 시점에 바로 에러로 알려준다(빌드 순서를 깜빡했을 때).
SourceDir=.
OutputDir=Output
OutputBaseFilename=BandWagon_Setup_{#MyAppVersion}
SetupIconFile={#MyAppIcon}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; ── 설치 권한: 사용자별 설치(관리자 권한/UAC 불필요) ──────────────────
; 처음엔 Program Files에 설치하는 관리자 권한 방식(PrivilegesRequired=admin)
; 으로 만들었는데, 그러면 설치 마법사를 실행할 때마다 UAC 창이 뜬다(이건
; 버그가 아니라 Program Files에 쓰려면 으레 필요한 절차). 그 UAC 창이
; 거슬린다는 피드백을 받아 사용자별 설치(lowest)로 바꿨다.
; DefaultDirName이 이미 {userpf}(관리자 권한 없는 사용자 폴더, 보통
; %LocalAppData%\Programs 아래)로 돼 있으니 PrivilegesRequired만 lowest로
; 맞추면 된다. 트레이드오프: 한 컴퓨터를 여러 계정이 같이 쓴다면 계정마다
; 따로 설치해야 한다(시스템 전체에 한 번 설치해서 공유하는 방식이 아님).
; 그 공유 방식(+UAC)으로 되돌리려면 아래 줄을 admin으로, DefaultDirName을
; {autopf}로 바꾸면 된다.
PrivilegesRequired=lowest

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; --onedir 빌드 결과(dist\BandWagon\ 폴더 전체 — exe + _internal 등 지원
; 파일들)를 그대로 복사한다. --onefile로 다시 바꿔 빌드했다면 이 줄을
; Source: "dist\BandWagon.exe"; DestDir: "{app}"; Flags: ignoreversion 로 바꾸세요.
Source: "dist\BandWagon\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; .bandwagon 확장자를 이 앱에 연결 — 탐색기에서 더블클릭하면 BandWagon.exe가
; 그 경로를 커맨드라인 인자로 받아서 뜬다(bandwagon/app.py의 Analyzer.__init__ ->
; open_path_smart가 확장자를 보고 프로젝트로 연다).
;
; Root는 HKCR이 아니라 HKA를 쓴다 — 처음엔 HKCR로 했다가 실제 설치에서
; "RegCreateKeyEx 실패, 액세스가 거부되었습니다"로 막혔다. HKCR은 그냥
; 문자 그대로 HKEY_CLASSES_ROOT에 쓰려고 시도하는데, 이건 관리자 권한
; 없이는(PrivilegesRequired=lowest) 쓸 수 없다. HKA(Inno Setup 6.1+ 전용
; 루트)는 설치 권한에 맞춰 HKLM(관리자 설치) 또는 HKCU(지금처럼 lowest)로
; 알아서 골라 쓴다 — 실제 설치로만 드러난 문제라 시뮬레이션으로는 못
; 잡았다.
;
; 주의: HKA는 HKCR과 달리 "Classes" 경로를 자동으로 붙여주지 않는다 —
; 그냥 HKLM 또는 HKCU 루트 자체를 가리킬 뿐이라, Subkey에 반드시
; "Software\Classes\"를 직접 붙여야 한다. 처음엔 이걸 빠뜨려서
; HKEY_CURRENT_USER\.bandwagon(최상위)에 써졌고, 탐색기가 보는
; HKEY_CURRENT_USER\Software\Classes\.bandwagon에는 아무것도 없어 파일
; 연결이 전혀 인식되지 않는 문제가 있었다(실제 설치 후 regedit으로
; 확인해서 발견).
; uninsdeletevalue/uninsdeletekey라 제거 시 등록도 같이 지워진다.
Root: HKA; Subkey: "Software\Classes\.bandwagon"; ValueType: string; ValueName: ""; ValueData: "BandWagon.Project"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\BandWagon.Project"; ValueType: string; ValueName: ""; ValueData: "BandWagon Project"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\BandWagon.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKA; Subkey: "Software\Classes\BandWagon.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

; .bwcomposite(웨스턴 블롯 합성 파일)도 마찬가지로 연결한다. 아이콘은 앱
; 아이콘 그대로 쓰지 않고 색만 다르게 만든 bandwagon_composite.ico를 따로
; 써서(build_exe.bat이 exe 옆에 그대로 복사해 둠), 탐색기에서 프로젝트
; 파일과 한눈에 구분되게 한다.
Root: HKA; Subkey: "Software\Classes\.bwcomposite"; ValueType: string; ValueName: ""; ValueData: "BandWagon.Composite"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\BandWagon.Composite"; ValueType: string; ValueName: ""; ValueData: "BandWagon Western Blot Composite"; Flags: uninsdeletekey
; PyInstaller 6.x onedir는 --add-data로 넣은 파일을 exe 옆이 아니라
; _internal\ 폴더 안에 둔다(bandwagon.ico도 마찬가지 — meta.resource_path()가
; sys._MEIPASS로 찾는 이유).
Root: HKA; Subkey: "Software\Classes\BandWagon.Composite\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\_internal\bandwagon_composite.ico"
Root: HKA; Subkey: "Software\Classes\BandWagon.Composite\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
// 설치 마법사에서 고른 언어를 앱 첫 실행 언어로 넘겨준다. 안 하면 앱은
// bandwagon/i18n.py의 load_lang_setting()이 OS 로캘로 알아서 추측하는데,
// 그러면 설치 때 고른 언어가 앱 언어에 전혀 반영되지 않아 두 선택이
// 서로 무관해 보이는 문제가 있었다. 이미 저장된 설정(앱에서 직접 언어를
// 바꾼 적 있는 재설치/업데이트)이 있으면 덮어쓰지 않는다.
procedure CurStepChanged(CurStep: TSetupStep);
var
  LangFile, LangCode: string;
begin
  if CurStep = ssPostInstall then
  begin
    if ActiveLanguage = 'korean' then
      LangCode := 'ko'
    else
      LangCode := 'en';
    LangFile := ExpandConstant('{%USERPROFILE}\.bandwagon_lang.json');
    if not FileExists(LangFile) then
      SaveStringToFile(LangFile, '{"lang": "' + LangCode + '"}', False);
  end;
end;
