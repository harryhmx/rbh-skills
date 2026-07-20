# Article Writing Guide for Local Agents

How to write MD articles that work well in the RBH content pipeline.
Target audience: **Local Agents** (Claude Code, Codex, etc.) acting as the content author.

---

## Article Structure

A well-formed RBH article follows this skeleton:

```markdown
# <Article Title — concise, descriptive, 4–12 words>

> <One-line subtitle or hook — 1 sentence that makes the reader want to continue>

## <Section 1 heading>

<Body paragraphs — 2–5 paragraphs per section. Each paragraph 2–5 sentences.
Vary sentence length for rhythm.>

## <Section 2 heading>

...

## <Section N heading>

---

**<Closing call-to-action or summary — 1–2 sentences>**
```

### Section guidelines

- **3–6 sections** is a good target for most articles (800–2000 words total).
- Each section should cover ONE idea. If you find yourself switching topics mid-section,
  split it.
- Section headings should be **descriptive** ("Why phonics works for ages 6–7") rather
  than generic ("Background").

---

## Input Validation Guardrails

Before writing, evaluate the user's request against these criteria.
**If the request fails any check, ask the user to clarify — do NOT proceed to writing.**

### 1. Is the topic specific enough?

| Too vague (REJECT) | Specific enough (ACCEPT) |
|---|---|
| "Write an article about English learning" | "Write an article about phonics-based reading strategies for 6–7 year old ESL learners" |
| "写一篇关于留学的文章" | "写一篇关于英国本科申请个人陈述写作技巧的文章，面向高二学生" |
| "Something about math" | "Explain the chain rule with 3 worked examples for high school calculus students" |

**Rule of thumb**: If you can't list 3 distinct section headings from the prompt alone,
it's too vague — ask for the audience, scope, and key points.

### 2. Is the audience specified?

The user should tell you (or you should ask):
- **Who** is reading this? (parents of 6-year-olds / high school students / English teachers)
- **What** do they already know? (beginners / intermediate / advanced)
- **What** should they be able to do after reading?

If the audience is unspecified, default to **general educated adult** and note this in your response.

### 3. Is the requested length reasonable?

| Request | Assessment |
|---|---|
| "< 300 words" | Too short for a substantive article — suggest 500+ or a micro-post format. |
| "500–2000 words" | Normal range. |
| "> 5000 words" | Is this a guide/ebook? Confirm with user — may need chapter splitting. |

### 4. Does the user provide source material or key facts?

If the article requires factual claims (statistics, research findings, historical events)
and the user provides none, either:
- Ask the user to supply the facts, or
- Clearly mark unknowns with `[citation needed]` and warn the user.

**NEVER fabricate statistics, study results, or expert quotes.**

---

## Writing Style by Content Type

### Educational / instructional articles (adventure-academy, HarryMath)

- **Tone**: Warm, encouraging, authoritative but not condescending.
- **Sentence length**: Shorter for younger audiences, normal for adults/teachers.
- **Structure**: Concept → Example → Practice/Application. Show, don't just tell.
- **Chinese content**: Use natural, conversational Chinese. Avoid translation-ese.

### Technical / tutorial articles (RBH Skills)

- **Tone**: Precise, clear, step-by-step.
- **Structure**: Problem → Solution → Code/Commands → Expected output → Troubleshooting.
- **Code blocks**: Always specify language for syntax highlighting. Include comments.

### Opinion / personal brand articles (Hepmad Media)

- **Tone**: Authentic, first-person where appropriate.
- **Structure**: Hook → Personal experience → General insight → Takeaway.

---

## Optional: Pairing Articles with Media

Writing the article itself is always Agent-native. Continue to this workflow **only when the user actually requests generated images**; suggesting prompts or delivering an article alone must not create a media input file.

1. After writing the article, identify 1–3 places where an illustration would add value
   (section openers, concept explanations, emotional moments).
2. For each spot, write an `image_prompt` following `references/prompt-guide.md`.
3. Create `media-segments.json` using the schema in `references/cli-reference.md`.
4. Run `content-production image` to generate the images.
5. Insert `![](images/000.png)` links at the corresponding positions in the article.

### When to generate images

| Article type | Images recommended? |
|---|---|
| Step-by-step tutorial | Yes — screenshots or diagrams at each major step |
| Concept explanation | Yes — 1 illustration per concept |
| Personal essay / opinion | Optional — 1 header image |
| Pure news / update | Usually not needed |

---

## Quality Checklist

Before finalising the article, verify:

- [ ] Title is specific and searchable (not clickbait).
- [ ] Subtitle/hook is present and engaging.
- [ ] Sections flow logically from one to the next.
- [ ] No section is a single sentence — merge or expand.
- [ ] All factual claims are either sourced by the user or marked `[citation needed]`.
- [ ] Code blocks (if any) have language tags and are self-contained.
- [ ] Reading time is roughly 3–10 minutes (800–2000 words for most articles).
- [ ] No markdown syntax errors (unclosed fences, broken links).
