#!/usr/bin/env python3
"""Apply the audited runtime dependency repair to the extracted NIA 0.6.4 snapshot."""
from __future__ import annotations

from pathlib import Path

REQUIRED = "itsdangerous>=2.2,<3.0"
CANDIDATES = (Path("restored/nia-studio-ai"), Path("nia-studio-ai"))


def main() -> int:
    root = next((candidate for candidate in CANDIDATES if (candidate / "requirements.txt").is_file()), None)
    if root is None:
        raise SystemExit("could not find restored/nia-studio-ai or nia-studio-ai/requirements.txt")
    requirements = root / "requirements.txt"
    lines = requirements.read_text(encoding="utf-8").splitlines()
    matches = [line.strip() for line in lines if line.strip().lower().startswith("itsdangerous")]
    if not matches:
        lines.extend(["", "# Required by Starlette SessionMiddleware (runtime dependency).", REQUIRED])
        requirements.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    elif matches != [REQUIRED]:
        raise SystemExit(f"unexpected itsdangerous constraint(s): {matches!r}")
    final_lines = requirements.read_text(encoding="utf-8").splitlines()
    if sum(line.strip() == REQUIRED for line in final_lines) != 1:
        raise SystemExit("runtime dependency repair was not applied exactly once")
    print(f"Verified {root}: {REQUIRED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
