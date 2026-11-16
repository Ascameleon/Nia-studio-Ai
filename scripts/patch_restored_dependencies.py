#!/usr/bin/env python3
"""Apply the audited runtime dependency repair to the extracted NIA 0.6.4 snapshot."""
from __future__ import annotations

from pathlib import Path

ROOT = Path("restored/nia-studio-ai")
REQUIREMENTS = ROOT / "requirements.txt"
REQUIRED = "itsdangerous>=2.2,<3.0"


def main() -> int:
    if not REQUIREMENTS.is_file():
        raise SystemExit(f"missing recovered runtime requirements: {REQUIREMENTS}")
    lines = REQUIREMENTS.read_text(encoding="utf-8").splitlines()
    matches = [line.strip() for line in lines if line.strip().lower().startswith("itsdangerous")]
    if not matches:
        lines.extend(["", "# Required by Starlette SessionMiddleware (runtime dependency).", REQUIRED])
        REQUIREMENTS.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    elif matches != [REQUIRED]:
        raise SystemExit(f"unexpected itsdangerous constraint(s): {matches!r}")
    final_lines = REQUIREMENTS.read_text(encoding="utf-8").splitlines()
    if sum(line.strip() == REQUIRED for line in final_lines) != 1:
        raise SystemExit("runtime dependency repair was not applied exactly once")
    print(f"Verified runtime dependency: {REQUIRED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
