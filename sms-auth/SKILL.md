---
name: sms-auth
description: "SMS verification code authentication for user login and registration. Use when implementing phone-number-based auth flows: sending verification codes, verifying codes, and issuing JWT tokens."
---

# SMS Auth

Phone-number-based authentication via SMS verification codes. Users receive a code on their phone, verify it, and are automatically logged in (new users are auto-registered).

## Use Cases

- Authenticate users via SMS verification code (login)
- Auto-register new users on first verification
- Send verification codes with rate limiting and cooldown

## Authentication Flow

```
Client ──▶ POST /sms/send ──▶ Alibaba Cloud SMS API ──▶ User's Phone
         (phone_number)        (sends code)

Client ──▶ POST /sms/verify ──▶ Alibaba Cloud Verify API
         (phone_number,          (validates code)
          verify_code)
              ◀── JWT tokens + user info
```

**Step-by-step:**

1. **Send Code** — Client submits phone number, server validates format and calls Alibaba Cloud SMS API to send a 6-digit code
2. **User Enters Code** — Code is valid for 5 minutes; 60-second cooldown between sends
3. **Verify & Login** — Server calls Alibaba Cloud Verify API to validate the code; on success, finds or creates the user and returns JWT tokens

## API Endpoints

### POST `/sms/send`

Send an SMS verification code to the given phone number.

**Request Body:**

```json
{
  "phone_number": "13800138000"
}
```

**Response (Success):**

```json
{
  "success": true,
  "message": "验证码已发送",
  "cooldown_seconds": 60
}
```

**Response (Failure):**

```json
{
  "success": false,
  "message": "发送过于频繁，请稍后再试"
}
```

**Validation Rules:**

| Rule | Value |
|------|-------|
| Phone format | Regex `^1[3-9]\d{9}$` (Chinese mainland mobile) |
| Cooldown | 60 seconds between sends |
| Rate limit | 3 requests per minute |

### POST `/sms/verify`

Verify the SMS code and complete login/registration.

**Request Body:**

```json
{
  "phone_number": "13800138000",
  "verify_code": "123456"
}
```

**Response (Success):**

```json
{
  "success": true,
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": {
    "id": 1,
    "username": "user_13800138000",
    "phone_number": "138****8000"
  }
}
```

**Response (Failure):**

```json
{
  "success": false,
  "message": "验证码错误或已过期"
}
```

**Business Logic:**

- Code verification is delegated to Alibaba Cloud API (never stored locally)
- New users are auto-registered with username format: `user_{phone_number}`
- Existing users are logged in directly
- Access Token: 4 hours expiry
- Refresh Token: 7 days expiry

## SMS Service Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Provider | Alibaba Cloud DYPNS | `alibabacloud_dypnsapi20170525` SDK |
| Endpoint | `dypnsapi.aliyuncs.com` | API endpoint |
| Sign Name | `速通互联验证码` | SMS signature |
| Template Code | `100001` | SMS template ID |
| Template Param | `{"code":"##code##","min":"5"}` | Template parameters |
| Code Expiry | 5 minutes | `SMS_CODE_EXPIRE_MINUTES` |
| Send Cooldown | 60 seconds | `SMS_COOLDOWN_SECONDS` |

## Environment Variables

```env
ALIBABA_CLOUD_ACCESS_KEY_ID=
ALIBABA_CLOUD_ACCESS_KEY_SECRET=
```

## Database Schema

### `users` table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | serial | PK | User ID |
| username | varchar(150) | UNIQUE, NOT NULL | Username (auto-generated for new users) |
| phone_number | varchar(20) | UNIQUE | Phone number (login credential) |
| created_at | timestamp | NOT NULL | Registration time |
| updated_at | timestamp | NOT NULL | Last updated |

> No separate verification code table is needed — code generation and validation are fully handled by the Alibaba Cloud API.

## Scripts

### `scripts/sms.py`

Core module containing all SMS auth logic:

- `send_sms_verify_code(phone_number)` — Validates phone format, checks cooldown, calls Alibaba Cloud to send SMS code
- `check_sms_verify_code(phone_number, verify_code)` — Validates code presence, calls Alibaba Cloud to verify code
- `_create_client()` — Initializes the Alibaba Cloud DYPNS client with credentials from settings
- In-memory cooldown tracking (`_cooldown` dict keyed by phone number)

**Security measures:**

- Phone number regex validation (`^1[3-9]\d{9}$`)
- Dual-layer rate limiting: per-IP throttle (3/min) + per-phone cooldown (60s)
- Zero local code storage — all verification delegated to provider API
- Phone number masking in responses (`138****8000`)

## Dependencies

```bash
pip install alibabacloud-dypnsapi20170525 alibabacloud-credentials
```

See [references/requirements.txt](references/requirements.txt) for full dependency list.

## Adaptation Notes

This skill is adapted from a reference Django implementation. Key changes for this FastAPI + Supabase project:

| Aspect | Reference Project | RBH Skills (This Project) |
|--------|---------------------|---------------------------|
| Framework | Django + DRF | FastAPI |
| Database | Django ORM (SQLite) | Supabase (PostgreSQL) |
| Validation | Django serializer | Pydantic model |
| JWT | djangorestframework-simplejwt | PyJWT / python-jose |
| Config | Django settings + .env | pydantic-settings |
| Routing | DRF ViewSet + urls.py | FastAPI router |
