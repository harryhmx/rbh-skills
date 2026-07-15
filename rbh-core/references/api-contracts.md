# API Contracts

## SMS Authentication

### POST /api/auth/sms/send

Send SMS verification code to phone number.

**Request:**
```json
{
  "phone_number": "13800138000"
}
```

**Response (success):**
```json
{
  "success": true,
  "message": "Code sent",
  "cooldown_seconds": 60
}
```

**Response (cooldown):**
```json
{
  "success": false,
  "message": "Please wait 45s before retrying"
}
```

**Response (invalid phone):**
```json
{
  "success": false,
  "message": "Invalid phone number format"
}
```

---

### POST /api/auth/sms/verify

Verify SMS code for phone number.

**Request:**
```json
{
  "phone_number": "13800138000",
  "verify_code": "123456"
}
```

**Response (success):**
```json
{
  "success": true,
  "message": "Verified"
}
```

**Response (invalid code):**
```json
{
  "success": false,
  "message": "Invalid or expired code",
  "error_type": "invalid_code"
}
```

**Response (missing code):**
```json
{
  "success": false,
  "message": "Code is required",
  "error_type": "missing_code"
}
```

---

## Project Management

### (Future) POST /api/project/generate

Generate Project via LLM and sync to database.

**Request:**
```json
{
  "prompt": "Create a story about space exploration"
}
```

**Response:**
```json
{
  "id": "uuid",
  "title": "Space Exploration Adventure",
  "description": "A thrilling journey through the cosmos...",
  "createdAt": "2026-07-16T10:00:00Z",
  "updatedAt": "2026-07-16T10:00:00Z"
}
```

**Note:** This route is not exposed in Phase 3.3. Implementation deferred to Stage 4+.

---

## Future Expansion (Stage 4+)

### Article CRUD
- `POST /api/article/create`
- `GET /api/article/{article_id}`
- `PUT /api/article/{article_id}`
- `DELETE /api/article/{article_id}`
- `GET /api/article/list`

### User Profile
- `GET /api/user/profile`
- `PUT /api/user/profile`
