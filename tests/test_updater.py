import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bandwagon.updater import GitHubUpdateService, UpdateError, version_tuple


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
        "assets": [{
            "name": f"BandWagon_Setup_{version}.exe",
            "browser_download_url": download,
            "size": len(content),
            "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
        }],
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
            service = GitHubUpdateService("2.1.0")
            with patch("bandwagon.updater.subprocess.Popen") as popen:
                service.launch_installer(installer)
            self.assertEqual(
                popen.call_args.args[0][0], str(installer.resolve()))
            self.assertIn("/CLOSEAPPLICATIONS", popen.call_args.args[0])
            self.assertNotIn("shell", popen.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
