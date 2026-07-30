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

## Licensing — commercial video font red line

These skills render text **into published videos**, so font licensing is a
project-level red line. A license that allows "display on the device" does
**not** allow extracting the font outlines into a redistributed video.

❌ **Do NOT use** (extraction into commercial video is a violation):
- **Microsoft YaHei / Windows SimSun / SimHei** — Founder/Microsoft license;
  free to display on Windows, embedding in commercial output is not.
- **PingFang / STHeiti (Apple system fonts)** — Apple-device use only;
  extracting and republishing is not permitted. ⚠️ These were the old defaults
  (`caption` → STHeiti, `subtitle-burn` → PingFang SC) — the bundled-font
  change below retires that default.
- **Founder (most) / Hanyi** — paid commercial license required (Founder has
  only four classic faces free for commercial use).

✅ **Safe** (SIL OFL or official free-for-commercial-use, bundleable):
- **Source Han Sans / Serif (思源黑体 / 思源宋体) = Noto CJK** — Adobe + Google,
  SIL OFL. Body-text gold standard. This is what `media-composer` bundles.
- **Smiley Sans (得意黑)** — OFL, modern display/title face.
- **LXGW WenKai (霞鹜文楷)** — OFL, handwriting/kaiti style (suits math/tutorial lines).
- **Alibaba PuHuiTi / OPPO Sans / HarmonyOS Sans / ZCOOL family** — official free commercial use.
- Font directories: [maoken.com](https://www.maoken.com/), [100font.com](https://www.100font.com/).

## Bundled OFL fonts (the default)

The bundled SIL-OFL **Source Han** family (Google's **Noto CJK SC**
distribution — identical glyphs to Adobe Source Han Sans/Serif SC,
co-released under SIL OFL) lives at the skills repo root in `../fonts/`,
shared with the RVM `../models/`. It is fetched on demand — large binaries,
gitignored, same pattern as the model checkpoints:

```bash
python scripts/download_fonts.py     # Noto Sans/Serif CJK SC, Regular + Bold
```

Both renderers prefer the bundled font and fall back to system fonts only when
it is absent (so behavior is unchanged on a machine that has not run the
download):

| Renderer | Default | Fallback | How it picks the bundled font |
|----------|---------|----------|-------------------------------|
| **Pillow** (`caption`) | `NotoSansCJKsc-Regular.otf` | system `_CJK_FONT_CANDIDATES` | opened directly by path |
| **libass** (`subtitle-burn`) | family `Noto Sans CJK SC` | fontconfig system fonts | `fontsdir=../fonts` clause (added only when the dir has fonts) |

`subtitle-burn --bold` resolves to the real bundled **Bold** face
(`NotoSansCJKsc-Bold.otf`) because Regular and Bold share the family name and
libass selects by style. Bundling the font also fixes cross-machine drift
(macOS used to render STHeiti, Linux Noto → different outputs).
