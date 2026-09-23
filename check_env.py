"""
check_env.py — verify requirements.txt matches the actual venv.

Reports:
    - Packages in requirements.txt that are NOT installed
    - Packages installed that are NOT in requirements.txt (extras)

The first category breaks fresh installs. The second is noise.
"""

import re
import subprocess
import sys
from pathlib import Path

REQS = Path(__file__).parent / "requirements.txt"


def normalize(spec: str) -> str:
    """Strip version specifiers and extras from a package name."""
    name = re.split(r"[=<>!~\[\s]", spec.strip(), maxsplit=1)[0]
    return name.lower().replace("_", "-")


def main() -> int:
    if not REQS.exists():
        print("ERROR: requirements.txt not found")
        return 1

    # Names listed in requirements.txt
    required = set()
    for line in REQS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = normalize(line)
        if name:
            required.add(name)

    # Names actually installed in the current venv
    frozen = subprocess.check_output(
        [sys.executable, "-m", "pip", "freeze"],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    installed = set()
    for line in frozen.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name = normalize(line)
        if name:
            installed.add(name)

    missing = required - installed
    extras = installed - required

    print("=" * 64)
    print(f"  requirements.txt: {len(required)} packages")
    print(f"  venv installed:   {len(installed)} packages")
    print("=" * 64)

    if missing:
        print()
        print(f"  MISSING from venv ({len(missing)}):")
        print("  These are in requirements.txt but not installed.")
        print("  Abu Bakr's fresh install WILL fail on these.")
        for name in sorted(missing):
            print(f"    - {name}")

    print()
    print(f"  EXTRAS installed ({len(extras)}):")
    print("  Installed but not in requirements.txt.")
    print("  Harmless, but if Abu Bakr needs them, add them.")
    for name in sorted(extras)[:40]:
        print(f"    + {name}")
    if len(extras) > 40:
        print(f"    ... and {len(extras) - 40} more")

    print()
    print("=" * 64)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())