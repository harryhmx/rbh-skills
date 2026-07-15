# Models

Large binary checkpoints used by media-composer subcommands. Not tracked in git
(`.gitignore` excludes `*.pth`) — run `python scripts/download_models.py` to fetch,
or download manually per the table below.

| File | Used by | Size | Source | MD5 |
|------|---------|------|--------|-----|
| `rvm_resnet50.pth` | `replace-bg` | ~103 MB | [RobustVideoMatting v1.0.0](https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_resnet50.pth) | `04da1044ab32202b73a164f679824f39` |
| `rvm_mobilenetv3.pth` | `replace-bg --variant mobilenetv3` (optional) | ~15 MB | [RobustVideoMatting v1.0.0](https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3.pth) | (not pinned) |
