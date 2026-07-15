# Subtitle styling (libass force_style)

How `subtitle-burn` styles SRT rendering, and the traps.

## Requirements

The `subtitles` filter needs a libass-capable ffmpeg. `resolve_ffmpeg(need_libass=True)`
finds one by **capability detection** (env `MC_FFMPEG_FULL` → `ffmpeg-full` on PATH →
`brew --prefix` → common keg paths → plain `ffmpeg`, each checked via `-filters`). Slim
Homebrew `ffmpeg` builds often lack it; `brew install ffmpeg-full` on macOS.

## Validated style (bill-talks-v7, 544×960)

```
FontName=PingFang SC,Fontsize=12,PrimaryColour=&H00A6B814,OutlineColour=&H00000000,
BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginL=28,MarginR=28,MarginV=20
```

Stored as `assets/style-presets/subtitle-default.json`.

## ASS color format — &HAABBGGRR

Byte order is alpha-blue-green-**red**, not RGB:

| Name | RGB | ASS |
|------|-----|-----|
| teal | `#14B8A6` | `&H00A6B814` |
| white | `#FFFFFF` | `&H00FFFFFF` |
| yellow | `#FFFF00` | `&H0000FFFF` |

Conversion: `#RRGGBB` → `&H00` + `BB` + `GG` + `RR`.

## Fontsize is NOT pixels

`force_style` Fontsize is in libass **PlayRes units**, scaled by PlayResX vs video width —
rendered size is not 1:1 with the number. `Fontsize=12` on a 544-wide video renders around
~30px visually. Calibrate by eye per resolution. If exact pixels matter, generate an
explicit ASS file with `PlayResX=<video width>` instead of burning SRT directly.

## Positioning

- `Alignment` uses numpad layout: `2` bottom-center, `8` top-center.
- **Always set `MarginL`/`MarginR`** (28 works) — long lines otherwise touch the frame
  edges before wrapping.
- `MarginV` is the distance from the aligned edge.

## CJK fonts under libass

- Use `"PingFang SC"` or `"Heiti SC"` on macOS. Verify with `fc-match "PingFang SC"`.
- Plain `"STHeiti"` mismatches through fontconfig to Verdana (no CJK) — avoid.
- Note the inversion vs Pillow: libass reads PingFang.ttc fine; Pillow cannot (see
  cjk-fonts.md).
