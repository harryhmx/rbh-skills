# RVM matting — architecture & operations

How `replace-bg` works internally (Robust Video Matting, ResNet50 variant).

## Pipeline (no temp frames)

```
ffmpeg decode --stdout--> raw rgb24 frames
        ↓
Python reads chunks (default 8 frames) → RVM forward pass (MPS/CPU)
→ alpha composite: out = fgr*pha + bg*(1-pha)
        ↓
ffmpeg encode <--stdin--- H.264 silent video → final audio mux
```

- Frames travel as raw rgb24 bytes over OS pipes — **backpressure-safe**: when inference
  is the bottleneck, the decoder simply blocks on its full stdout buffer.
- **Temporal recurrence**: RVM carries 4 recurrent states; `replace_bg` threads
  `rec = [None]*4` across chunks so temporal consistency spans the whole video. RVM is
  robust to the cold start.
- `auto_downsample_ratio = min(512/max(h,w), 1)` — the official heuristic (≈0.533 for
  544×960). The DeepGuidedFilter refiner restores full-resolution edges.
- Tensor path: `torch.frombuffer(bytearray(...))` (bytearray wrap avoids the non-writable
  warning) → `view(T,h,w,3).permute(0,3,1,2)` → `[1,T,3,H,W]` float / 255.

## Performance (Apple Silicon MPS)

- 544×960, resnet50: ~22–28 fps matting; peak ~1 GB GPU memory.
- `--chunk 8` amortizes Python overhead; larger chunks add memory, little speed.

## Checkpoints

| File | Variant | MD5 |
|------|---------|-----|
| `rvm_resnet50.pth` (~103 MB) | quality (needs torchvision) | `04da1044ab32202b73a164f679824f39` |
| `rvm_mobilenetv3.pth` (~15 MB) | light (no torchvision) | (not pinned) |

Source: `https://github.com/PeterL1n/RobustVideoMatting/releases/tag/v1.0.0`.
Fetched by `scripts/download_models.py` into `../models/` (gitignored).

## Vendored source

`scripts/rvm/` is a snapshot of upstream `model/` (MIT license, no pip distribution).
Sync manually if upstream revises. Unused upstream capabilities worth knowing about:
`inference.py` offers green-screen/pha output and photo mode — re-clone the public repo
if `replace-bg` ever needs those.
