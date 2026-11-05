"""Per-user layout and fail-closed migration. Call prepare_default under both locks."""
from contextlib import ExitStack, contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat

from .identity import IDENTITY

FILES = {
    "config.json": "Config/config.json",
    "config.json.bak": "Backups/config.json.bak",
    "xiaomi.dpapi": "Storage/xiaomi.dpapi",
    "assistant.log": "Logs/assistant.log",
    "assistant.log.1": "Logs/assistant.log.1",
    "assistant.log.2": "Logs/assistant.log.2",
    "login-qr.png": "Temp/login-qr.png",
    "assistant.lock": "Runtime/assistant.lock",
    "lifecycle.lock": "Runtime/lifecycle.lock",
}
LOCKS = {"assistant.lock", "lifecycle.lock"}
JOURNAL = "tangerine-migration.json"
ORIGINALS = "tangerine-originals"
BLOCKER = b'{"moved_to_tangerine": "Use version 0.4.2 or newer. See docs/STORAGE.md."}\n'


def local_root():
    value = os.environ.get("LOCALAPPDATA")
    if not value:
        raise RuntimeError("需要 Windows LOCALAPPDATA 目录。")
    return Path(value).absolute()


def default_directory():
    return local_root() / "Tangerine" / "Data" / IDENTITY["data_folder"]


def legacy_directory():
    return local_root() / IDENTITY["data_folder"]


def managed(directory):
    return Path(directory).resolve() == default_directory().resolve()


def data_file(directory, name):
    return directory / (FILES.get(name, "Runtime/" + name) if managed(directory) else name)


def safe_path(path):
    # Do not resolve links first: that would hide a redirected owned directory.
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise RuntimeError("数据目录包含链接或重解析路径，已停止；请保留现场检查。")


def safe_tree(path):
    safe_path(path)
    if path.is_dir():
        for child in path.iterdir():
            safe_tree(child)


def _exclusive_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fail():
    raise RuntimeError("发现数据冲突或未完成的目录迁移，未继续运行。请保留新旧目录，按 docs/STORAGE.md 恢复；不要删除迁移记录或启动旧版。")


def prepare_default():
    """Never decrypt secrets; preserve originals and stop old versions via invalid config.

    Journal is deliberately not auto-resumed after interruption. Original files are
    either in the old root or its originals folder, and never overwritten/deleted.
    """
    from . import config
    old, new = legacy_directory(), default_directory()
    safe_tree(old)
    safe_tree(new)
    marker = new / "Runtime/layout.json"
    journal = old / JOURNAL
    expected = {"layout": 1, "identity": IDENTITY["app_id"]}
    if journal.exists():
        try:
            record = json.loads(journal.read_bytes())
            if record["identity"] != expected["identity"] or record["layout"] != 1:
                _fail()
            if json.loads(marker.read_bytes()) != expected:
                _fail()
            if (old / "config.json").read_bytes() != BLOCKER:
                _fail()
            if set(p.name for p in old.iterdir()) - (LOCKS | {JOURNAL, ORIGINALS, "config.json"}):
                _fail()
            hashes = record["originals"]
            if set(p.name for p in (old / ORIGINALS).iterdir()) != set(hashes):
                _fail()
            for name, checksum in hashes.items():
                if name not in FILES or name in LOCKS or digest(old / ORIGINALS / name) != checksum:
                    _fail()
            if (new / "Runtime/config-initialized").exists() or "config.json" in hashes:
                config.load(data_file(new, "config.json"))
        except (OSError, ValueError, KeyError, TypeError):
            _fail()
        return
    old_names = {p.name for p in old.iterdir()}
    if old_names - set(FILES) or any(not p.is_file() for p in old.iterdir()):
        _fail()
    # Only the lock files created by this invocation / installer may preexist.
    if any(p.relative_to(new).as_posix() not in {"Runtime", "Runtime/assistant.lock", "Runtime/lifecycle.lock"}
           for p in new.rglob("*")):
        _fail()
    payload = old_names - LOCKS
    if payload and "config.json" not in payload:
        _fail()
    for name in ("config.json", "config.json.bak"):
        if name in payload:
            config.load(old / name)
    hashes = {name: digest(old / name) for name in sorted(payload)}
    record = dict(expected, originals=hashes)
    # Journal precedes every data write. Any failure after this point fails closed.
    _exclusive_write(journal, json.dumps(record, sort_keys=True).encode("utf-8"))
    originals = old / ORIGINALS
    originals.mkdir()
    for name in sorted(payload):
        source = old / name
        destination = data_file(new, name)
        _exclusive_write(destination, source.read_bytes())
        if digest(destination) != hashes[name] or digest(source) != hashes[name]:
            _fail()
    # Never leave config.json absent: old desktop versions would generate a new
    # default configuration in that gap after a crash. Retain its exact bytes,
    # then atomically replace it with a blocker before retiring other files.
    if "config.json" in payload:
        _exclusive_write(originals / "config.json", (old / "config.json").read_bytes())
        config._atomic_write(old / "config.json", BLOCKER)
    else:
        _exclusive_write(old / "config.json", BLOCKER)
    for name in sorted(payload - {"config.json"}):
        (old / name).rename(originals / name)
    _exclusive_write(marker, json.dumps(expected, sort_keys=True).encode("utf-8"))


@contextmanager
def session(directory, *, frozen=False):
    from .lifecycle import lifecycle_guard
    from .runtime import single_instance
    safe_path(directory)
    use_default = managed(directory)
    with ExitStack() as stack:
        if use_default or frozen:
            old = legacy_directory()
            safe_path(old)
            for name in LOCKS:
                safe_path(old / name)
            # Same byte locks as all old versions and old installers.
            stack.enter_context(lifecycle_guard(old))
            if use_default:
                stack.enter_context(single_instance(old))
            guard = default_directory() / "Runtime"
            safe_path(guard)
            safe_path(guard / "lifecycle.lock")
            stack.enter_context(lifecycle_guard(guard))
        safe_tree(directory)
        if not use_default:
            if (directory / JOURNAL).exists():
                _fail()
            if not frozen:
                stack.enter_context(lifecycle_guard(directory))
        stack.enter_context(single_instance(directory))
        if use_default:
            try:
                prepare_default()
            except OSError:
                _fail()
        yield
        if use_default and data_file(directory, "config.json").is_file():
            initialized = directory / "Runtime/config-initialized"
            if not initialized.exists():
                _exclusive_write(initialized, b"1\n")
