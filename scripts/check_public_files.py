"""Check public files for machine paths, runtime data and common credential forms.

Uses only the standard library. Findings never include the matched secret text.
This is a guardrail, not a guarantee that arbitrary text or images contain no PII.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DRIVE_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
HOME_PATH = re.compile(r"(?i)(?:[A-Za-z]:[\\/]+Users[\\/]+|/(?:home|Users)/[^/\s]+/)")
SECRETS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16})"),
    re.compile(r'''(?i)(?:password|passToken|serviceToken|client_secret|api_key)["']?\s*[=:]\s*["'][A-Za-z0-9_+/=-]{24,}["']'''),
)


def inspect_file(name, content):
    """Return categories only; test fixtures may contain synthetic drive paths."""
    path = PurePosixPath(name)
    lower = path.name.lower()
    findings = []
    if (lower == 'config.json' or lower.startswith('config.') and lower.endswith('.json') and lower != 'config.example.json'
            or lower.startswith('.env') or lower == 'login-qr.png'
            or lower.endswith(('.dpapi', '.bak', '.tmp', '.lnk'))
            or '.log' in path.suffixes
            or any(part in ('data', '.venv', 'dist', 'build', '__pycache__', '.idea', '.vscode') for part in path.parts)):
        findings.append('private/runtime file')
    if b'\x00' in content:
        return findings  # Binary images require separate visual/metadata review.
    text = content.decode('utf-8', errors='replace')
    if lower == 'config.example.json':
        try:
            example = json.loads(text)
            if example.get('xiaomi', {}).get('device_id') or any(c.get('path') for c in example.get('commands', [])):
                findings.append('example contains device ID or installed application path')
        except (ValueError, AttributeError, TypeError):
            findings.append('invalid example configuration')
    if HOME_PATH.search(text):
        findings.append('user home path')
    if not name.startswith('tests/') and DRIVE_PATH.search(text):
        findings.append('absolute machine path (use a placeholder or environment variable)')
    if any(pattern.search(text) for pattern in SECRETS):
        findings.append('possible credential')
    return findings


def check_paths(root, paths):
    failures = []
    for path in paths:
        name = path.relative_to(root).as_posix()
        failures.extend(f'{name}: {reason}' for reason in inspect_file(name, path.read_bytes()))
    if failures:
        raise ValueError('Public-file privacy check failed:\n' + '\n'.join(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', action='store_true', help='check staged Git contents, not working-tree versions')
    args = parser.parse_args()
    command = (['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z'] if args.staged else
               ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'])
    names = sorted(set(subprocess.check_output(command, cwd=ROOT).decode('utf-8').split('\0')) - {''})
    failures = []
    checked = 0
    for name in names:
        if args.staged:
            content = subprocess.check_output(['git', 'show', ':' + name], cwd=ROOT)
        elif (ROOT / name).is_file():
            content = (ROOT / name).read_bytes()
        else:
            continue
        checked += 1
        failures.extend(f'{name}: {reason}' for reason in inspect_file(name, content))
    if failures:
        print('\n'.join(failures))
        return 1
    print(f'Public-file privacy check: PASS ({checked} files; review screenshots and free text separately)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
