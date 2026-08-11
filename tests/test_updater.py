import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from bandwagon.updater import (
    GitHubUpdateService, UpdateError, _PORTABLE_UPDATE_SCRIPT,
    is_portable_runtime, version_tuple,
)


class FakeResponse:
    def __init__(self, payload):
        self.stream = io.BytesIO(payload)

    def __enter__(self):
        return self

    def __exit__(self, _kind, _error, _traceback):
        return False

    def read(self, size=-1):
        return self.stream.read(size)


def release_payload(tag="v2.2.0", content=b"installer", url=None):
    version = tag.lstrip("v")
    download = url or (
        "https://github.com/loselessss/BandWagon/releases/download/"
        f"{tag}/BandWagon_Setup_{version}.exe")
    return json.dumps({
        "tag_name": tag,
        "name": f"BandWagon {version}",
        "body": "변경 내용",
        "html_url": (
            "https://github.com/loselessss/BandWagon/releases/tag/" + tag),
        "assets": [
            {
                "name": f"BandWagon_Setup_{version}.exe",
                "browser_download_url": download,
                "size": len(content),
                "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
            },
            {
                "name": f"BandWagon_Portable_{version}.zip",
                "browser_download_url": (
                    "https://github.com/loselessss/BandWagon/releases/download/"
                    f"{tag}/BandWagon_Portable_{version}.zip"),
                "size": len(content),
                "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
            },
        ],
    }).encode("utf-8")


class UpdateServiceTests(unittest.TestCase):
    def test_version_comparison_is_numeric(self):
        self.assertGreater(version_tuple("v2.10.0"), version_tuple("2.9.9"))

    def test_newer_release_selects_exact_versioned_installer(self):
        service = GitHubUpdateService(
            "2.1.0", opener=lambda _request, timeout: FakeResponse(
                release_payload()))
        update = service.check()
        self.assertEqual(update.version, "2.2.0")
        self.assertEqual(update.asset.name, "BandWagon_Setup_2.2.0.exe")
        self.assertEqual(len(update.asset.sha256), 64)

    def test_portable_runtime_selects_exact_portable_zip(self):
        service = GitHubUpdateService(
            "2.1.0", portable=True,
            opener=lambda _request, timeout: FakeResponse(release_payload()))
        update = service.check()
        self.assertEqual(update.asset.name, "BandWagon_Portable_2.2.0.zip")

    def test_runtime_detection_uses_inno_uninstaller_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable = root / "BandWagon.exe"
            executable.write_bytes(b"MZ")
            self.assertTrue(is_portable_runtime(executable, frozen=True))
            (root / "unins000.exe").write_bytes(b"MZ")
            self.assertFalse(is_portable_runtime(executable, frozen=True))
            self.assertFalse(is_portable_runtime(executable, frozen=False))

    def test_same_release_is_current(self):
        service = GitHubUpdateService(
            "2.2.0", opener=lambda _request, timeout: FakeResponse(
                release_payload()))
        self.assertIsNone(service.check())

    def test_untrusted_asset_is_rejected(self):
        service = GitHubUpdateService(
            "2.1.0", opener=lambda _request, timeout: FakeResponse(
                release_payload(url="https://example.com/setup.exe")))
        with self.assertRaisesRegex(UpdateError, "안전하지"):
            service.check()

    def test_download_verifies_hash_and_reports_progress(self):
        content = b"verified installer"
        calls = [release_payload(content=content), content]

        def opener(_request, timeout):
            return FakeResponse(calls.pop(0))

        with tempfile.TemporaryDirectory() as temp:
            service = GitHubUpdateService(
                "2.1.0", opener=opener, download_root=Path(temp))
            update = service.check()
            progress = []
            result = service.download(update, progress=progress.append)
            self.assertEqual(result.read_bytes(), content)
            self.assertEqual(progress[-1].completed_bytes, len(content))

    def test_download_rejects_tampered_installer(self):
        calls = [release_payload(content=b"expected"), b"tampered"]

        def opener(_request, timeout):
            return FakeResponse(calls.pop(0))

        with tempfile.TemporaryDirectory() as temp:
            service = GitHubUpdateService(
                "2.1.0", opener=opener, download_root=Path(temp))
            update = service.check()
            with self.assertRaisesRegex(UpdateError, "SHA-256"):
                service.download(update)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_installer_launch_does_not_use_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            installer = Path(temp) / "BandWagon_Setup_2.2.0.exe"
            installer.write_bytes(b"MZ")
            with patch("bandwagon.updater.subprocess.Popen") as popen:
                service = GitHubUpdateService("2.1.0", popen=popen)
                service.launch_installer(installer)
            self.assertEqual(
                popen.call_args.args[0][0], str(installer.resolve()))
            self.assertIn("/CLOSEAPPLICATIONS", popen.call_args.args[0])
            self.assertNotIn("shell", popen.call_args.kwargs)

    def test_portable_update_launches_external_rollback_helper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "BandWagon"
            app_dir.mkdir()
            (app_dir / "BandWagon.exe").write_bytes(b"MZ")
            archive = root / "BandWagon_Portable_2.2.1.zip"
            archive.write_bytes(b"zip")
            with patch("bandwagon.updater.subprocess.Popen") as popen:
                service = GitHubUpdateService(
                    "2.2.0", portable=True, app_dir=app_dir,
                    popen=popen, script_root=root / "scripts")
                service.launch_update(archive)
            command = popen.call_args.args[0]
            self.assertIn("-ExecutionPolicy", command)
            self.assertIn("Bypass", command)
            self.assertIn(str(archive.resolve()), command)
            self.assertIn(str(app_dir.resolve()), command)
            self.assertNotIn("shell", popen.call_args.kwargs)
            scripts = list((root / "scripts").glob("*.ps1"))
            self.assertEqual(len(scripts), 1)
            script_text = scripts[0].read_text(encoding="utf-8-sig")
            self.assertIn("Move-Item -LiteralPath $backup", script_text)
            self.assertIn("Updated BandWagon exited during startup", script_text)

    @unittest.skipUnless(os.name == "nt", "Windows portable updater")
    def test_portable_helper_restores_old_folder_when_new_app_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app_dir = root / "BandWagon"
            app_dir.mkdir()
            shutil.copy2(Path(os.environ["WINDIR"]) / "System32" / "where.exe",
                         app_dir / "BandWagon.exe")
            (app_dir / "old-version.txt").write_text("keep", encoding="utf-8")
            archive = root / "BandWagon_Portable_2.2.1.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                # 실행할 수 없는 파일로 시작 실패를 유도해 롤백 경로를 검증한다.
                bundle.writestr("BandWagon/BandWagon.exe", b"not an executable")
                bundle.writestr("BandWagon/new-version.txt", "replace")
            script = root / "apply.ps1"
            script.write_text(_PORTABLE_UPDATE_SCRIPT, encoding="utf-8-sig")
            powershell = (
                Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" /
                "WindowsPowerShell" / "v1.0" / "powershell.exe"
            )
            subprocess.run(
                [str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(script), "-Archive", str(archive),
                 "-InstallDir", str(app_dir), "-ProcessId", "999999"],
                check=True, timeout=30,
            )
            self.assertEqual(
                (app_dir / "old-version.txt").read_text(encoding="utf-8"), "keep")
            self.assertFalse((app_dir / "new-version.txt").exists())
            self.assertTrue((root / "BandWagon-update-error.log").is_file())
            time.sleep(1)


if __name__ == "__main__":
    unittest.main()
