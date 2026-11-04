"""Check package provenance, privacy, architecture and installer manifests without installing."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import types
import zipfile

import pefile
from PyInstaller.archive.readers import CArchiveReader
try:
    from .build_installer import verified_payload
    from .check_public_files import inspect_file
except ImportError:
    from build_installer import verified_payload
    from check_public_files import inspect_file

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_icon_resources(pe, icon_path):
    """Compare the primary RT_GROUP_ICON and its actual RT_ICON payloads."""
    ico = icon_path.read_bytes()
    frames = {}
    for offset in range(6, 6 + 16 * struct.unpack_from('<H', ico, 4)[0], 16):
        size, start = struct.unpack_from('<II', ico, offset + 8)
        frames[ico[offset] or 256] = ico[start:start + size]
    assert set(frames) == {16, 24, 32, 48, 64, 128, 256}

    def resource_bytes(entry):
        data = entry.directory.entries[0].data.struct
        return pe.get_data(data.OffsetToData, data.Size)

    resources = {entry.id: entry for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries}
    icons = {entry.id: resource_bytes(entry) for entry in resources[3].directory.entries}
    group = resource_bytes(resources[14].directory.entries[0])
    actual = {}
    for offset in range(6, 6 + 14 * struct.unpack_from('<H', group, 4)[0], 14):
        identifier = struct.unpack_from('<H', group, offset + 12)[0]
        actual[group[offset] or 256] = icons[identifier]
    assert actual == frames, 'Primary executable icons differ from packaged app.ico'


def verify(package):
    package = package.resolve()
    info, identity = verified_payload(package)
    assert not any(p.suffix in ('.dpapi', '.bak', '.log') or p.name == 'config.json' for p in package.rglob('*'))
    for name, digest in info['sources'].items():
        path = ROOT / name
        assert path.resolve().is_relative_to(ROOT) and sha(path.read_bytes()) == digest, 'Source changed since build: ' + name
    with zipfile.ZipFile(package / 'source' / f"TangerineXiaoAiAssistant-{info['version']}-source.zip") as source:
        assert set(source.namelist()) == set(info['sources'])
        for name, digest in info['sources'].items():
            data = source.read(name)
            assert sha(data) == digest, 'Corresponding source differs: ' + name
            assert not inspect_file(name, data), 'Private source content detected: ' + name
    binaries = [package / 'TangerineXiaoAiAssistant.exe', package / 'TangerineXiaoAiAssistant-Desktop.exe']
    setup = package.parent / f"{identity['directory_name']}-{info['version']}-windows-x64-Setup.exe"
    for binary in binaries + [setup]:
        pe = pefile.PE(str(binary))
        verify_icon_resources(pe, package / 'app.ico')
        if binary != setup:
            assert pe.FILE_HEADER.Machine == 0x8664, 'Runtime executable must be x64'
        assert pe.OPTIONAL_HEADER.DATA_DIRECTORY[4].Size == 0, 'Review signature handling if signing is introduced'
        manifests = []
        for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            if entry.id == 24:
                for resource in entry.directory.entries:
                    for language in resource.directory.entries:
                        data = language.data.struct
                        manifests.append(pe.get_data(data.OffsetToData, data.Size))
        assert any(b'asInvoker' in data for data in manifests), 'Unexpected elevation requirement'
        pe.close()
    for binary in binaries:
        archive = CArchiveReader(str(binary))
        assert json.loads(archive.extract('app-identity.json')) == identity
        assert archive.extract('LICENSE') == (ROOT / 'LICENSE').read_bytes()
        for name, entry in archive.toc.items():
            if entry[-1] == 'z':
                pyz = archive.open_embedded_archive(name)
                for module in pyz.toc:
                    if module.startswith('xiaoai_pc'):
                        pending = [pyz.extract(module)]
                        while pending:
                            code = pending.pop()
                            if not isinstance(code, types.CodeType):
                                continue
                            assert not re.match(r'[A-Za-z]:|/', code.co_filename), 'Private bytecode filename'
                            pending.extend(c for c in code.co_consts if isinstance(c, types.CodeType))
    checksums = (package.parent / 'SHA256SUMS.txt').read_text('utf-8').splitlines()
    assert checksums
    for line in checksums:
        digest, name = line.split('  ', 1)
        path = package.parent / name
        assert path.resolve().parent == package.parent and sha(path.read_bytes()) == digest
    portable = package.parent / f"{identity['directory_name']}-{info['version']}-windows-x64.zip"
    with zipfile.ZipFile(portable) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {"TangerineXiaoAiAssistant/" + p.relative_to(package).as_posix() + ('/' if p.is_dir() else '')
                                            for p in [package, *package.rglob('*')] if p != package} | {"TangerineXiaoAiAssistant/"}
        for path in package.rglob('*'):
            if path.is_file():
                assert archive.read('TangerineXiaoAiAssistant/' + path.relative_to(package).as_posix()) == path.read_bytes()
    print('Package verification: PASS (corresponding source, exact payload, privacy, x64, asInvoker, unsigned, SHA256, ZIP)')
    return info


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-dir', type=Path, required=True)
    args = parser.parse_args()
    verify(args.package_dir)
