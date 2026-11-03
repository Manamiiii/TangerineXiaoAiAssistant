"""Build console/desktop executables and a portable zip without elevation."""
from importlib import metadata
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "TangerineXiaoAiAssistant"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["version"]
PYSTRAY_SOURCE_SHA256 = "99fb0f7ec3a551e6c96d3946ecfce0e9dc04bac7994fa64ae348921a634af70e"


def source_archives(destination, custom_library=None):
    """Ship corresponding library and application source, including rebuild scripts."""
    destination.mkdir(parents=True, exist_ok=True)
    library = destination / "pystray-0.19.5.zip"
    if custom_library is not None:
        shutil.copy2(custom_library, library)
    elif not library.exists():
        with urlopen("https://codeload.github.com/moses-palmer/pystray/zip/refs/tags/v0.19.5", timeout=60) as response:
            library.write_bytes(response.read())
    if custom_library is None and hashlib.sha256(library.read_bytes()).hexdigest() != PYSTRAY_SOURCE_SHA256:
        raise RuntimeError("pystray source checksum mismatch")
    dist = metadata.distribution("pystray")
    if dist.version != "0.19.5":
        raise RuntimeError("Review corresponding sources when changing pystray version")
    with zipfile.ZipFile(library) as upstream:
        for item in dist.files:
            if str(item).startswith("pystray/") and item.suffix == ".py":
                installed = Path(dist.locate_file(item)).read_bytes().replace(b"\r\n", b"\n")
                source = upstream.read("pystray-0.19.5/lib/" + item.as_posix()).replace(b"\r\n", b"\n")
                if installed != source:
                    raise RuntimeError("Modified pystray detected: include matching source before distribution")
    write_application_source(destination / f"{NAME}-{VERSION}-source.zip")


def source_files(root=ROOT):
    """Only explicitly reviewed files belong in a distribution (also works without Git)."""
    entries = (root / "scripts/source-files.txt").read_text("utf-8").splitlines()
    paths = []
    for entry in entries:
        if not entry or entry.startswith("#"):
            continue
        path = root / entry
        if (Path(entry).is_absolute() or ".." in Path(entry).parts
                or not path.resolve().is_relative_to(root.resolve()) or not path.is_file()
                or path.is_symlink()):
            raise RuntimeError("Invalid or missing distribution manifest entry")
        if path in paths:
            raise RuntimeError("Duplicate distribution manifest entry")
        paths.append(path)
    # Do not build imported application code without accompanying source.
    if any(p not in paths for p in (root / "src").rglob("*.py")):
        raise RuntimeError("Add new application modules to scripts/source-files.txt")
    return paths


def write_application_source(destination, root=ROOT):
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in source_files(root):
            archive.write(path, path.relative_to(root))


def copy_public_files(destination, root=ROOT):
    for path in source_files(root):
        relative = path.relative_to(root)
        if (relative.parts[0] in ("docs", "licenses")
                or relative.as_posix() in ("README.md", "THIRD_PARTY_NOTICES.md", "config.example.json", "LICENSE")):
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def collect_licenses(runtime_licenses):
    # Actual license texts from installed distributions, not hand-written summaries.
    for name in ("requests", "certifi", "charset-normalizer", "idna", "urllib3", "pyinstaller", "pycaw", "comtypes", "psutil", "pystray", "Pillow", "six"):
        dist = metadata.distribution(name)
        copied = 0
        for item in dist.files or []:
            if any(word in item.name.lower() for word in ("license", "copying", "copyright", "notice")) and item.suffix != ".py":
                source = Path(dist.locate_file(item))
                if source.is_file():
                    destination = runtime_licenses / name / str(item)
                    # Installed distribution paths must remain within this output tree.
                    if not destination.resolve().is_relative_to(runtime_licenses.resolve()):
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                    copied += 1
        if not copied:
            raise RuntimeError(f"Missing license text for {name}")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("Python runtime license not found")
    shutil.copy2(python_license, runtime_licenses / "Python-LICENSE.txt")
    tk_license = Path(sys.base_prefix) / "tcl" / "tk8.6" / "license.terms"
    if not tk_license.is_file():
        raise RuntimeError("Tk license not found")
    shutil.copy2(tk_license, runtime_licenses / "Tk-license.terms")


def build(output, custom_library=None):
    source_files()  # Validate before invoking the compiler.
    output = output.resolve()
    portable = output / NAME
    package = output / f"{NAME}-{VERSION}-windows-x64.zip"
    if portable.exists() or package.exists() or (output / "SHA256SUMS.txt").exists():
        raise RuntimeError("Output already exists; use a new --output-dir. Existing files were not changed.")
    scratch = (ROOT / "build").resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    # Fresh per-build staging prevents old configs/logs/credentials entering a zip.
    with tempfile.TemporaryDirectory(prefix="package-", dir=scratch) as temporary:
        stage = Path(temporary).resolve()
        if not stage.is_relative_to(scratch):
            raise RuntimeError("Build staging escaped workspace")
        staged_portable = stage / NAME
        staged_portable.mkdir()
        copy_public_files(staged_portable)
        runtime_licenses = staged_portable / "licenses/runtime"
        runtime_licenses.mkdir(parents=True)
        collect_licenses(runtime_licenses)
        source_archives(staged_portable / "source", custom_library)
        for executable, entry, mode in ((NAME, "entry.py", "--console"),
                                        (NAME + "-Desktop", "desktop_entry.py", "--windowed")):
            subprocess.run([
                sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", mode,
                "--name", executable, "--specpath", str(scratch),
                "--distpath", str(stage / "executables"),
                "--exclude-module", "setuptools", "--exclude-module", "pkg_resources",
                "--hidden-import", "pystray._win32",
                "--paths", str(ROOT / "src"),
                "--add-data", f"{staged_portable / 'licenses'}:licenses",
                "--add-data", f"{ROOT / 'LICENSE'}:.",
                "--add-data", f"{ROOT / 'THIRD_PARTY_NOTICES.md'}:.",
                str(ROOT / "scripts" / entry),
            ], cwd=ROOT, check=True)
            shutil.copy2(stage / "executables" / f"{executable}.exe", staged_portable / f"{executable}.exe")
        for name, command in (("login", "login"), ("run", "run"), ("probe", "probe"),
                              ("configure-app", "add-app"), ("upgrade-config", "enable-local-commands")):
            content = (f'@echo off\nchcp 65001 >nul\n"%~dp0{NAME}.exe" init\n'
                       f'if errorlevel 1 goto done\n"%~dp0{NAME}.exe" {command}\n:done\npause\n')
            (staged_portable / f"{name}.cmd").write_text(content, encoding="utf-8", newline="\r\n")
        shutil.make_archive(str(stage / "portable"), "zip", stage, NAME)
        output.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged_portable, portable)  # Never merge with user files.
        shutil.copy2(stage / "portable.zip", package)
        (output / "SHA256SUMS.txt").write_text(
            f"{hashlib.sha256(package.read_bytes()).hexdigest()}  {package.name}\n", encoding="utf-8")
    print(f"Portable build: {portable}")
    print("Local build only; nothing has been uploaded or published.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pystray-source", type=Path, help="matching modified pystray source zip, for rebuilding/relinking")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / VERSION,
                        help="unused output directory; existing packages are never overwritten")
    args = parser.parse_args()
    build(args.output_dir, args.pystray_source)


if __name__ == "__main__":
    main()
