"""Check the frozen app with Python paths removed; no login or desktop side effects."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-audio", action="store_true", help="read-only check on a machine with an audio output")
    args = parser.parse_args()
    executable = ROOT / "dist" / "TangerineXiaoAiAssistant" / "TangerineXiaoAiAssistant.exe"
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    with tempfile.TemporaryDirectory(prefix="xiaoai-exe-smoke-") as folder:
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
        assert not (Path(folder) / "xiaomi.dpapi").exists()
    print("Frozen smoke: PASS (all command dry-runs / app registration / upgrade / injection rejection / missing login; no Python on PATH)")
    if args.check_audio:
        print("Frozen Core Audio read-only check: PASS")


if __name__ == "__main__":
    main()
