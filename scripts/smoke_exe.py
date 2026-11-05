"""Check the frozen app with Python paths removed; no login or desktop side effects."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-window", action="store_true", help="skip GUI when host window access is excluded")
    parser.add_argument("--legacy-cli", type=Path, help="optional historical EXE, init only with isolated synthetic data")
    parser.add_argument("--check-audio", action="store_true", help="read-only check on a machine with an audio output")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["version"]
    parser.add_argument("--package-dir", type=Path, default=ROOT / "dist" / version / "TangerineXiaoAiAssistant")
    args = parser.parse_args()
    executable = (args.package_dir / "TangerineXiaoAiAssistant.exe").resolve()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    with tempfile.TemporaryDirectory(prefix="xiaoai-exe-smoke-") as folder:
        env["LOCALAPPDATA"] = str(Path(folder) / "local-data")
        command = [str(executable), "--data-dir", folder]
        def run(*args, expected=0):
            result = subprocess.run(command + list(args), env=env, cwd=folder,
                                    capture_output=True, encoding="utf-8", timeout=30)
            if result.returncode != expected:
                raise RuntimeError(f"Frozen command {args[0]} failed (exit {result.returncode})")
            return result
        run("init")
        result = run("test-command", "小爱同学，让电脑打开 B 站")
        assert json.loads(result.stdout)["code"] == "dry_run"
        for text in ("让电脑把音量调到百分之三十", "让电脑锁屏"):
            assert json.loads(run("test-command", text).stdout)["code"] == "dry_run"
        run("test-command", "让电脑把音量调到101", expected=2)
        fixture = Path(folder) / "Fixture.exe"
        fixture.write_bytes(b"not executable; registration must not launch it")
        run("add-app", "测试应用", str(fixture))
        assert json.loads(run("test-command", "让电脑打开测试应用").stdout)["code"] == "dry_run"
        cfg_path = Path(folder) / "config.json"
        cfg = json.loads(cfg_path.read_text("utf-8"))
        cfg["commands"] = [c for c in cfg["commands"] if c["action"] not in ("set_volume", "lock")]
        cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
        run("enable-local-commands")
        assert len(json.loads(cfg_path.read_text("utf-8"))["commands"]) == 4
        if args.check_audio:
            audio = json.loads(run("volume-status").stdout)
            assert 0 <= audio["volume_percent"] <= 100 and isinstance(audio["muted"], bool)
        run("test-command", "让电脑打开B站 & calc", expected=2)
        run("run", expected=2)
        if not args.no_window:
            desktop = executable.with_name("TangerineXiaoAiAssistant-Desktop.exe")
            desktop_result = subprocess.run([str(desktop), "--data-dir", folder, "desktop", "--smoke-test"],
                                            env=env, cwd=folder, timeout=45)
            if desktop_result.returncode != 0:
                raise RuntimeError("Frozen desktop / Tk / tray smoke failed")
        # The desktop must have released its lock before another process starts.
        run("init")
        assert not (Path(folder) / "xiaomi.dpapi").exists()
        # Formal identity defaults use a synthetic LOCALAPPDATA, never the host profile.
        legacy = Path(env["LOCALAPPDATA"]) / "TangerineXiaoAiAssistant"
        legacy.mkdir(parents=True, exist_ok=True)
        original = cfg_path.read_bytes()
        encrypted_fixture = b"opaque synthetic DPAPI bytes; migration must never decrypt"
        (legacy / "config.json").write_bytes(original)
        (legacy / "xiaomi.dpapi").write_bytes(encrypted_fixture)
        command = [str(executable)]
        run("init")
        current = Path(env["LOCALAPPDATA"]) / "Tangerine/Data/TangerineXiaoAiAssistant"
        assert (current / "Config/config.json").read_bytes() == original
        assert (current / "Storage/xiaomi.dpapi").read_bytes() == encrypted_fixture
        assert (legacy / "tangerine-originals/xiaomi.dpapi").read_bytes() == encrypted_fixture
        run("test-command", "让电脑打开B站")
        run("init")
        if args.legacy_cli:
            previous = subprocess.run([str(args.legacy_cli.resolve()), "init"], env=env, cwd=folder,
                                      capture_output=True, timeout=30)
            assert previous.returncode == 2, "Old default entry must refuse retired data"
            assert (current / "Storage/xiaomi.dpapi").read_bytes() == encrypted_fixture
        print("Frozen default storage: PASS (migration / exact encrypted bytes / reopen / isolated profile)")

    print("Frozen smoke: PASS (all command dry-runs / app registration / upgrade / injection rejection / missing login; no Python on PATH)")
    if args.check_audio:
        print("Frozen Core Audio read-only check: PASS")
    print("Frozen desktop smoke: SKIPPED (host window constraint)" if args.no_window else
          "Frozen desktop smoke: PASS (Tk widgets / real tray / clean exit / released lock)")


if __name__ == "__main__":
    main()
