[README.md](https://github.com/user-attachments/files/26199863/README.md)
# Project Team Bot v2

A production-ready Slack bot and FastAPI web server featuring a 5-agent system for ISO 21500:2021 compliant project analysis.

## Features

- **Dual Interface**: Slack bot + Web API with streaming responses
- **5-Agent Pipeline**: Specialized agents working sequentially with context preservation
- **ISO 21500:2021 Compliance**: All agents reference ISO standards terminology
- **Streaming Responses**: Server-Sent Events (SSE) with NDJSON format
- **JWT Authentication**: Secure API endpoints with token-based auth
- **Concurrent Execution**: Slack bot and web server run simultaneously

## 5 Agent Roles

1. **Project Manager** - Creates project charter, identifies stakeholders, defines WBS
2. **Researcher & Analyst** - Conducts risk analysis, RACI matrix, feasibility study
3. **Report Creator** - Synthesizes findings into formal project documentation
4. **Critic & Reviewer** - Reviews for gaps, compliance, and improvement areas
5. **Scheduler** - Creates execution schedule, resource plan, Gantt chart, resourcing table

All agents reference ISO 21500:2021 concepts:
- 5 Process Groups: Initiating, Planning, Implementing, Controlling, Closing
- 10 Subject Groups: Integration, Stakeholders, Scope, Resources, Time, Cost, Risk, Quality, Procurement, Communication

## Setup

### Prerequisites

- Python 3.9+
- Slack workspace with bot app configured
- Anthropic API key
- Socket Mode enabled in Slack app

### Installation

1. Clone or download the project
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
```

4. Configure environment variables:

```env
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_APP_TOKEN=xapp-your-token

# Anthropic API
ANTHROPIC_API_KEY=sk-ant-your-key

# Security
JWT_SECRET=your-secret-key-change-in-production
PASSWORD_HASH=your-sha256-hash
```

### Generating PASSWORD_HASH

```bash
python3 -c "import hashlib; print(hashlib.sha256(b'your_password').hexdigest())"
```

### Slack Bot Setup

1. Create a Slack app at api.slack.com
2. Enable Socket Mode
3. Add bot scopes: `chat:write`, `app_mentions:read`, `messages:read`
4. Copy Bot Token and App Token to `.env`

## Running the Application

```bash
python app.py
```

This starts:
- **Slack Bot**: Connects via Socket Mode (background thread)
- **Web Server**: FastAPI running on `http://0.0.0.0:8000`

## API Endpoints

### POST /auth/verify
Authenticate and get JWT token

**Request:**
```json
{
  "password_hash": "sha256_hash_of_password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### POST /api/analyze
Analyze a project brief with 5-agent pipeline (streaming)

**Headers:**
```
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json
```

**Request:**
```json
{
  "brief": "Your project brief text here..."
}
```

**Response:** Server-Sent Events stream with NDJSON

Event format:
```
data: {"agent_id":"pm","type":"start"}
data: {"agent_id":"pm","type":"content_block","content":"text chunk"}
data: {"agent_id":"pm","type":"message_stop","is_final":false}
```

### GET /
Serves web UI (index.html)

### GET /health
Health check endpoint

## Slack Bot Usage

### Option 1: Message in #project-briefs

Post a message in the `#project-briefs` channel:

```
We need to build a new customer dashboard. Timeline: 3 months. Team: 4-5 people.
Priority: High. Key features: real-time data, custom reports, user authentication.
```

The bot will:
1. Analyze the brief
2. Run all 5 agents sequentially
3. Post each agent's response as a thread reply

### Option 2: @mention the bot

```
@ProjectTeamBot Please analyze this project: Build a mobile app for iOS and Android...
```

Same behavior - all 5 agents run and responses appear in thread.

## Web UI

Access the web interface at `http://localhost:8000`

1. Enter password to authenticate (get JWT token)
2. Paste project brief
3. Click "Analyze with 5-Agent Team"
4. Watch real-time streaming responses from all 5 agents
5. View complete analysis in the results section

## Architecture

```
┌─────────────────────────────────────────────────┐
│          Project Team Bot v2                    │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────────┐  ┌─────────────────────┐ │
│  │   Slack Bot      │  │   FastAPI Server    │ │
│  │  (Socket Mode)   │  │   (Streaming API)   │ │
│  └──────────────────┘  └─────────────────────┘ │
│         │                         │              │
│         │                         │              │
│  ┌──────────────────────────────────────────┐  │
│  │     5-Agent Pipeline (Sequential)        │  │
│  │                                          │  │
│  │  1. Project Manager → Charter            │  │
│  │  2. Researcher → Risk Analysis           │  │
│  │  3. Reporter → Documentation             │  │
│  │  4. Critic → Review & Gaps               │  │
│  │  5. Scheduler → Schedule & Resources     │  │
│  └──────────────────────────────────────────┘  │
│         │                                       │
│         ├─→ Slack Thread (bot)                  │
│         └─→ SSE Stream (web)                    │
└─────────────────────────────────────────────────┘
```

## Model Configuration

Currently uses `claude-sonnet-4-6` for all agents. To change:

Edit the `model` parameter in:
- `run_agent_pipeline()` function (Slack bot)
- `stream_agent_response()` function (Web API)

## Security Notes

1. **Password Hash**: Always use strong passwords
2. **JWT Secret**: Change `JWT_SECRET` in production
3. **Token Expiry**: Tokens expire after 24 hours
4. **HTTPS**: Deploy behind reverse proxy with HTTPS in production
5. **Environment Variables**: Never commit `.env` to version control

## Troubleshooting

### Slack bot not responding

Check:
- SLACK_BOT_TOKEN and SLACK_APP_TOKEN are correct
- Socket Mode is enabled in Slack app
- Bot has required scopes

View logs:
```bash
# Enable debug logging
export SLACK_SDK_ENABLE_SOCKET_MODE_DEBUG=1
python app.py
```

### API returns 401 Unauthorized

- Verify JWT token is valid (not expired)
- Check token is included in Authorization header
- Regenerate token with correct password

### Streaming response cuts off

- Check network connectivity
- Verify Anthropic API key is valid
- Check Claude API status

## Performance Considerations

- Each agent makes an API call to Claude
- Sequential execution: total time = sum of all agent times
- Typical analysis: 2-5 minutes for full pipeline
- Web server supports multiple concurrent requests

## Production Deployment

### Docker

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "app.py"]
```

### Environment

```bash
# Use production-grade secret
export JWT_SECRET=$(openssl rand -hex 32)

# Use strong password hash
export PASSWORD_HASH=$(python3 -c "import hashlib; print(hashlib.sha256(b'strong_password_here').hexdigest())")

# Deploy behind nginx/reverse proxy for HTTPS
```

### Scaling

For high-traffic scenarios:
- Use multiple worker processes (uvicorn --workers)
- Deploy Slack bot and API separately
- Use Redis for caching/state
- Implement rate limiting on /api/analyze

## Files

- `app.py` - Main application (Slack bot + FastAPI)
- `requirements.txt` - Python dependencies
- `static/index.html` - Web UI
- `.env.example` - Environment variable template
- `README.md` - This file

## License

Proprietary - ISO 21500:2021 Project Management

## Support

For issues or questions about ISO 21500:2021 concepts, consult:
- ISO 21500:2021 standard documentation
- Project Management Institute (PMI) resources
- Anthropic Claude documentation for streaming APIs

## Changelog

### v2.0.0
- Added 5-agent pipeline with sequential execution
- Implemented FastAPI with SSE streaming
- Added JWT authentication
- Created web UI for analysis
- Full ISO 21500:2021 compliance
- Slack bot now uses all 5 agents
- Added Scheduler agent with Gantt chart and resourcing table

### v1.0.0
- Initial release (single-agent)
