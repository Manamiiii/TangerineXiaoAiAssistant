"""Read-only check of an existing portable shortcut and its proposed build.

No application launch, credential read, migration, shortcut write or installation.
Output is local evidence and can contain machine paths; never commit the report.
"""
import argparse
import dis
import hashlib
import json
from pathlib import Path
import sys

from PyInstaller.archive.readers import CArchiveReader
from xiaoai_pc.identity import PRODUCTION

try:
    from .build_installer import verified_payload
except ImportError:
    from build_installer import verified_payload

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_EXE = "TangerineXiaoAiAssistant-Desktop.exe"


def literal_version(code):
    previous = None
    for instruction in dis.get_instructions(code):
        if instruction.opname == "STORE_NAME" and instruction.argval == "__version__":
            if previous and previous.opname == "LOAD_CONST" and isinstance(previous.argval, str):
                return previous.argval
            break
        previous = instruction
    raise ValueError("Embedded version is not a literal; review the build")


def embedded_version(binary):
    archive = CArchiveReader(str(binary))
    if json.loads(archive.extract("app-identity.json")) != PRODUCTION:
        raise ValueError("Expected the production application identity")
    for name, entry in archive.toc.items():
        if entry[-1] == "z":
            return literal_version(archive.open_embedded_archive(name).extract("xiaoai_pc"))
    raise ValueError("Embedded application module not found")


def package_evidence(folder):
    folder = folder.resolve(strict=True)
    if not folder.is_relative_to(ROOT):
        raise ValueError("Only builds inside this checkout are inspected")
    info, identity = verified_payload(folder)
    if identity != PRODUCTION:
        raise ValueError("A fixture must never replace the daily entry")
    binary = folder / DESKTOP_EXE
    version = embedded_version(binary)
    if version != info["version"]:
        raise ValueError("Embedded version differs from build manifest")
    return {"directory": str(folder), "version": version,
            "desktop_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}


def inspect(shortcut, expected_package):
    from comtypes.client import CreateObject
    from comtypes.persist import IPersistFile, STGM_READ
    from comtypes.shelllink import ShellLink, IShellLinkW
    shortcut = shortcut.resolve(strict=True)
    if shortcut.suffix.lower() != ".lnk":
        raise ValueError("An existing .lnk is required")
    link = CreateObject(ShellLink, interface=IShellLinkW)
    link.QueryInterface(IPersistFile).Load(str(shortcut), STGM_READ)
    target = Path(link.GetPath(0))
    if target.name != DESKTOP_EXE:
        raise ValueError("Shortcut does not directly launch the expected portable desktop EXE")
    actual = package_evidence(target.parent)
    expected = package_evidence(expected_package)
    matches = target.resolve() == expected_package.resolve() / DESKTOP_EXE
    return {"shortcut": str(shortcut), "target": str(target), "arguments": link.GetArguments(),
            "working_directory": link.GetWorkingDirectory(), "icon": link.GetIconLocation(),
            "current_entry": actual, "proposed_build": expected, "entry_matches_proposed_build": matches,
            "running_instance_verified": False,
            "note": "Static payload check only. Review processes and migration authorization before switching."}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shortcut", type=Path, required=True)
    parser.add_argument("--expected-package", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.shortcut, args.expected_package)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["entry_matches_proposed_build"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
