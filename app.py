#!/usr/bin/env python3
"""
Virtual Project Team v2 - FastAPI Web Server
5-agent AI pipeline with real-time streaming and ISO 21500:2021 compliance.
Slack integration is optional - runs as web-only if tokens are placeholders.
"""

import os
import json
import threading
import logging
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
from anthropic import Anthropic

# Slack imports - optional
try:
    from slack_bolt import App as SlackApp
    from slack_bolt.adapter.socket_mode import SocketModeHandler
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PASSWORD = "PM888"

def is_valid_slack_token(token: str, prefix: str) -> bool:
    """Check if a Slack token looks real (not a placeholder)."""
    return (
        token
        and token.startswith(prefix)
        and len(token) > 20
        and "placeholder" not in token.lower()
        and "dummy" not in token.lower()
    )

SLACK_ENABLED = (
    SLACK_AVAILABLE
    and is_valid_slack_token(SLACK_BOT_TOKEN, "xoxb-")
    and is_valid_slack_token(SLACK_APP_TOKEN, "xapp-")
)

if not ANTHROPIC_API_KEY:
    logger.warning("ANTHROPIC_API_KEY not set - analysis will fail")

if SLACK_ENABLED:
    logger.info("Slack integration enabled")
else:
    logger.info("Running in web-only mode (no Slack tokens)")

# ============================================================================
# AGENT PROMPTS - ISO 21500:2021 COMPLIANT
# ============================================================================

AGENT_PROMPTS = {
    "pm": """You are an expert Project Manager specialising in ISO 21500:2021.
Analyse the project brief and produce a comprehensive PROJECT CHARTER.

Your output must cover:
1. Project objectives and success criteria
2. Stakeholder Register (name, role, interest, influence)
3. Scope definition - in scope and out of scope
4. High-level Work Breakdown Structure (WBS)
5. Constraints, assumptions and dependencies
6. Mapping to ISO 21500 Process Groups: Initiating, Planning, Implementing, Controlling, Closing
7. Mapping to ISO 21500 Subject Groups: Integration, Stakeholders, Scope, Resources, Time, Cost, Risk, Quality, Procurement, Communication

Start your response with: ## PROJECT CHARTER
Be thorough - your output feeds into the Researcher, Reporter, Critic and Scheduler.""",

    "researcher": """You are an expert Research Analyst specialising in ISO 21500:2021.
You are the SECOND agent. Build on the Project Manager's charter with deeper research.

Your output must cover:
1. Risk Register with probability, impact, score and mitigation for each risk
2. RACI matrix for key roles and deliverables
3. Resource requirements - skills, headcount, budget estimate
4. Technical and organisational feasibility assessment
5. Gaps or ambiguities in the project definition
6. Best practices and applicable standards beyond ISO 21500
7. Assumptions that need validation

Start your response with: ## RESEARCH & ANALYSIS
Reference the PM's charter throughout.""",

    "reporter": """You are an expert Report Creator specialising in ISO 21500:2021 documentation.
You are the THIRD agent. Synthesise the PM and Researcher outputs into a formal project document.

Your output must cover:
1. Executive Summary (2-3 paragraphs)
2. Detailed section for each ISO 21500 Subject Group
3. Communication Plan - who, what, when, how
4. Quality Plan - standards, acceptance criteria, review process
5. Procurement strategy (if applicable)
6. Risk Response Plan referencing the Risk Register
7. Resource Plan summary

Start your response with: ## PROJECT PLAN REPORT
This is a stakeholder-ready document - professional tone throughout.""",

    "critic": """You are an expert Critical Reviewer specialising in ISO 21500:2021.
You are the FOURTH agent. Critically review all previous outputs.

Your output must cover:
1. Strengths of the project plan
2. Gaps in ISO 21500 Process Group coverage
3. Gaps in ISO 21500 Subject Group coverage
4. Risks not adequately addressed
5. Assumptions that are unrealistic or untested
6. Inconsistencies between PM, Researcher and Reporter outputs
7. Specific recommendations to improve the plan
8. Open questions requiring stakeholder input

Start your response with: ## CRITICAL REVIEW
Be constructive but direct - flag real issues that could derail the project.""",

    "scheduler": """You are an expert Scheduler specialising in ISO 21500:2021 time and resource management.
You are the FIFTH and final agent. Create a detailed schedule based on all previous outputs.

Your output must include:
1. Project timeline overview with total duration
2. Phase breakdown: Initiating, Planning, Implementing, Controlling, Closing
3. Key milestones with target dates (use relative weeks, e.g. Week 1, Week 4)
4. TEXT-BASED GANTT CHART using ASCII characters showing all phases and milestones
5. RESOURCING TABLE in this exact format:

| Week | Role | Hours | FTE | Task |
|------|------|-------|-----|------|
| 1-2  | PM   | 40    | 1.0 | Project initiation |

6. Critical path analysis
7. Resource constraints and mitigation
8. Schedule risks and contingency

Start your response with: ## EXECUTION SCHEDULE & RESOURCING PLAN
Always include BOTH the Gantt chart and the resourcing table.""",
}

AGENT_ORDER = ["pm", "researcher", "reporter", "critic", "scheduler"]

# ============================================================================
# SLACK BOT (optional)
# ============================================================================

slack_app = None

