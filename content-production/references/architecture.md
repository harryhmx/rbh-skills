# Content-Production Architecture

How `content-production` fits in the RBH pipeline and what it produces. Loaded on demand for context
— the [SKILL.md](../SKILL.md) overview has the trigger decision tree and the core run commands.

```
User Prompts / Documents
        │
        └── Local Agent
                │
                ├── creates segments.json directly from user prompts
                │       │
                │       ▼
                │   content-production (CLI)
                │       │
                │       ├── image ──> generate_images()          [IMAGE_PROVIDER]
                │       │               │
                │       │               ├── agnes:  POST /v1/images/generations → download URL
                │       │               └── gemini: POST /v1beta/interactions (Nano Banana, inline base64)
                │       │                       → 000.png, 001.png, ...
                │       │
                │       ├── video ──> generate_videos()          [VIDEO_PROVIDER]
                │       │               │
                │       │               ├── agnes:  POST /v1/videos → GET /v1/videos/{id} (parallel poll)
                │       │               └── gemini: :predictLongRunning (Veo) → poll operation → file URI
                │       │                       → Download MP4 → 000.mp4, 001.mp4, ...
                │       │
                │       └── speech ─> generate_speech()          [SPEECH_PROVIDER]
                │                       │
                │                       ├── siliconflow: Fish Speech → 000.mp3, ...
                │                       └── gemini:      Gemini TTS (PCM→WAV) → 000.wav, ...
                │                           (uses text field)
                │
                └── Binary documents (docx/pdf)
                        │
                        ▼
                content-production (CLI)
                        │
                        ├── extract ─> extract_text()
                        │               │
                        │               ├── DOCX: python-docx → .txt (per paragraph)
                        │               └── PDF:  pypdf → .txt (per page)
                        │               (--range selects a 1-indexed paragraph/page subset)
                        │
                        └── convert ─> convert_to_md()
                                        │
                                        └── DOCX: python-docx (+ mammoth fallback) → .md
                                            (headings / lists / bold-italic / tables)
```

> Image captioning (overlay text on images) has moved to **media-composer**'s `caption` subcommand.

## Output consumed by

- **media-composer**: receives images + audio for compositing and concatenation
- **Direct publishing**: images published as article illustrations
- **Manual editing**: images and audio files for further processing
- **extract**: Agent reads the resulting `.txt` / `.csv` files
- **convert**: Agent reads the resulting `.md` files (can be published directly or further edited)
