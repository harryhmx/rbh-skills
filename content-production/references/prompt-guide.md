# Prompt Writing Guide for AI Media Generation

How to write effective generation prompts for Agnes AI (image/video) and SiliconFlow (speech).
Target audience: **Local Agents** (Claude Code, Codex, etc.) that construct prompts to feed into
downstream generation APIs.

---

## image_prompt — AI Image Generation (Agnes `agnes-image-2.1-flash`)

**Length**: 2–4 sentences in English.
**Goal**: A self-contained visual description that the model can render directly.

### Required elements

| Element | What to describe |
|---------|-----------------|
| **Main subject(s)** | Who or what is in the scene — people, objects, animals. Include facial expressions for people. |
| **Setting / background** | Where the scene takes place — indoor/outdoor, environment details. |
| **Key actions** | What is happening — gestures, interactions, movement frozen in the frame. |
| **Composition / framing** | `close-up` / `medium shot` / `wide shot` / `aerial`. What is centered, what fills the frame. |
| **Lighting** | Direction (from left / backlit / overhead) and quality (soft diffused / harsh shadows / golden hour). |
| **Dominant colour palette** | 3–5 colours that set the mood — e.g. `navy blue, warm gray, cream white, brushed steel`. |

### Optional

- **Art style**: `photorealistic`, `oil painting`, `editorial illustration`, `3D render`,
  `watercolour`, `pencil sketch`. Match the style to the content's tone.
- **Camera details**: `shallow depth of field`, `bokeh background`, `35mm lens`.

### What to avoid

- Abstract concepts or emotions ("the feeling of hope") — describe what the viewer SEES.
- Overly long text — the model has limited prompt understanding.
- Internal thoughts, metaphors, text that should appear in the image.

### Example

> A wide shot of a modern office conference room with professionals seated around a long table,
> engaged in discussion. Editorial illustration style with natural lighting from floor-to-ceiling
> windows on the left. Composition centers on the presenter standing at the head of the table.
> Dominant colours: navy blue, warm gray, cream white, brushed steel.

---

## video_prompt — AI Video Generation (Agnes `agnes-video-v2.0`)

**Length**: 2–4 sentences in English.
**Goal**: A short video scene description that includes motion and temporal change.

### Required elements

| Element | What to describe |
|---------|-----------------|
| **Visual scene** | What is visible — subjects, setting, key objects (same level as image_prompt). |
| **Motion & action** | What HAPPENS over time — people move, objects change, scenes transform. |
| **Primary camera movement** | ONE of: `slow pan right` / `gentle zoom in` / `tracking shot following subject` / `static with internal motion`. |
| **Pacing** | `slow and gentle` / `energetic and quick` / `steady and deliberate`. |
| **Start/end transition** | `fade in from black` / `cut to next scene` / `hard cut from previous`. |

### Example

> Fade in from black to a wide shot of a modern conference room. The camera slowly pans right
> across attendees seated around a table, each nodding in turn as a point is made. A presenter
> at the front gestures toward a projected chart. Slow, professional pacing with natural
> atmosphere. Fade out as the discussion concludes.

---

## text — Speech Audio (SiliconFlow Fish Speech)

**Length**: Whatever the segment needs — but keep it self-contained.
**Goal**: Natural-sounding spoken audio from written text.

### Guidelines

- **Same language as the source content** — the TTS voice expects the audience's language.
- **Self-contained** — the listener has no visual context; every reference must be explicit.
- **Preserve key facts** — dates, names, numbers must be spelled out clearly.
- **Natural pauses**: Use sentence breaks and paragraph breaks to create natural speech rhythm.
  The TTS model respects punctuation (`.`, `,`, `—`) for pause timing.
- **Avoid**: Markdown formatting (`**bold**`, `[links]()`), emoji, code blocks, ASCII art.
  These will be read literally and sound unnatural.

### Pre-processing check

Before feeding text to speech generation:
1. Strip all markdown formatting.
2. Expand abbreviations on first use.
3. Read the text aloud mentally — if it sounds awkward, rephrase.
