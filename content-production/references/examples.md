# Content-Production Examples

These examples create `media-segments.json` only because actual media generation follows. Do not create this file for ordinary article, Markdown, JSON, or prompt-writing requests.

## Image generation

```json
{
  "segments": [
    {
      "index": 0,
      "title": "Sunset mountains",
      "image_prompt": "A breathtaking sunset over snow-capped mountains, warm orange and pink sky, photorealistic"
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
python scripts/cli.py image -i media-segments.json -o images/
```

```text
images/
├── 000.png
└── 001.png
```

The CLI summary contains two results because the input contains two segments:

```json
{
  "total": 2,
  "succeeded": 2,
  "failed": 0,
  "results": [
    {
      "index": 0,
      "title": "Sunset mountains",
      "file_path": "/abs/path/to/images/000.png",
      "url": "https://provider.example/image.png",
      "prompt": "A breathtaking sunset over snow-capped mountains, warm orange and pink sky, photorealistic"
    }
  ]
}
```

## Reusing one input for several media types

A segment may contain all three known fields:

```json
{
  "segments": [
    {
      "index": 0,
      "title": "Welcome",
      "image_prompt": "A welcoming English classroom, warm morning light",
      "video_prompt": "Slow camera movement through a welcoming English classroom in warm morning light",
      "text": "Welcome to today's English adventure."
    }
  ]
}
```

```bash
python scripts/cli.py image  -i media-segments.json -o images/
python scripts/cli.py video  -i media-segments.json -o videos/
python scripts/cli.py speech -i media-segments.json -o audio/
```

Agnes/SiliconFlow produce PNG, MP4, and MP3. Gemini image/video/speech produce PNG, MP4, and WAV.

## Failed media items remain visible

If one video times out, the batch still reports that input:

```json
{
  "total": 2,
  "succeeded": 1,
  "failed": 1,
  "results": [
    {
      "index": 1,
      "title": "Closing scene",
      "file_path": null,
      "url": null,
      "prompt": "Camera pulls away from the classroom at sunset",
      "video_id": "video_123",
      "error": "Timed out after 900s"
    }
  ]
}
```

## Document conversion

Document commands do not use or create a media input:

```bash
python scripts/cli.py extract -i report.docx -o report.txt
python scripts/cli.py extract -i paper.pdf --range 2-5 -o excerpt.txt
python scripts/cli.py convert -i report.docx -o report.md
```
