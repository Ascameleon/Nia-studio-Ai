"""Extract a source ZIP without allowing traversal, special files, or ZIP bombs."""
from __future__ import annotations

import math
import stat
import sys
import unicodedata
from pathlib import Path, PurePosixPath, PureWindowsPath
from zipfile import ZipFile

MAX_ENTRIES = 10_000
MAX_MEMBER_SIZE = 128 * 1024 * 1024
MAX_TOTAL_SIZE = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


def _validate_portable_component(component: str, member_name: str) -> None:
    """Reject names that alias, target streams, or device files on Windows."""
    if component.endswith((" ", ".")):
        raise ValueError(f"Non-portable ZIP path component: {member_name!r}")
    if any(ord(char) < 32 or char in '<>:"|?*' for char in component):
        raise ValueError(f"Invalid Windows ZIP path component: {member_name!r}")
    device_stem = component.split(".", 1)[0].upper()
    if device_stem in {"CON", "PRN", "AUX", "NUL"} or device_stem in {
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
        "COM¹", "COM²", "COM³", "LPT¹", "LPT²", "LPT³",
    }:
        raise ValueError(f"Reserved Windows device name in ZIP path: {member_name!r}")


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
        or (isinstance(max_compression_ratio, float) and not math.isfinite(max_compression_ratio))
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
        regular_files: set[str] = set()
        portable_paths: dict[str, str] = {}
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

            raw_parts = name.split("/")
            if member.is_dir():
                raw_parts = raw_parts[:-1]
            if not raw_parts or any(part in {"", ".", ".."} for part in raw_parts):
                raise ValueError(f"Non-canonical ZIP member path: {name!r}")
            for component in raw_parts:
                _validate_portable_component(component, name)

            # Windows filesystems are case-insensitive and normalize some names.
            # Reject aliases before extraction so archive order cannot overwrite a
            # different source file or merge differently-cased parent directories.
            original_prefix: list[str] = []
            for component in raw_parts:
                original_prefix.append(component)
                spelling = "/".join(original_prefix)
                # NFC collapses canonically equivalent Unicode spellings (for example,
                # precomposed and combining-accent forms) before case folding. This
                # prevents one archive from creating aliases on normalization-insensitive
                # filesystems such as common macOS volumes.
                key = unicodedata.normalize("NFC", spelling.casefold())
                previous = portable_paths.get(key)
                if previous is not None and previous != spelling:
                    raise ValueError(
                        f"Case-insensitive ZIP path collision after Unicode NFC normalization: {previous!r} and {spelling!r}"
                    )
                portable_paths[key] = spelling

            normalized = posix.as_posix().rstrip("/")
            if normalized in seen:
                raise ValueError(f"Duplicate ZIP member path: {name!r}")
            seen.add(normalized)

            file_type = stat.S_IFMT(member.external_attr >> 16)
            if file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError(f"Unsupported ZIP member type: {name!r}")

            if file_type == stat.S_IFDIR and not member.is_dir():
                raise ValueError(f"Directory ZIP member must end with '/': {name!r}")
            if member.is_dir() and file_type == stat.S_IFREG:
                raise ValueError(f"Directory ZIP member has regular-file metadata: {name!r}")
            if not member.is_dir():
                regular_files.add(normalized)

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

        # A ZIP may be traversal-safe yet structurally impossible: a regular file
        # cannot also be the parent directory of another member. Detect every
        # such conflict before extractall so a malformed archive cannot leave a
        # partially extracted tree.
        for name in seen:
            for parent in PurePosixPath(name).parents:
                parent_name = parent.as_posix()
                if parent_name != "." and parent_name in regular_files:
                    raise ValueError(
                        f"ZIP member path conflicts with regular file: "
                        f"{parent_name!r} is a parent of {name!r}"
                    )

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
