# Content-Production Architecture

`content-production` handles media generation and deterministic document conversion. Ordinary text and JSON authoring remains in the Local Agent.

```text
User requests actual image / video / speech generation
        │
        └── Local Agent
                │
                ├── creates media-segments.json immediately before generation
                │       │
                │       ▼
                │   content-production CLI
                │       ├── image  → Agnes / Gemini → 000.png, ...
                │       ├── video  → Agnes / Veo   → 000.mp4, ...
                │       └── speech → Fish / Gemini → 000.mp3 or 000.wav, ...
                │
                └── media files may feed media-composer

DOCX / PDF document
        │
        └── content-production CLI
                ├── extract: DOCX/PDF → plain text
                └── convert: DOCX → structured Markdown
```

The media input is temporary CLI scaffolding, not an additional user-facing JSON deliverable. `extract` and `convert` neither consume nor create it.

## Provider flows

- **Image:** Agnes returns a URL that is downloaded; Gemini returns inline image bytes; OpenAI uses the Images API with curl by default or the OpenAI SDK as an alternative, accepts structured `size`, and returns base64 image bytes (or a URL when provided).
- **Video:** Agnes submits all requests and polls them; Gemini/Veo uses long-running operations with bounded concurrency. Completed media is downloaded as soon as it is available.
- **Speech:** SiliconFlow produces MP3; Gemini TTS returns PCM wrapped as WAV.

## Downstream consumers

- **media-composer:** compositing, concatenation, captioning, subtitles, and editing
- **Direct publishing:** article illustrations and standalone generated media
- **Agent-native follow-up:** read or edit extracted `.txt` and converted `.md` output

PPTX and XLSX document processing are not currently supported.
