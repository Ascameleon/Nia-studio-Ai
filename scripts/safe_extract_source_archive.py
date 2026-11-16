"""Extract a source ZIP without allowing traversal, special files, or ZIP bombs."""
from __future__ import annotations

import stat
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from zipfile import ZipFile

MAX_ENTRIES = 10_000
MAX_MEMBER_SIZE = 128 * 1024 * 1024
MAX_TOTAL_SIZE = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


def safe_extract(
    archive_path: str | Path,
    destination: str | Path,
    *,
    max_entries: int = MAX_ENTRIES,
    max_member_size: int = MAX_MEMBER_SIZE,
    max_total_size: int = MAX_TOTAL_SIZE,
    max_compression_ratio: float = MAX_COMPRESSION_RATIO,
) -> int:
    """Validate every ZIP member and resource bound before extracting anything."""
    limits = (max_entries, max_member_size, max_total_size)
    if any(type(limit) is not int or limit <= 0 for limit in limits):
        raise ValueError("ZIP extraction limits must be positive integers")
    if (
        isinstance(max_compression_ratio, bool)
        or not isinstance(max_compression_ratio, (int, float))
        or max_compression_ratio <= 0
    ):
        raise ValueError("ZIP compression ratio limit must be positive")

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()

    with ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) > max_entries:
            raise ValueError(
                f"ZIP entry count {len(members)} exceeds maximum {max_entries}"
            )

        seen: set[str] = set()
        total_size = 0
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

            if member.file_size < 0 or member.compress_size < 0:
                raise ValueError(f"Invalid ZIP member size: {name!r}")
            if member.file_size > max_member_size:
                raise ValueError(
                    f"ZIP member {name!r} exceeds maximum size {max_member_size}"
                )
            total_size += member.file_size
            if total_size > max_total_size:
                raise ValueError(
                    f"ZIP expanded size exceeds maximum {max_total_size}"
                )
            if member.file_size:
                if member.compress_size == 0:
                    raise ValueError(f"Invalid compressed size for ZIP member: {name!r}")
                ratio = member.file_size / member.compress_size
                if ratio > max_compression_ratio:
                    raise ValueError(
                        f"ZIP member {name!r} compression ratio {ratio:.1f} "
                        f"exceeds maximum {max_compression_ratio}"
                    )

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
    except Exception as exc:
        print(f"Safe ZIP extraction failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"Safely extracted {count} ZIP entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
