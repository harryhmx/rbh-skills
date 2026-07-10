# Content-Production Examples

End-to-end examples for each generation path. Loaded on demand. For argument details see
[cli-reference.md](cli-reference.md); for the trigger decision tree see the [SKILL.md](../SKILL.md)
overview.

## Contents

- [Example 1 — Direct from prompts (default path)](#example-1--direct-from-prompts-default-path)
- [Example 2 — JSON output structure (image generation)](#example-2--json-output-structure-image-generation)
- [Example 3 — Generate videos from segments](#example-3--generate-videos-from-segments)
- [Example 4 — Speech generation](#example-4--speech-generation)

---

## Example 1 — Direct from prompts (default path)

The Local Agent creates a segments JSON directly from user prompts:

```json
// prompts.json — created by Local Agent
{
  "total_segments": 2,
  "segments": [
    {
      "index": 0,
      "title": "Sunset mountains",
      "image_prompt": "A breathtaking sunset over snow-capped mountains, warm orange and pink sky, photorealistic, 4K"
    },
    {
      "index": 1,
      "title": "Forest stream",
      "image_prompt": "A crystal-clear stream winding through a dense green forest, dappled sunlight, cinematic lighting"
    }
  ]
}
```

```bash
# Generate images directly
python scripts/cli.py image -i prompts.json -o images/
```

Output:

```
images/
├── 000.png   # Segment 0 image
├── 001.png   # Segment 1 image
├── 002.png   # Segment 2 image
├── 003.png   # Segment 3 image
```

---

## Example 2 — JSON output structure (image generation)

The CLI prints a JSON summary to stdout after generation:

```json
{
  "total": 4,
  "succeeded": 4,
  "failed": 0,
  "results": [
    {
      "index": 0,
      "title": "Opening Scene",
      "file_path": "/abs/path/to/images/000.png",
      "url": "https://...",
      "prompt": "A wide shot of a sunlit classroom..."
    }
  ]
}
```

---

## Example 3 — Generate videos from segments

The Local Agent creates a segments JSON with `video_prompt` fields, then:

```bash
python scripts/cli.py video -i segments.json -o videos/ --size 1152x768 --num-frames 121 --frame-rate 24
```

Output:

```
videos/
├── 000.mp4   # Segment 0 video
├── 001.mp4   # Segment 1 video
├── 002.mp4   # Segment 2 video
├── 003.mp4   # Segment 3 video
```

Video generation is asynchronous — each video is submitted to Agnes AI, polled until complete (up to
15 min timeout), then downloaded. The JSON output includes `video_id` for each video result.

---

## Example 4 — Speech generation

The Local Agent creates a segments JSON with `text` fields directly from user input.

```bash
# Generate speech audio
python scripts/cli.py speech -i segments.json -o audio/
```

Output:

```
audio/
├── 000.mp3   # Segment 0 audio
├── 001.mp3   # Segment 1 audio
├── 002.mp3   # Segment 2 audio
├── 003.mp3   # Segment 3 audio
```

The speech content comes from the `text` field.
