#!/usr/bin/env python3
"""Apply the audited runtime dependency repair to one extracted NIA 0.6.4 snapshot."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

REQUIRED = "itsdangerous>=2.2,<3.0"
CANDIDATES = (Path("restored/nia-studio-ai"), Path("nia-studio-ai"))


def locate_project_root(base_dir: Path) -> Path:
    """Find exactly one safe extracted project tree below the repository root."""
    base = base_dir.resolve()
    matches: list[Path] = []

    for relative in CANDIDATES:
        candidate = base / relative
        if candidate.is_symlink():
            raise ValueError(f"refusing symlink project root: {relative}")
        requirements = candidate / "requirements.txt"
        if requirements.is_symlink():
            raise ValueError(f"refusing symlink requirements file: {relative / 'requirements.txt'}")
        if requirements.is_file():
            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(base):
                raise ValueError(f"project root escapes repository directory: {relative}")
            resolved_requirements = requirements.resolve(strict=True)
            if resolved_requirements.parent != resolved:
                raise ValueError(f"requirements file escapes project root: {relative}")
            matches.append(resolved)

    if not matches:
        expected = " or ".join(str(path / "requirements.txt") for path in CANDIDATES)
        raise ValueError(f"could not find an extracted project requirements file ({expected})")
    if len(matches) != 1:
        raise ValueError(
            "ambiguous extracted project roots; keep exactly one of "
            + ", ".join(str(path.relative_to(base)) for path in matches)
        )
    return matches[0]


def _replace_text_atomically(path: Path, content: str) -> None:
    """Write a sibling temporary file safely, then atomically replace the target."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def repair_dependencies(base_dir: Path) -> Path:
    """Repair the one unambiguous extracted snapshot and return its resolved root."""
    root = locate_project_root(base_dir)
    requirements = root / "requirements.txt"
    lines = requirements.read_text(encoding="utf-8").splitlines()
    matches = [line.strip() for line in lines if line.strip().lower().startswith("itsdangerous")]

    if not matches:
        lines.extend(["", "# Required by Starlette SessionMiddleware (runtime dependency).", REQUIRED])
        _replace_text_atomically(requirements, "\n".join(lines).rstrip() + "\n")
    elif matches != [REQUIRED]:
        raise ValueError(f"unexpected itsdangerous constraint(s): {matches!r}")

    final_lines = requirements.read_text(encoding="utf-8").splitlines()
    if sum(line.strip() == REQUIRED for line in final_lines) != 1:
        raise ValueError("runtime dependency repair was not applied exactly once")
    return root


def main() -> int:
    try:
        root = repair_dependencies(Path.cwd())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Dependency repair refused: {exc}") from None
    print(f"Verified {root}: {REQUIRED}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
