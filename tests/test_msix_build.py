import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from PIL import Image
from scripts import build_msix


NS = {'p': 'http://schemas.microsoft.com/appx/manifest/foundation/windows10',
      'uap': 'http://schemas.microsoft.com/appx/manifest/uap/windows10',
      'uap3': 'http://schemas.microsoft.com/appx/manifest/uap/windows10/3'}


class MsixBuildTest(unittest.TestCase):
    def test_manifest_keeps_file_paths_quoted_and_matches_app_version(self):
        root = ET.fromstring(build_msix.manifest('2.8.0', publisher='CN=Example & Research'))
        identity = root.find('p:Identity', NS)
        self.assertEqual(identity.get('Version'), '2.8.0.0')
        self.assertEqual(identity.get('Publisher'), 'CN=Example & Research')
        self.assertEqual(identity.get('ProcessorArchitecture'), 'x64')
        extensions = root.findall('.//uap3:FileTypeAssociation', NS)
        self.assertEqual(len(extensions), 2)
        for extension in extensions:
            self.assertEqual(extension.get('Parameters'), '"%1"')
        self.assertEqual({node.text for node in root.findall('.//uap:FileType', NS)},
                         {'.bandwagon', '.bwcomposite'})

    def test_package_version_rejects_incompatible_values(self):
        for version in ('0.1.0', '2.8', '2.8.0.1', '2.65536.0', 'v2.8.0'):
            with self.subTest(version=version), self.assertRaises(ValueError):
                build_msix.package_version(version)

    def test_layout_contains_runtime_and_valid_logos(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = root / 'payload'
            (payload / '_internal').mkdir(parents=True)
            (payload / 'BandWagon.exe').write_bytes(b'MZ')
            (payload / '_internal/runtime.dll').write_bytes(b'dll')
            layout = root / 'layout'
            build_msix.prepare_layout(payload, layout, '2.8.0', 'loselessss.BandWagon', 'CN=BandWagon')
            manifest = ET.parse(layout / 'AppxManifest.xml').getroot()
            self.assertEqual((layout / '_internal/runtime.dll').read_bytes(), b'dll')
            for node in manifest.iter():
                for path in (node.get('Square44x44Logo'), node.get('Square150x150Logo'),
                             node.text if node.tag.endswith('Logo') else None):
                    if not path:
                        continue
                    with Image.open(layout / path.replace('\\', '/')) as logo:
                        self.assertEqual(logo.mode, 'RGBA')
                        self.assertGreater(logo.width, 0)
            (payload / 'unins000.exe').write_bytes(b'MZ')
            with self.assertRaisesRegex(ValueError, 'clean onedir'):
                build_msix.prepare_layout(payload, root / 'bad', '2.8.0', 'loselessss.BandWagon', 'CN=BandWagon')

    def test_signing_failure_never_prints_password(self):
        password = 'private-test-secret'
        failure = subprocess.CalledProcessError(1, ['signtool', '/p', password])
        with patch('sys.argv', ['build_msix.py']), patch.object(build_msix, 'build', side_effect=failure):
            with self.assertRaises(SystemExit) as caught:
                build_msix.main()
        self.assertNotIn(password, str(caught.exception))

    def test_unsigned_build_has_separate_name_and_no_signing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = type('Args', (), dict(sdk_bin=None, require_signed=False,
                                        payload=str(root / 'payload'), output=str(root / 'output'),
                                        identity='loselessss.BandWagon', publisher='CN=BandWagon'))()
            def fake_tool(command, check):
                Path(command[command.index('/p') + 1]).write_bytes(b'package')
            with patch.dict(os.environ, {}, clear=True), patch.object(build_msix.sys, 'platform', 'win32'), \
                    patch.object(build_msix, 'sdk_tool', return_value=Path('makeappx.exe')), \
                    patch.object(build_msix, 'prepare_layout'), patch.object(build_msix.subprocess, 'run', side_effect=fake_tool), \
                    patch('sys.stdout', new_callable=io.StringIO):
                result = build_msix.build(args)
            self.assertTrue(result.name.endswith('_unsigned.msix'))
            self.assertFalse((result.parent / result.name.replace('_unsigned', '')).exists())


if __name__ == '__main__':
    unittest.main()