if SLACK_ENABLED:
    try:
        slack_app = SlackApp(token=SLACK_BOT_TOKEN)
        logger.info("Slack App initialised successfully")

        @slack_app.event("app_mention")
        def handle_mention(event, say):
            text = event.get("text", "")
            # Strip the @mention
            import re
            clean = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
            if not clean:
                say("Hi! Mention me with a project brief to analyse.")
                return
            result = say("🤖 Analysing your project with the 5-agent team...")
            _run_slack_pipeline(clean, say, result["ts"])

        @slack_app.message("project brief")
        def handle_project_brief(message, say):
            text = message.get("text", "")
            result = say("🤖 Analysing your project with the 5-agent team...")
            _run_slack_pipeline(text, say, result["ts"])

    except Exception as e:
        logger.warning(f"Slack init failed: {e} — running web-only")
        slack_app = None
        SLACK_ENABLED = False


def _run_slack_pipeline(brief: str, say, thread_ts: str):
    """Run 5-agent pipeline and post results to Slack thread."""
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    history = []
    names = {
        "pm": "Project Manager",
        "researcher": "Research Analyst",
        "reporter": "Report Creator",
        "critic": "Critical Reviewer",
        "scheduler": "Schedule Optimizer",
    }

    for agent_id in AGENT_ORDER:
        user_msg = (
            f"Please analyse this project brief:\n\n{brief}"
            if agent_id == "pm"
            else "Please continue the analysis based on all previous findings."
        )
        history.append({"role": "user", "content": user_msg})
        response_text = ""

        try:
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=3000,
                system=AGENT_PROMPTS[agent_id],
                messages=history,
            ) as stream:
                for chunk in stream.text_stream:
                    response_text += chunk
        except Exception as e:
            response_text = f"Error: {e}"

        history.append({"role": "assistant", "content": response_text})

        try:
            say(f"*{names[agent_id]}*\n\n{response_text}", thread_ts=thread_ts)
        except Exception as e:
            logger.error(f"Slack post error for {agent_id}: {e}")


# ============================================================================
# FASTAPI WEB APP
# ============================================================================

web_app = FastAPI(title="Virtual Project Team", version="2.0.0")
security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify session token from Authorization header."""
    token = credentials.credentials
    if not token or not token.startswith("session_token_"):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"token": token}


@web_app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@web_app.get("/")
async def serve_root():
    """Serve the main web app HTML file."""
    # Look for index.html alongside app.py (root of repo)
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in ["index.html", "static/index.html"]:
        path = os.path.join(here, candidate)
        if os.path.exists(path):
            logger.info(f"Serving {path}")
            return FileResponse(path, media_type="text/html")

    # Fallback - shouldn't happen in production
    return {
        "message": "Virtual Project Team API v2.0",
        "note": "index.html not found - check deployment",
        "endpoints": {"auth": "POST /auth/verify", "analyze": "POST /api/analyze"},
    }


@web_app.post("/auth/verify")
async def verify_password(body: dict):
    """Verify shared password and return session token."""
    provided = body.get("password", "")
    if provided != PASSWORD:
        raise HTTPException(status_code=401, detail="Incorrect password")
    token = f"session_token_{datetime.utcnow().timestamp()}"
    return {"access_token": token, "token_type": "bearer"}


async def _stream_pipeline(brief: str) -> AsyncGenerator[str, None]:
    """Stream 5-agent pipeline as NDJSON lines."""
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    history = []

    for agent_id in AGENT_ORDER:
        # Signal agent starting
        yield json.dumps({"agent": agent_id, "status": "speaking"}) + "\n"

        user_msg = (
            f"Please analyse this project brief:\n\n{brief}"
            if agent_id == "pm"
            else "Please continue the analysis based on all previous findings."
        )
        history.append({"role": "user", "content": user_msg})
        response_text = ""

        try:
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=3000,
                system=AGENT_PROMPTS[agent_id],
                messages=history,
            ) as stream:
                for chunk in stream.text_stream:
                    response_text += chunk
                    yield json.dumps({"agent": agent_id, "content": chunk}) + "\n"

        except Exception as e:
            logger.error(f"Stream error for {agent_id}: {e}")
            yield json.dumps({"agent": agent_id, "content": f"\n\n[Error: {e}]"}) + "\n"

        history.append({"role": "assistant", "content": response_text})

        # Signal agent complete
        yield json.dumps({"agent": agent_id, "status": "complete"}) + "\n"


@web_app.post("/api/analyze")
async def analyze(
    body: dict,
    _: dict = Depends(verify_token),
) -> StreamingResponse:
    """Run 5-agent analysis and stream results as NDJSON."""
    brief = body.get("brief", "").strip()
    if not brief:
        raise HTTPException(status_code=400, detail="brief is required")
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    return StreamingResponse(
        _stream_pipeline(brief),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no"},  # Disable Nginx buffering for streaming
    )


# ============================================================================
# SLACK SOCKET MODE (background thread)
# ============================================================================

def _run_slack_socket_mode():
    """Start Slack socket mode in background thread."""
    if not slack_app:
        logger.info("Slack not configured - skipping socket mode")
        return
    try:
        handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
        logger.info("Starting Slack socket mode...")
        handler.start()
    except Exception as e:
        logger.error(f"Slack socket mode error: {e}")


# ============================================================================
# ENTRY POINT (used when running python app.py directly)
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))

    if SLACK_ENABLED and slack_app:
        t = threading.Thread(target=_run_slack_socket_mode, daemon=True)
        t.start()

    logger.info(f"Starting web server on port {port}")
    uvicorn.run(web_app, host="0.0.0.0", port=port, log_level="info")
