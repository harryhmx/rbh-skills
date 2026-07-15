# Audio loudness — two-pass loudnorm

How `enhance` normalizes loudness. Two-pass **linear** mode avoids the pumping/breathing
artifacts of single-pass dynamic normalization.

## Why two passes

`loudnorm` in one pass works *dynamically* — it adjusts gain continuously, which audibly
"breathes" on speech. Feeding the filter its own measurements switches it to *linear* mode:
one constant gain, clean result.

## Pass 1 — measure

```bash
ffmpeg -i in.mp4 -af "highpass=f=80,afftdn=nr=8,loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json" \
  -vn -f null -
```

The JSON block on stderr contains `input_i`, `input_tp`, `input_lra`, `input_thresh`,
`target_offset`.

## Pass 2 — apply with measured values

```bash
ffmpeg -i in.mp4 -af "highpass=f=80,afftdn=nr=8,loudnorm=I=-16:TP=-1.5:LRA=11\
:measured_I=<input_i>:measured_TP=<input_tp>:measured_LRA=<input_lra>\
:measured_thresh=<input_thresh>:offset=<target_offset>:linear=true" \
  -c:a aac -b:a 192k -ar 44100 out.mp4
```

- **Prefilter first**: `highpass=f=80` removes rumble, `afftdn=nr=8` light spectral
  denoise — run them in *both* passes so measurements match the final chain.
- Target: `I=-16` LUFS (voice content), `TP=-1.5` dBTP true-peak ceiling.
- Validated example: source −22.62 LUFS → −16.13 LUFS (+6.5 dB perceived) with true peak
  held under −1.5 dB.

## Picture chain (same subcommand)

```
hqdn3d=1.5:1.5:6:6, unsharp=5:5:0.5, format=yuv420p
```

Denoise **before** sharpening — the reverse amplifies grain. Encode `-crf 16 -preset slow`
for the final-quality pass.
