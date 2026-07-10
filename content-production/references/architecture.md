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
                │       ├── image ──> generate_images()
                │       │               │
                │       │               └── POST /v1/images/generations
                │       │                       → Agnes AI → 000.png, 001.png, ...
                │       │
                │       ├── video ──> generate_videos()
                │       │               │
                │       │               ├── POST /v1/videos (create video)
                │       │               ├── GET /v1/videos/{video_id} (parallel poll)
                │       │               └── Download MP4 → 000.mp4, 001.mp4, ...
                │       │
                │       └── speech ─> generate_speech()
                │                       │
                │                       └── SiliconFlow Fish Speech → 000.mp3, ...
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

- **video-converter**: receives images + audio for video synthesis
- **Direct publishing**: images published as article illustrations
- **Manual editing**: images and audio files for further processing
- **extract**: Agent reads the resulting `.txt` / `.csv` files
- **convert**: Agent reads the resulting `.md` files (can be published directly or further edited)
