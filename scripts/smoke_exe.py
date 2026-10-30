"""Check the frozen app with Python paths removed; no login or desktop side effects."""
from pathlib import Path
import json
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
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
        run("test-command", "让电脑打开B站 & calc", expected=2)
        run("run", expected=2)
        assert not (Path(folder) / "xiaomi.dpapi").exists()
    print("Frozen smoke: PASS (init / dry-run / injection rejection / missing login; no Python on PATH)")


if __name__ == "__main__":
    main()
