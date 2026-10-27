"""Fail when tracked BhashaFlow files contain secrets.

Downloads pinned gitleaks, checks that Muse key assignments are detected, then
scans this branch's git history, changes to tracked files, and untracked files
that are not gitignored. A gitignored ``.env`` is not part of the scan.
"""

from __future__ import annotations

import hashlib
import json
import platform
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "8.30.1"
ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".gitleaks.toml"
CACHE = ROOT / ".cache" / "gitleaks" / VERSION

# sha256 of the official v8.30.1 release archives.
ARCHIVES = {
    ("darwin", "arm64"): (
        "gitleaks_8.30.1_darwin_arm64.tar.gz",
        "b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5",
    ),
    ("darwin", "x64"): (
        "gitleaks_8.30.1_darwin_x64.tar.gz",
        "dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709",
    ),
    ("linux", "arm64"): (
        "gitleaks_8.30.1_linux_arm64.tar.gz",
        "e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080",
    ),
    ("linux", "x64"): (
        "gitleaks_8.30.1_linux_x64.tar.gz",
        "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
    ),
    ("windows", "arm64"): (
        "gitleaks_8.30.1_windows_arm64.zip",
        "b95f5e4f5c425cedca7ee203d9afd29597e692c4924a12ed42f970537c72cc0f",
    ),
    ("windows", "x64"): (
        "gitleaks_8.30.1_windows_x64.zip",
        "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e",
    ),
}


def main() -> int:
    binary = ensure_binary()
    self_test(binary)
    say(f"gitleaks {VERSION}: canary matched sk- assignments and ignored placeholders")
    scans = (
        ("git history", ["--log-opts=--all -m"]),
        ("uncommitted tracked changes", ["--pre-commit"]),
        ("staged tracked changes", ["--pre-commit", "--staged"]),
    )
    for label, extra in scans:
        say(f"gitleaks: scanning {label}")
        code = scan_repo(binary, extra)
        if code != 0:
            print(f"secret scan failed while scanning {label}", file=sys.stderr, flush=True)
            return code
    code = scan_untracked(binary)
    if code != 0:
        return code
    say("no secrets found in git history or uncommitted files")
    return 0


def say(message: str) -> None:
    print(message, flush=True)


def ensure_binary() -> Path:
    system, arch = platform_key()
    filename, digest = ARCHIVES[(system, arch)]
    binary_name = "gitleaks.exe" if system == "windows" else "gitleaks"
    binary = CACHE / binary_name
    if binary.is_file() and version_of(binary) == VERSION:
        return binary
    CACHE.mkdir(parents=True, exist_ok=True)
    archive = CACHE / filename
    url = f"https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/{filename}"
    download(url, archive)
    actual = sha256(archive)
    if actual != digest:
        archive.unlink(missing_ok=True)
        raise SystemExit(f"gitleaks checksum mismatch for {filename}")
    extracted = extract_binary(archive, binary_name)
    archive.unlink(missing_ok=True)
    found = version_of(extracted)
    if found != VERSION:
        raise SystemExit(f"expected gitleaks {VERSION}, found {found!r}")
    return extracted


