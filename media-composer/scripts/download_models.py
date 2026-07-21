#!/usr/bin/env python3
"""Download the model checkpoints media-composer needs (currently RVM).

Fetches from the official RobustVideoMatting release into the shared ``../models/`` dir (skills repo root) and
verifies md5.  Run directly, or let ``replace-bg`` prompt you when the
checkpoint is missing.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"

_RELEASE = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0"

# name → (url, md5 or None)
CHECKPOINTS = {
    "rvm_resnet50.pth": (f"{_RELEASE}/rvm_resnet50.pth", "04da1044ab32202b73a164f679824f39"),
    "rvm_mobilenetv3.pth": (f"{_RELEASE}/rvm_mobilenetv3.pth", None),
}


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(name: str, force: bool = False) -> Path:
    """Download checkpoint *name* into ../models/ (skips if present and valid)."""
    if name not in CHECKPOINTS:
        raise ValueError(f"Unknown checkpoint: {name} (choose {'/'.join(CHECKPOINTS)})")
    url, md5 = CHECKPOINTS[name]
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    target = MODELS_DIR / name

    if target.exists() and not force:
        if md5 is None or _md5(target) == md5:
            print(f"OK (already present): {target}")
            return target
        print(f"md5 mismatch on existing {target.name} — re-downloading")

    print(f"Downloading {url} ...")
    tmp = target.with_suffix(".part")
    urllib.request.urlretrieve(url, tmp)
    if md5 is not None:
        actual = _md5(tmp)
        if actual != md5:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"md5 mismatch for {name}: expected {md5}, got {actual}")
    tmp.rename(target)
    print(f"Saved: {target} ({target.stat().st_size / 1e6:.1f} MB)")
    return target


def main() -> None:
    names = sys.argv[1:] or ["rvm_resnet50.pth"]
    for name in names:
        download(name)


if __name__ == "__main__":
    main()
