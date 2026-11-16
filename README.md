# NIA Studio AI

## Recovered source snapshot — 0.6.4

This repository now carries the complete recovered MIT-licensed application source snapshot in [NIA-Studio-AI-0.6.4-restored.zip](./NIA-Studio-AI-0.6.4-restored.zip). The archive contains 73 source, test, documentation and configuration files.

Restore the working tree locally:

```bash
unzip -q NIA-Studio-AI-0.6.4-restored.zip
cd nia-studio-ai
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/assemble_upstreams.py --dry-run
```

The GitHub Actions workflow verifies the archive checksum, ZIP integrity and package metadata on Python 3.11. It then applies the repository-owned dependency repair script (the recovered requirements omitted `itsdangerous`, which Starlette `SessionMiddleware` imports), installs the repaired runtime/dev requirements, runs tests and the source-assembly dry-run, and publishes the patched extracted-source artifact.

- Archive SHA-256: `c5eb80304ac201b7d27c3e1030c81300db8da4119d7781d6308f17e3bd98f9ae`
- Package version: `0.6.4`
- Local recovery verification: **36 tests passed** on Python 3.13.5.
- License: MIT; see [LICENSE](./LICENSE) and the copy inside the source archive.

## Runtime limitations — not a finished image/video generator

- No image or video model weights are included.
- No real image or video inference has been demonstrated.
- ComfyUI is an optional external local service and is not bundled or started automatically.
- The local NIA inference engine is a separate service; it is not embedded in the Studio server.
- Model weights and optional upstream dependencies have separate licenses and must be reviewed before use.
- No remote paid provider is enabled by this local-only snapshot.

A successful test suite validates application logic and packaging, not model inference or performance on the target Samsung device. Do not describe this as a fully operational image/video generator until real image and video outputs have been generated, opened and inspected on target hardware.
