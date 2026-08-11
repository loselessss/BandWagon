"""GitHub Releases 기반 업데이트 확인, 다운로드, 설치 실행."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


GITHUB_REPOSITORY = "loselessss/BandWagon"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
_INSTALLER_RE = re.compile(
    r"^BandWagon_Setup_(\d+\.\d+\.\d+)\.exe$", re.IGNORECASE)
_PORTABLE_RE = re.compile(
    r"^BandWagon_Portable_(\d+\.\d+\.\d+)\.zip$", re.IGNORECASE)
_SHA256_RE = re.compile(r"^sha256:([0-9a-fA-F]{64})$")
_MAX_RELEASE_JSON_BYTES = 2 * 1024 * 1024


class UpdateError(RuntimeError):
    pass


class UpdateCancelled(UpdateError):
    pass


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int
    sha256: str


@dataclass(frozen=True)
class AvailableUpdate:
    version: str
    tag_name: str
    release_name: str
    release_notes: str
    release_url: str
    asset: object


@dataclass(frozen=True)
class UpdateDownloadProgress:
    completed_bytes: int
    total_bytes: int
    bytes_per_second: float


def version_tuple(value):
    match = _VERSION_RE.fullmatch(value.strip())
    if not match:
        raise UpdateError(f"지원하지 않는 버전 형식입니다: {value}")
    return tuple(int(part) for part in match.groups())


def _trusted_github_url(value, release_asset=False):
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        return False
    expected = f"/{GITHUB_REPOSITORY}/releases/"
    if not parsed.path.casefold().startswith(expected.casefold()):
        return False
    return not release_asset or "/download/" in parsed.path.casefold()


def is_portable_runtime(executable=None, frozen=None):
    """Inno 설치본에는 실행 파일 옆에 unins*.exe가 있다는 점으로 구분한다."""
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if not is_frozen:
        return False
    app_dir = Path(executable or sys.executable).resolve().parent
    return not any(app_dir.glob("unins*.exe"))


class GitHubUpdateService:
    def __init__(self, current_version, opener=urlopen, download_root=None,
                 portable=None, app_dir=None, popen=subprocess.Popen,
                 script_root=None):
        self.current_version = current_version
        self._open = opener
        self._download_root = download_root
        self.portable = is_portable_runtime() if portable is None else portable
        self.app_dir = Path(app_dir or sys.executable).resolve()
        if self.app_dir.is_file():
            self.app_dir = self.app_dir.parent
        self._popen = popen
        self._script_root = Path(script_root) if script_root else None

    def check(self):
        request = Request(
            GITHUB_API_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"BandWagon/{self.current_version}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with self._open(request, timeout=15) as response:
                payload = response.read(_MAX_RELEASE_JSON_BYTES + 1)
        except (HTTPError, URLError, OSError, TimeoutError) as error:
            raise UpdateError(f"GitHub 릴리스 정보를 확인하지 못했습니다: {error}")
        if len(payload) > _MAX_RELEASE_JSON_BYTES:
            raise UpdateError("GitHub 릴리스 응답이 허용 크기를 초과했습니다.")
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise UpdateError(f"GitHub 릴리스 응답을 읽지 못했습니다: {error}")
        if not isinstance(data, dict):
            raise UpdateError("GitHub 릴리스 응답 형식이 올바르지 않습니다.")

        tag_name = str(data.get("tag_name", "")).strip()
        latest_version = tag_name[1:] if tag_name.startswith("v") else tag_name
        if version_tuple(latest_version) <= version_tuple(self.current_version):
            return None
        release_url = str(data.get("html_url", ""))
        if not _trusted_github_url(release_url):
            raise UpdateError("GitHub 릴리스 주소를 신뢰할 수 없습니다.")
        return AvailableUpdate(
            version=latest_version,
            tag_name=tag_name,
            release_name=str(data.get("name") or tag_name),
            release_notes=str(data.get("body") or ""),
            release_url=release_url,
            asset=self._select_asset(data.get("assets"), latest_version),
        )

    def _select_asset(self, assets, version):
        if not isinstance(assets, list):
            return None
        expected = (f"BandWagon_Portable_{version}.zip" if self.portable
                    else f"BandWagon_Setup_{version}.exe")
        candidates = [
            item for item in assets if isinstance(item, dict)
            and str(item.get("name", "")).casefold() == expected.casefold()
        ]
        if not candidates:
            return None
        item = candidates[0]
        name = str(item.get("name", ""))
        download_url = str(item.get("browser_download_url", ""))
        name_pattern = _PORTABLE_RE if self.portable else _INSTALLER_RE
        if (Path(name).name != name or not name_pattern.fullmatch(name)
                or not _trusted_github_url(download_url, release_asset=True)):
            raise UpdateError("릴리스 설치 파일 정보가 안전하지 않습니다.")
        digest = str(item.get("digest") or "")
        match = _SHA256_RE.fullmatch(digest)
        return ReleaseAsset(
            name=name,
            download_url=download_url,
            size=max(0, int(item.get("size") or 0)),
            sha256=match.group(1).lower() if match else "",
        )

    def download(self, update, progress=None, cancel=None):
        asset = update.asset
        if asset is None:
            package = "포터블 ZIP" if self.portable else "Windows 설치 파일"
            raise UpdateError(f"이 릴리스에는 {package}이 없습니다.")
        if not asset.sha256:
            raise UpdateError("설치 파일의 SHA-256 정보가 없어 자동 업데이트할 수 없습니다.")
        root = self._download_root or Path(tempfile.gettempdir()) / "BandWagon" / "updates"
        root.mkdir(parents=True, exist_ok=True)
        destination = root / asset.name
        partial = destination.with_suffix(destination.suffix + ".part")
        digest = hashlib.sha256()
        completed = 0
        started = time.monotonic()
        request = Request(
            asset.download_url,
            headers={"User-Agent": f"BandWagon/{self.current_version}"},
        )
        try:
            with self._open(request, timeout=60) as response, partial.open("wb") as stream:
                while True:
                    if cancel is not None and cancel.is_set():
                        raise UpdateCancelled("업데이트 다운로드를 취소했습니다.")
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    stream.write(chunk)
                    digest.update(chunk)
                    completed += len(chunk)
                    if progress is not None:
                        elapsed = max(time.monotonic() - started, 0.001)
                        progress(UpdateDownloadProgress(
                            completed, asset.size, completed / elapsed))
                stream.flush()
                os.fsync(stream.fileno())
        except UpdateCancelled:
            partial.unlink(missing_ok=True)
            raise
        except (HTTPError, URLError, OSError, TimeoutError) as error:
            partial.unlink(missing_ok=True)
            raise UpdateError(f"업데이트 다운로드에 실패했습니다: {error}")
        if asset.size and completed != asset.size:
            partial.unlink(missing_ok=True)
            raise UpdateError(
                f"설치 파일 크기가 다릅니다: {completed:,} / {asset.size:,} bytes")
        if digest.hexdigest().lower() != asset.sha256:
            partial.unlink(missing_ok=True)
            raise UpdateError("설치 파일 SHA-256 검증에 실패했습니다.")
        os.replace(str(partial), str(destination))
        return destination

    def launch_installer(self, path):
        installer = Path(path).resolve()
        if (not installer.is_file() or installer.suffix.casefold() != ".exe"
                or not _INSTALLER_RE.fullmatch(installer.name)):
            raise UpdateError("실행할 업데이트 설치 파일이 올바르지 않습니다.")
        try:
            self._popen(
                [str(installer), "/SP-", "/CLOSEAPPLICATIONS"],
                close_fds=True,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise UpdateError(f"업데이트 설치 파일을 실행하지 못했습니다: {error}")

    def launch_update(self, path):
        if self.portable:
            self.launch_portable_update(path)
        else:
            self.launch_installer(path)

    def launch_portable_update(self, path):
        archive = Path(path).resolve()
        if (not archive.is_file() or archive.suffix.casefold() != ".zip"
                or not _PORTABLE_RE.fullmatch(archive.name)):
            raise UpdateError("실행할 포터블 업데이트 파일이 올바르지 않습니다.")
        executable = self.app_dir / "BandWagon.exe"
        if not executable.is_file():
            raise UpdateError("현재 포터블 실행 파일 위치를 확인할 수 없습니다.")
        parent = self.app_dir.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            script_root = self._script_root or Path(tempfile.gettempdir()) / "BandWagon" / "updates"
            script_root.mkdir(parents=True, exist_ok=True)
            script = script_root / f"apply-portable-{os.getpid()}.ps1"
            script.write_text(_PORTABLE_UPDATE_SCRIPT, encoding="utf-8-sig")
        except OSError as error:
            raise UpdateError(f"포터블 업데이트 도우미를 준비하지 못했습니다: {error}")
        powershell = Path(os.environ.get("WINDIR", r"C:\Windows")) / \
            "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        command = [
            str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(script), "-Archive", str(archive),
            "-InstallDir", str(self.app_dir), "-ProcessId", str(os.getpid()),
        ]
        try:
            self._popen(
                command, close_fds=True,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        except (OSError, subprocess.SubprocessError) as error:
            script.unlink(missing_ok=True)
            raise UpdateError(f"포터블 업데이트 도우미를 실행하지 못했습니다: {error}")


_PORTABLE_UPDATE_SCRIPT = r'''param(
    [Parameter(Mandatory=$true)][string]$Archive,
    [Parameter(Mandatory=$true)][string]$InstallDir,
    [Parameter(Mandatory=$true)][int]$ProcessId
)
$ErrorActionPreference = "Stop"
$parent = Split-Path -Parent $InstallDir
$token = [Guid]::NewGuid().ToString("N")
$staging = Join-Path $parent (".BandWagon-update-" + $token)
$backup = Join-Path $parent (".BandWagon-backup-" + $token)
$movedOld = $false
try {
    Wait-Process -Id $ProcessId -ErrorAction SilentlyContinue
    Expand-Archive -LiteralPath $Archive -DestinationPath $staging -Force
    $payload = Join-Path $staging "BandWagon"
    $newExe = Join-Path $payload "BandWagon.exe"
    if (-not (Test-Path -LiteralPath $newExe -PathType Leaf)) {
        throw "Portable archive does not contain BandWagon/BandWagon.exe"
    }
    Move-Item -LiteralPath $InstallDir -Destination $backup
    $movedOld = $true
    Move-Item -LiteralPath $payload -Destination $InstallDir
    $started = Start-Process -FilePath (Join-Path $InstallDir "BandWagon.exe") -PassThru
    Start-Sleep -Seconds 5
    if ($started.HasExited) { throw "Updated BandWagon exited during startup" }
    Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Archive -Force -ErrorAction SilentlyContinue
} catch {
    if ($movedOld) {
        Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
        Move-Item -LiteralPath $backup -Destination $InstallDir -ErrorAction SilentlyContinue
        Start-Process -FilePath (Join-Path $InstallDir "BandWagon.exe") -ErrorAction SilentlyContinue
    }
    Add-Content -LiteralPath (Join-Path $parent "BandWagon-update-error.log") -Value $_
} finally {
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}
'''
