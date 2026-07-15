# ffmpeg Recipes (validated commands)

The exact command shapes behind `trim` / `extract-audio` / `replace-segment`, verified on
real talking-head footage (bill-talks v1→v7 chain). The subcommands wrap these; this file is
for understanding/debugging them.

## trim — always re-encode

```bash
ffmpeg -ss 0.5 -i in.mp4 -t 122 -c:v libx264 -crf 18 -preset medium \
  -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart out.mp4
```

- **Never `-c copy`**: stream copy cuts at the nearest keyframe; talking-head footage has
  large keyframe intervals, so the cut point freezes for seconds.
- `-ss` before `-i` = input-level seek (fast); `-t` controls duration.

## extract-audio

```bash
ffmpeg -i in.mp4 -vn -map 0:a -c:a pcm_s16le out.wav   # lossless, for transcribe
ffmpeg -i in.mp4 -vn -map 0:a -c:a aac -b:a 192k out.m4a  # distribution
```

## replace-segment — three-part concat

Replace `START`–`END` with a still image, keeping the audio as voice-over:

```bash
ffmpeg -i in.mp4 -loop 1 -framerate 30 -t LEN -i pic.jpg -filter_complex "
[0:v]trim=start=0:end=START,setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v1];
[1:v]scale=W:H:force_original_aspect_ratio=decrease,
     pad=W:H:(ow-iw)/2:(oh-ih)/2:0x3B2417,setsar=1,format=yuv420p,fps=30[v2];
[0:v]trim=start=END,setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v3];
[v1][v2][v3]concat=n=3:v=1:a=0[vout]" \
  -map "[vout]" -map 0:a -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p \
  -c:a copy -movflags +faststart out.mp4
```

- **contain fit**: `force_original_aspect_ratio=decrease` + `pad` keeps the whole image,
  bars in `pad` color. **cover fit**: `...=increase` + `crop=W:H` fills and crops.
- **Frame alignment**: snap START/END to integer frame boundaries (`round(t*fps)/fps`) —
  misaligned cuts produce visible seams at the concat joints.
- Audio `-c:a copy` runs the full timeline (the replaced span usually still narrates).

## Lossless concat (uniform sources)

When all parts share codec/resolution/fps (e.g. same-generator outputs):

```bash
printf "file 'a.mp4'\nfile 'b.mp4'\n" > list.txt
ffmpeg -f concat -safe 0 -i list.txt -c copy out.mp4
```

Only for identical stream parameters — otherwise re-encode through a concat filter.