def platform_key() -> tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = {
        "x86_64": "x64",
        "amd64": "x64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(machine)
    if (system, arch) not in ARCHIVES:
        supported = ", ".join(f"{name}-{cpu}" for name, cpu in sorted(ARCHIVES))
        raise SystemExit(f"unsupported platform {system} {machine}; supported: {supported}")
    return system, arch


def download(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "bhashaflow-scan-secrets"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            dest.write_bytes(response.read())
    except OSError as exc:
        raise SystemExit(f"failed to download gitleaks from {url}: {exc}") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_binary(archive: Path, binary_name: str) -> Path:
    if binary_name != "gitleaks" and binary_name != "gitleaks.exe":
        raise SystemExit(f"refusing to extract {binary_name}")
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            info = bundle.getinfo(binary_name)
            if info.filename != binary_name:
                raise SystemExit(f"unexpected archive member {info.filename}")
            bundle.extract(info, CACHE)
    else:
        with tarfile.open(archive, "r:gz") as bundle:
            member = bundle.getmember(binary_name)
            if member.name != binary_name or not member.isfile():
                raise SystemExit(f"unexpected archive member {member.name}")
            bundle.extract(member, CACHE, filter="data")
    binary = CACHE / binary_name
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    return binary


def version_of(binary: Path) -> str:
    completed = subprocess.run(
        [str(binary), "version"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or "gitleaks version failed")
    return completed.stdout.strip()


def self_test(binary: Path) -> None:
    sk = "sk-" + "7f3a91c0" + "d4e27b6a15c9ff01aa"
    opaque = "a8F3kQ91" + "mZ0pL2xN7vR4w"
    leaks = (
        f"MODEL_API_KEY={sk}\n",
        f'BHASHAFLOW_STT_API_KEY="{sk}"\n',
        f'monkeypatch.setenv("MODEL_API_KEY", "{sk}")\n',
        f'{{"BHASHAFLOW_MUSE_API_KEY": "{sk}"}}\n',
        f"export BHASHAFLOW_TTS_API_KEY={sk}\n",
        f"MODEL_API_KEY={opaque}\n",
        "MODEL_API_KEY=sk-" + "12345678\n",
    )
    clean = (
        "MODEL_API_KEY=\nBHASHAFLOW_MUSE_API_KEY=\nBHASHAFLOW_STT_API_KEY=\n"
        "BHASHAFLOW_TTS_API_KEY=\n",
        'monkeypatch.setenv("MODEL_API_KEY", "already-exported-secret")\n',
        '_KEY_ENVS = ("MODEL_API_KEY", "BHASHAFLOW_MUSE_API_KEY", "BHASHAFLOW_STT_API_KEY")\n',
        "MODEL_API_KEY=other-secret\n",
        "MODEL_API_KEY=your-api-key-here\n",
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for index, text in enumerate(leaks):
            path = root / f"leak{index}.txt"
            path.write_text(text, encoding="utf-8")
            found = scan_file(binary, path, root / f"leak{index}.json")
            rule_ids = {item.get("RuleID", "") for item in found}
            if not any(str(rule_id).startswith("bhashaflow-") for rule_id in rule_ids):
                raise SystemExit(
                    "secret rule did not fire for a Muse key assignment "
                    f"(rules={sorted(str(rule_id) for rule_id in rule_ids) or 'none'})"
                )
        for index, text in enumerate(clean):
            path = root / f"clean{index}.txt"
            path.write_text(text, encoding="utf-8")
            found = scan_file(binary, path, root / f"clean{index}.json")
            if found:
                raise SystemExit("secret rule flagged a placeholder or variable name")
        example = scan_file(binary, ROOT / ".env.example", root / "example.json")
    if example:
        raise SystemExit(".env.example was flagged; key fields must stay empty")


def scan_file(binary: Path, path: Path, report: Path) -> list[dict[str, object]]:
    completed = subprocess.run(
        [
            str(binary),
            "dir",
            str(path),
            "--config",
            str(CONFIG),
            "--redact",
            "--no-banner",
            "--no-color",
            "--log-level",
            "error",
            "--report-format",
            "json",
            "--report-path",
            str(report),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode not in (0, 1) or not report.is_file():
        detail = (completed.stderr or completed.stdout).strip()
        raise SystemExit(detail or f"gitleaks failed while scanning {path.name}")
    data = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("gitleaks report was not a list")
    return data


def scan_untracked(binary: Path) -> int:
    """Scan files git would add. Gitignored paths, including a local .env, stay out."""
    completed = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode().strip()
        raise SystemExit(detail or "git ls-files failed")
    paths = [ROOT / name for name in completed.stdout.decode().split("\0") if name]
    say(f"gitleaks: scanning {len(paths)} untracked files")
    failed = False
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for index, path in enumerate(paths):
            if scan_file(binary, path, root / f"untracked{index}.json"):
                failed = True
                print(
                    f"secret scan failed in untracked file {path.relative_to(ROOT)}",
                    file=sys.stderr,
                    flush=True,
                )
                subprocess.run(
                    [
                        str(binary),
                        "dir",
                        str(path),
                        "--config",
                        str(CONFIG),
                        "--redact",
                        "--no-banner",
                        "--no-color",
                        "--verbose",
                    ],
                    cwd=ROOT,
                    check=False,
                )
    return 1 if failed else 0


def scan_repo(binary: Path, extra: list[str]) -> int:
    command = [
        str(binary),
        "git",
        *extra,
        "--config",
        str(CONFIG),
        "--redact",
        "--no-banner",
        "--no-color",
        "--verbose",
        str(ROOT),
    ]
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
