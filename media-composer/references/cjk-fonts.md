# CJK fonts — what actually works where

Two different font stacks are in play and they do **not** agree:

| Renderer | Used by | Works | Broken |
|----------|---------|-------|--------|
| **Pillow** | `caption` (all modes) | `/System/Library/Fonts/STHeiti Medium.ttc`, `/Library/Fonts/Arial Unicode.ttf` | `PingFang.ttc` (Pillow cannot open it) |
| **libass/fontconfig** | `subtitle-burn` | `"PingFang SC"`, `"Heiti SC"` (by *name*, resolved via fontconfig) | bare `"STHeiti"` (falls back to Verdana — no CJK) |

## Linux candidates (Pillow)

```
/usr/share/fonts/truetype/wqy/wqy-microhei.ttc
/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc
/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
```

## Tools

- `fc-match "PingFang SC"` — check what fontconfig/libass will really use.
- `fc-list :lang=zh` — list all CJK-capable fonts on the system.

## Crisp CJK in Pillow

Render at 2× and downscale with Lanczos (`caption` does this via the
`supersample` preset value). Direct 1× rendering leaves CJK strokes visibly
soft, especially at small sizes.
