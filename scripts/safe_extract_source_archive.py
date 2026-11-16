"""Extract a source ZIP without allowing path traversal or special files."""
from __future__ import annotations

import stat
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from zipfile import ZipFile


def safe_extract(archive_path: str | Path, destination: str | Path) -> int:
    """Validate every member before extracting any archive content."""
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()

    with ZipFile(archive_path) as archive:
        members = archive.infolist()
        seen: set[str] = set()
        for member in members:
            name = member.filename
            posix = PurePosixPath(name)
            windows = PureWindowsPath(name)
            if (
                not name
                or "\\" in name
                or posix.is_absolute()
                or windows.is_absolute()
                or bool(windows.drive)
                or ".." in posix.parts
                or name in {".", "./"}
            ):
                raise ValueError(f"Unsafe ZIP member path: {name!r}")

            normalized = posix.as_posix().rstrip("/")
            if normalized in seen:
                raise ValueError(f"Duplicate ZIP member path: {name!r}")
            seen.add(normalized)

            file_type = stat.S_IFMT(member.external_attr >> 16)
            if file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError(f"Unsupported ZIP member type: {name!r}")

            target = (root / Path(*posix.parts)).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"ZIP member escapes extraction directory: {name!r}")

        archive.extractall(root)
        return len(members)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: safe_extract_source_archive.py ARCHIVE.zip DESTINATION", file=sys.stderr)
        return 2
    try:
        count = safe_extract(sys.argv[1], sys.argv[2])
    except (OSError, ValueError, Exception) as exc:
        print(f"Safe ZIP extraction failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"Safely extracted {count} ZIP entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
