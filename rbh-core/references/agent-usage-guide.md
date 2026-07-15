# Agent Usage Guide

This guide shows how Agent (Claude) uses rbh-core CLI to create conversational authentication experiences.

## Design Philosophy

**CLI = Parameterized, not Interactive**
- CLI commands accept all inputs as arguments (`--username`, `--phone`, `--code`)
- No `input()` or `getpass()` calls — fully non-interactive
- Agent creates conversational flow by asking questions and passing answers to CLI

## Conversational Flow Examples

### Example 1: SMS Login

**User Request**: "Help me login to RBH platform"

**Agent Conversation**:

```
Agent: What's your username?
User: Mengxun Huang

Agent: Do you want to use password or SMS verification?
User: SMS verification

Agent: What's your phone number?
User: 18118784765

[Agent executes: python scripts/cli.py auth send-sms --phone 18118784765]

Agent: ✓ Verification code sent to 181****4765. What's the code?
User: 9774

[Agent executes: python scripts/cli.py auth login-sms --username mengxun_huang --phone 18118784765 --code 9774]

Agent: ✓ Login successful! Welcome, Mengxun Huang!
```

**Behind the scenes**:
1. Agent asks questions in natural language
2. User provides answers conversationally
3. Agent translates answers to CLI arguments
4. Agent executes CLI command with all parameters
5. Agent presents result in friendly format

### Example 2: Registration

**User Request**: "Register a new account"

**Agent Conversation**:

```
Agent: Choose a username (3-20 characters):
User: john_doe

Agent: Create a password (at least 6 characters):
User: mySecurePass123

[Agent executes: python scripts/cli.py auth register --username john_doe --password mySecurePass123]

Agent: ✓ Registration successful! Welcome, john_doe!
      ✓ You're now logged in automatically.
```

### Example 3: Create Project (Authenticated)

**User Request**: "Create a new project about space exploration"

**Agent Conversation**:

```
[Agent checks: python scripts/cli.py auth whoami]

[If logged in:]
[Agent executes: python scripts/cli.py project generate --prompt "space exploration"]

Agent: ✓ Project created successfully!
      Title: Journey to Mars
      Description: An educational adventure exploring the solar system...

[If not logged in:]
Agent: You need to login first. Would you like to login now?
```

## Command Reference

### Authentication Commands

```bash
# Register new user
python scripts/cli.py auth register --username <username> --password <password>

# Login with password
python scripts/cli.py auth login --username <username> --password <password>

# Send SMS verification code
python scripts/cli.py auth send-sms --phone <phone_number>

# Login with SMS code
python scripts/cli.py auth login-sms --username <username> --phone <phone> --code <code>

# Check current user
python scripts/cli.py auth whoami

# Logout
python scripts/cli.py auth logout
```

### Project Commands

```bash
# Generate new project (requires authentication)
python scripts/cli.py project generate --prompt "<project_idea>"
```

## Session Management

- Sessions are stored in `~/.rbh/session.json`
- Auto-saved after successful login/registration
- Validated via JWT token
- Used by `@require_auth` decorator in project commands

## Error Handling

Agent should handle these common errors gracefully:

```bash
# Not logged in
$ python scripts/cli.py project generate --prompt "test"
Error: Not logged in. Please authenticate first.

# Invalid credentials
$ python scripts/cli.py auth login --username wrong --password wrong
{
  "success": false,
  "message": "Invalid username or password"
}

# SMS cooldown
$ python scripts/cli.py auth send-sms --phone 18118784765
{
  "success": false,
  "message": "Please wait 45s before retrying"
}
```

## Best Practices for Agent

1. **Always check login status first** when user requests authenticated actions
2. **Mask sensitive data** in conversation (e.g., `181****4765` not full phone number)
3. **Parse JSON output** from CLI to present results naturally
4. **Handle errors gracefully** and guide user to retry or fix issues
5. **Normalize usernames** (e.g., "Mengxun Huang" → "mengxun_huang")

## Implementation Notes

- CLI uses `importlib` to load modules from kebab-case directory (`rbh-core/`)
- All commands return JSON for programmatic parsing
- Exit codes: 0 = success, 1 = failure
- Session JWT has 7-day expiration
