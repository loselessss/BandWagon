"""Package the existing Windows x64 onedir build; signing is optional.

Unsigned output is explicitly named *_unsigned.msix and is never selected by
the app updater. MSIX_PFX_PATH / MSIX_PFX_PASSWORD supply optional signing.
"""
import argparse
import base64
import binascii
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def package_version(version):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("APP_VERSION must use x.y.z")
    parts = [int(part) for part in version.split('.')]
    if not 1 <= parts[0] <= 65535 or any(part > 65535 for part in parts):
        raise ValueError("MSIX version components must fit Windows package limits")
    return '.'.join(map(str, parts)) + '.0'


def read_version():
    source = (ROOT / 'bandwagon/meta.py').read_text(encoding='utf-8')
    match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', source, re.MULTILINE)
    if not match:
        raise ValueError("APP_VERSION not found")
    return match.group(1)


def sdk_tool(name, sdk_bin=None):
    if sdk_bin:
        tool = Path(sdk_bin) / name
        if tool.is_file():
            return tool
        raise FileNotFoundError(f"{name} not found in specified SDK directory")
    kit = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Windows Kits/10/bin'
    candidates = list(kit.glob(f'*/x64/{name}'))
    candidates.sort(key=lambda p: tuple(int(v) for v in p.parent.parent.name.split('.')
                                      if v.isdigit()), reverse=True)
    if candidates:
        return candidates[0]
    raise FileNotFoundError(f"Install Windows 10/11 SDK (Signing Tools): {name} missing")


def manifest(version, identity='loselessss.BandWagon', publisher='CN=BandWagon',
             display_name='BandWagon', publisher_display_name='BandWagon'):
    if not re.fullmatch(r'[A-Za-z0-9.-]{3,50}', identity):
        raise ValueError("Invalid MSIX identity name")
    if not publisher.strip():
        raise ValueError("Publisher cannot be empty")
    if not display_name.strip() or not publisher_display_name.strip():
        raise ValueError('Display names cannot be empty')
    text = (ROOT / 'packaging/msix/AppxManifest.xml').read_text(encoding='utf-8')
    for key, value in {'IDENTITY': identity, 'PUBLISHER': publisher,
                       'VERSION': package_version(version), 'DISPLAY_NAME': display_name,
                       'PUBLISHER_DISPLAY_NAME': publisher_display_name}.items():
        text = text.replace('@' + key + '@', escape(value, {'"': '&quot;'}))
    ET.fromstring(text)
    return text


