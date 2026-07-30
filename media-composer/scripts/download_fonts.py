#!/usr/bin/env python3
"""Download the SIL-OFL CJK fonts media-composer bundles (Source Han / Noto CJK SC).

Fetches the Simplified-Chinese Source Han family — Google's Noto CJK SC
distribution (= Adobe + Google Source Han Sans/Serif, identical glyphs, SIL
OFL) — into the shared ``../fonts/`` dir (skills repo root, same place as the
RVM ``../models/``) and verifies md5.  These bundled fonts are the
license-clean default for ``caption`` and ``subtitle-burn``; system fonts
(Apple STHeiti/PingFang, whose license forbids embedding in commercial video)
are last-resort fallbacks only.  Run directly, or let the skills pick them up
once present.

Mirrors ``download_models.py`` (RVM checkpoints): large binaries, gitignored,
fetched on demand, shared across skills at the repo root.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parents[2] / "fonts"

_SOURCE = "https://raw.githubusercontent.com/notofonts/noto-cjk/main"
# family/weight → (url, md5)
FONTS = {
    "NotoSansCJKsc-Regular.otf": (
        f"{_SOURCE}/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
        "6d30d01b9b25bd766898ecba71d5cd3d",
    ),
    "NotoSansCJKsc-Bold.otf": (
        f"{_SOURCE}/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf",
        "3a01596d9e24dc34f03fba7bfccdf141",
    ),
    "NotoSerifCJKsc-Regular.otf": (
        f"{_SOURCE}/Serif/OTF/SimplifiedChinese/NotoSerifCJKsc-Regular.otf",
        "1b00b42cf7cf738611ad53442ea1ea7f",
    ),
    "NotoSerifCJKsc-Bold.otf": (
        f"{_SOURCE}/Serif/OTF/SimplifiedChinese/NotoSerifCJKsc-Bold.otf",
        "6cccfeac1c9e12c520c3027ace51fa12",
    ),
}


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(name: str, force: bool = False) -> Path:
    """Download font *name* into ../fonts/ (skips if present and valid)."""
    if name not in FONTS:
        raise ValueError(f"Unknown font: {name} (choose {'/'.join(FONTS)})")
    url, md5 = FONTS[name]
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    target = FONTS_DIR / name

    if target.exists() and not force:
        if _md5(target) == md5:
            print(f"OK (already present): {target}")
            return target
        print(f"md5 mismatch on existing {target.name} — re-downloading")

    print(f"Downloading {url} ...")
    tmp = target.with_suffix(".part")
    urllib.request.urlretrieve(url, tmp)
    actual = _md5(tmp)
    if actual != md5:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"md5 mismatch for {name}: expected {md5}, got {actual}")
    tmp.rename(target)
    print(f"Saved: {target} ({target.stat().st_size / 1e6:.1f} MB)")
    return target


def main() -> None:
    names = sys.argv[1:] or list(FONTS)
    for name in names:
        download(name)


if __name__ == "__main__":
    main()
