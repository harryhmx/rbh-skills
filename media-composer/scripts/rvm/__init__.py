# Vendored from RobustVideoMatting (https://github.com/PeterL1n/RobustVideoMatting)
# — the `model/` package at v1.0.0. Upstream has no pip distribution, so the
# source is carried here directly. License: MIT (upstream). Sync manually if
# upstream revises; do not auto-overwrite local changes.
from .model import MattingNetwork

__all__ = ["MattingNetwork"]