def prepare_layout(payload, layout, version, identity, publisher,
                   display_name='BandWagon', publisher_display_name='BandWagon'):
    if not (payload / 'BandWagon.exe').is_file() or not (payload / '_internal').is_dir():
        raise ValueError("Build dist/BandWagon first: python scripts/build_windows.py")
    if any(payload.rglob('unins*.exe')):
        raise ValueError("Use a clean onedir build, not an installed application")
    shutil.copytree(payload, layout, dirs_exist_ok=True)
    (layout / 'AppxManifest.xml').write_text(
        manifest(version, identity, publisher, display_name, publisher_display_name), encoding='utf-8')
    from PIL import Image
    assets = layout / 'Assets'
    assets.mkdir(exist_ok=True)
    for filename, size, icon in (
            ('StoreLogo.png', 50, 'bandwagon.ico'),
            ('Square44x44Logo.png', 44, 'bandwagon.ico'),
            ('Square150x150Logo.png', 150, 'bandwagon.ico'),
            ('CompositeLogo.png', 44, 'bandwagon_composite.ico')):
        with Image.open(ROOT / icon) as source:
            image = source.convert('RGBA')
        image.thumbnail((round(size * .8), round(size * .8)), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (size, size))
        canvas.alpha_composite(image, ((size - image.width) // 2, (size - image.height) // 2))
        canvas.save(assets / filename)


def build(args):
    if sys.platform != 'win32':
        raise ValueError("MSIX packaging requires Windows and Windows SDK")
    version = read_version()
    store = getattr(args, 'store', False)
    if store and args.require_signed:
        raise ValueError('--store prepares an unsigned Store submission; do not use --require-signed')
    settings = json.loads((ROOT / 'packaging/msix/store.json').read_text(encoding='utf-8')) if store else {
        'identity': args.identity, 'publisher': args.publisher,
        'display_name': getattr(args, 'display_name', 'BandWagon'),
        'publisher_display_name': getattr(args, 'publisher_display_name', 'BandWagon'),
    }
    makeappx = sdk_tool('makeappx.exe', args.sdk_bin)
    pfx = None if store else os.environ.get('MSIX_PFX_PATH')
    encoded_pfx = None if store else os.environ.get('MSIX_PFX_BASE64')
    signing = bool(pfx or encoded_pfx)
    if pfx and encoded_pfx:
        raise ValueError("Set only one of MSIX_PFX_PATH and MSIX_PFX_BASE64")
    if args.require_signed and not signing:
        raise ValueError("MSIX_PFX_PATH or MSIX_PFX_BASE64 is required for a signed package")
    if pfx and not Path(pfx).is_file():
        raise ValueError("MSIX_PFX_PATH does not point to a certificate file")
    signtool = sdk_tool('signtool.exe', args.sdk_bin) if signing else None
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Unique staging folders avoid touching existing builds or user data.
    with tempfile.TemporaryDirectory(prefix='bandwagon-msix-') as temporary:
        stage = Path(temporary)
        if encoded_pfx:
            try:
                certificate = base64.b64decode(encoded_pfx, validate=True)
            except (ValueError, binascii.Error):
                raise ValueError("MSIX_PFX_BASE64 is not valid base64") from None
            if not certificate:
                raise ValueError("MSIX_PFX_BASE64 is empty")
            pfx = str(stage / 'signing.pfx')
            Path(pfx).write_bytes(certificate)
        layout = stage / 'layout'
        prepare_layout(Path(args.payload).resolve(), layout, version, settings['identity'], settings['publisher'],
                       settings['display_name'], settings['publisher_display_name'])
        package = stage / 'BandWagon.msix'
        subprocess.run([str(makeappx), 'pack', '/d', str(layout), '/p', str(package), '/o'], check=True)
        if pfx:
            command = [str(signtool), 'sign', '/fd', 'SHA256', '/f', str(Path(pfx).resolve())]
            password = os.environ.get('MSIX_PFX_PASSWORD')
            if password:
                command += ['/p', password]
            if args.timestamp_url:
                command += ['/tr', args.timestamp_url, '/td', 'SHA256']
            command.append(str(package))
            subprocess.run(command, check=True)
            subprocess.run([str(signtool), 'verify', '/pa', '/v', str(package)], check=True)
        suffix = '' if signing else '_unsigned'
        destination = output / f'BandWagon_{version}_x64{suffix}.msix'
        shutil.copy2(package, destination)
    print(f"MSIX built: {destination}")
    if not signing:
        print('Store submission: Microsoft signs the package after submission.' if store else
              "Unsigned build: sign with a trusted certificate before normal installation/distribution.")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', default=str(ROOT / 'dist/BandWagon'))
    parser.add_argument('--output', default=str(ROOT / 'Output'))
    parser.add_argument('--sdk-bin')
    parser.add_argument('--identity', default=os.environ.get('MSIX_IDENTITY', 'loselessss.BandWagon'))
    parser.add_argument('--publisher', default=os.environ.get('MSIX_PUBLISHER', 'CN=BandWagon'))
    parser.add_argument('--timestamp-url', default=os.environ.get('MSIX_TIMESTAMP_URL'))
    parser.add_argument('--require-signed', action='store_true')
    parser.add_argument('--store', action='store_true', help='Use reserved Store identity; never apply a local certificate')
    parser.add_argument('--display-name', default='BandWagon')
    parser.add_argument('--publisher-display-name', default='BandWagon')
    args = parser.parse_args()
    try:
        build(args)
    except subprocess.CalledProcessError as error:
        # A signing command may contain the PFX password: never print its args.
        raise SystemExit(f"MSIX tool failed (exit {error.returncode}). See tool diagnostics above.") from None
    except (ValueError, OSError) as error:
        raise SystemExit(str(error)) from None


if __name__ == '__main__':
    main()
