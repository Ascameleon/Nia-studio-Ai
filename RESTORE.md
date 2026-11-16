# Restoring the NIA Studio AI 0.6.4 source snapshot

The source archive is stored at the repository root as `NIA-Studio-AI-0.6.4-restored.zip`.

1. Verify the archive checksum:
   `sha256sum NIA-Studio-AI-0.6.4-restored.zip`
2. Extract it:
   `unzip -q NIA-Studio-AI-0.6.4-restored.zip`
3. Enter `nia-studio-ai/`, create a Python 3.11+ virtual environment, and install `requirements-dev.txt`.
4. Run `python -m pytest -q`, `python scripts/assemble_upstreams.py --dry-run`, and `python -m compileall -q app nia_core nia-autonomous-engine tests scripts`.

The archive checksum is `c5eb80304ac201b7d27c3e1030c81300db8da4119d7781d6308f17e3bd98f9ae`. The root GitHub Actions workflow performs these checks on every relevant push or pull request and uploads an extracted source snapshot for 14 days.

The application source is MIT-licensed. Optional upstream projects are not vendored or installed by the dry-run. The manifest records their candidate licenses; inspect the exact upstream revision and notices before incorporating any of them. Model weights are not included and must be licensed separately.

**Runtime boundary:** no model weights, no real image/video inference, and no target-device performance test are included in this recovery.

## Verification evidence

The recovered snapshot was checked locally on Python 3.13.5: 36 tests passed, `scripts/assemble_upstreams.py --dry-run` passed, and `compileall` completed. The checksum and Python 3.11 CI workflow are the authoritative checks for this committed archive; a local test pass does not establish image/video inference or model availability.
