# Data Models

## Project

Represents a learning project in the RBH platform.

**Database Table:** `Project`

**Fields:**
- `id` (String, UUID) — Primary key
- `title` (String) — Project title (max 100 characters)
- `description` (String, optional) — Project description (100-200 characters)
- `systemPrompt` (String, optional) — Custom system prompt for story generation
- `conclusionPrompt` (String, optional) — Custom conclusion prompt for story generation
- `createdAt` (DateTime) — Creation timestamp
- `updatedAt` (DateTime) — Last update timestamp

**Example:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Space Exploration Adventure",
  "description": "A thrilling journey through the cosmos for young learners",
  "systemPrompt": "You are a creative storyteller...",
  "conclusionPrompt": "Wrap up the adventure with...",
  "createdAt": "2026-07-16T10:00:00Z",
  "updatedAt": "2026-07-16T10:00:00Z"
}
```

---

## User (Future - Stage 4+)

Represents a user account (student or teacher).

**Database Table:** `User`

**Fields:**
- `id` (String, UUID) — Primary key
- `phone` (String, unique) — Phone number for authentication
- `name` (String, optional) — Display name
- `avatar` (String, optional) — Avatar URL
- `level` (Int, default: 1) — User level
- `score` (Int, default: 0) — Total score
- `createdAt` (DateTime) — Creation timestamp
- `updatedAt` (DateTime) — Last update timestamp

---

## Article (Future - Stage 4+)

Represents learning content articles.

**Database Table:** `Article`

**Fields:**
- `id` (String, UUID) — Primary key
- `title` (String) — Article title
- `content` (String) — Article content
- `authorId` (String) — Reference to User.id
- `published` (Boolean, default: false) — Publication status
- `createdAt` (DateTime) — Creation timestamp
- `updatedAt` (DateTime) — Last update timestamp

---

## Story

Represents branching story chapters (managed by adventure-academy skill).

**Database Table:** `Story`

**Fields:**
- `id` (String, UUID) — Primary key
- `projectId` (String) — Reference to Project.id
- `title` (String) — Story chapter title
- `content` (String) — Story content
- `imageUrl` (String, optional) — AI-generated image URL
- `audioUrl` (String, optional) — TTS audio URL
- `rcQuestion` (JSON, optional) — Reading Comprehension question
- `ctQuestion` (JSON, optional) — Critical Thinking question
- `depth` (Int) — Story depth in branching tree
- `parentStoryId` (String, optional) — Parent story reference
- `createdAt` (DateTime) — Creation timestamp
- `updatedAt` (DateTime) — Last update timestamp

**Note:** Story data model is documented here for reference. Story operations are handled by the adventure-academy skill.
