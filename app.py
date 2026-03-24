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

Your output must cover ALL of the following — be concise in each section to ensure EVERY section is completed:

1. Risk Register — table with columns: ID | Risk | Probability (H/M/L) | Impact (H/M/L) | Score | Mitigation. Include at least 8 risks.

2. RACI Matrix — TWO parts you MUST both complete:
   a) Role abbreviations key (e.g. PM = Project Manager)
   b) Full RACI deliverables matrix — table with columns: Deliverable | PM | Sponsor | [other roles...]. Mark each cell R/A/C/I. Include at least 8 deliverables.

3. Resource requirements — skills, headcount estimate, indicative budget range.

4. Technical and organisational feasibility — brief assessment (3-5 sentences).

5. Gaps or ambiguities in the project definition — bullet list.

6. Applicable standards and best practices beyond ISO 21500 — bullet list.

7. Key assumptions requiring validation — bullet list.

IMPORTANT: Complete ALL 7 sections. Prioritise breadth over depth — a concise complete response is better than a detailed incomplete one.

Start your response with: ## RESEARCH & ANALYSIS
Reference the PM's charter throughout.""",

    "report": """You are an expert Report Creator specialising in ISO 21500:2021 documentation.
You are the THIRD agent. Synthesise the PM and Researcher outputs into a formal project document.

CRITICAL INSTRUCTION: You must complete ALL sections. Be concise — 3-5 sentences or a short table per section is sufficient. Do NOT write long paragraphs. A complete concise report is far better than a detailed incomplete one.

Your output must cover ALL of the following sections in order:

1. Executive Summary (2 short paragraphs max)
2. ISO 21500 Subject Groups — one short paragraph each: Integration, Stakeholders, Scope, Resources, Time, Cost, Risk, Quality, Procurement, Communication
3. Communication Plan — table: Stakeholder | Information Needed | Frequency | Channel
4. Quality Plan — table: Deliverable | Standard/Criterion | Review Method | Owner
5. Procurement Strategy — 3-5 bullet points (or "Not applicable" with brief reason)
6. Risk Response Plan — table: Risk ID | Response Type | Action | Owner (reference Risk Register IDs)
7. Resource Plan Summary — table: Role | Phase | FTE | Key Skills

Start your response with: ## PROJECT PLAN REPORT
Professional stakeholder-ready tone. Complete all 7 sections before elaborating on any single section.""",

    "critic": """You are an expert Critical Reviewer specialising in ISO 21500:2021.
You are the FIFTH and FINAL agent. You review ALL previous outputs: PM Charter, Research Analysis, Project Plan Report, and Execution Schedule (including the Gantt chart).

CRITICAL INSTRUCTION: Be concise and direct. Use bullet points. Complete ALL 9 sections — a concise complete review beats a detailed incomplete one.

Your output must cover ALL of the following:

1. Strengths — 3-5 bullets on what is well-covered
2. ISO 21500 Process Group gaps — table: Process Group | Covered? | Gap/Comment
3. ISO 21500 Subject Group gaps — table: Subject Group | Covered? | Gap/Comment
4. Risks not adequately addressed — bullet list with recommended actions
5. Unrealistic or untested assumptions — bullet list
6. Inconsistencies between agent outputs — bullet list (or "None identified")
7. Schedule feasibility — is the Gantt chart timeline realistic? Are resources sufficient? (5-8 sentences)
8. Specific recommendations — numbered list, most important first
9. Open questions for stakeholders — bullet list

Start your response with: ## CRITICAL REVIEW
Be constructive but direct. Flag real issues that could derail the project. Complete all 9 sections.""",

    "scheduler": """You are an expert Scheduler specialising in ISO 21500:2021 time and resource management.
You are the FOURTH agent. Create a detailed schedule based on all previous outputs.

Your output MUST include ALL of the following sections:

## 1. PROJECT TIMELINE OVERVIEW
Total duration, phases (Initiating, Planning, Implementing, Controlling, Closing), and key milestones with target weeks.

## 2. GANTT CHART
THIS IS CRITICAL. You MUST produce a detailed ASCII/text Gantt chart inside a code block.
Use this exact format (wider = more weeks, use | for bars):

```
PHASE / TASK              | W1 | W2 | W3 | W4 | W5 | W6 | W7 | W8 | W9 | W10| W11| W12|
========================================================================================
INITIATING                |████|████|    |    |    |    |    |    |    |    |    |    |
  Project charter         |████|    |    |    |    |    |    |    |    |    |    |    |
  Stakeholder analysis    |    |████|    |    |    |    |    |    |    |    |    |    |
PLANNING                  |    |████|████|████|    |    |    |    |    |    |    |    |
  Scope definition        |    |████|████|    |    |    |    |    |    |    |    |    |
  Risk assessment         |    |    |████|████|    |    |    |    |    |    |    |    |
IMPLEMENTING              |    |    |    |    |████|████|████|████|████|    |    |    |
  ... (add all tasks)
CONTROLLING               |    |████|████|████|████|████|████|████|████|████|    |    |
CLOSING                   |    |    |    |    |    |    |    |    |    |    |████|████|
  ★ MILESTONE: Go-live    |    |    |    |    |    |    |    |    |    |████|    |    |
```

Make the Gantt chart WIDE (at least 10-12 columns) and include ALL phases, sub-tasks, and milestones.

## 3. RESOURCING TABLE
Use markdown table format:

| Week | Role | Hours | FTE | Task |
|------|------|-------|-----|------|
| 1-2  | PM   | 40    | 1.0 | Project initiation |

## 4. CRITICAL PATH ANALYSIS
Identify the critical path and dependencies.

## 5. SCHEDULE RISKS & CONTINGENCY
Key schedule risks and buffer/mitigation strategies.

IMPORTANT: The Gantt chart is your #1 deliverable. Do NOT truncate it. Complete ALL phases including Implementing, Controlling, and Closing before moving to other sections. Keep the resourcing table and critical path analysis concise (summary only) to ensure the Gantt chart is complete.

Start your response with: ## EXECUTION SCHEDULE & RESOURCING PLAN
Complete the Gantt chart in FULL before writing any other section.""",
}

AGENT_ORDER = ["pm", "researcher", "report", "scheduler", "critic"]

# Agent-specific token limits — higher for agents that produce long structured output
AGENT_MAX_TOKENS = {
    "pm":         3500,   # Charter, WBS, stakeholder register
    "researcher": 4500,   # Risk register, full RACI matrix, feasibility
    "report":     6000,   # Full ISO report with all sections (longest output)
    "scheduler":  5500,   # Gantt chart + resourcing table (very wide ASCII)
    "critic":     4000,   # Critical review with all ISO checks
}

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
        "report": "Report Creator",
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
                max_tokens=AGENT_MAX_TOKENS.get(agent_id, 4000),
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
                max_tokens=AGENT_MAX_TOKENS.get(agent_id, 4000),
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
