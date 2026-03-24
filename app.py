#!/usr/bin/env python3
"""
Project Team Bot v2 - Slack Bot + FastAPI Web Server
Combines Slack integration with streaming web API, featuring 5 specialized agents.
Implements ISO 21500:2021 project management standards.
"""

import os
import json
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Generator, AsyncGenerator
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from anthropic import Anthropic
from fastapi.security import HTTPBearer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
PASSWORD = "PM888"  # Shared team password

# Validation
if not all([SLACK_BOT_TOKEN, SLACK_APP_TOKEN, ANTHROPIC_API_KEY]):
    logger.warning(
        "Missing required Slack/Anthropic environment variables. "
        "Slack bot will not function without them."
    )

# ============================================================================
# AGENT SYSTEM PROMPTS - ISO 21500:2021 COMPLIANT
# ============================================================================

AGENT_PROMPTS = {
    "pm": """You are an expert Project Manager specializing in ISO 21500:2021 project management.
Your role is to analyze project requirements and create a comprehensive project charter.

CONTEXT: You are part of a 5-agent team analyzing project briefs in sequence.
You work FIRST, establishing the foundation for other agents.

RESPONSIBILITIES:
1. Extract and clarify project scope, objectives, and success criteria
2. Identify stakeholders and create a Stakeholder Register
3. Define the 5 Process Groups: Initiating, Planning, Implementing, Controlling, Closing
4. Reference the 10 Subject Groups: Integration, Stakeholders, Scope, Resources, Time, Cost, Risk, Quality, Procurement, Communication
5. Create a high-level Work Breakdown Structure (WBS)
6. Identify constraints, assumptions, and dependencies

OUTPUT FORMAT:
- Start with "PROJECT CHARTER" heading
- Include stakeholder analysis
- Define scope boundaries (in-scope, out-of-scope)
- List success criteria
- Map to relevant Process Groups and Subject Groups

Be concise but thorough. Your analysis will feed into the Researcher's deeper analysis.""",

    "researcher": """You are an expert Researcher and Analyst specializing in ISO 21500:2021 project management.
Your role is to conduct detailed analysis based on the Project Manager's charter.

CONTEXT: You are the SECOND agent in a 5-agent team.
The Project Manager has already created a charter (see previous analysis).
You build upon their foundation with deeper research and risk analysis.

RESPONSIBILITIES:
1. Analyze project risks and create a Risk Register
2. Identify resource requirements and constraints
3. Evaluate technical and organizational feasibility
4. Research best practices and applicable standards
5. Document assumptions and dependencies
6. Create RACI matrix for key stakeholders
7. Identify gaps in the project definition

OUTPUT FORMAT:
- Start with "RESEARCH & ANALYSIS" heading
- Include Risk Register (probability, impact, mitigation)
- Document resource constraints
- RACI matrix for key roles
- Feasibility assessment
- Reference specific ISO 21500 concepts

Build upon the PM's charter. Keep the Researcher's analysis focused on investigation and risk.""",

    "reporter": """You are an expert Report Creator specializing in ISO 21500:2021 documentation.
Your role is to synthesize findings from PM and Researcher into a comprehensive project document.

CONTEXT: You are the THIRD agent in a 5-agent team.
The PM and Researcher have provided charter and analysis (see previous work).
You create the formal project documentation.

RESPONSIBILITIES:
1. Synthesize PM's charter and Researcher's analysis
2. Create detailed project plan document
3. Document communication plan
4. Define quality standards and acceptance criteria
5. Create procurement strategy if needed
6. Document all process groups and subject groups coverage
7. Create executive summary

OUTPUT FORMAT:
- Start with "PROJECT PLAN REPORT" heading
- Executive summary (1-2 paragraphs)
- Detailed sections for each Subject Group
- Quality and acceptance criteria
- Communication and escalation plan
- Resource plan summary
- Risk response strategies

Reference previous findings from PM and Researcher. Create a professional, stakeholder-ready document.""",

    "critic": """You are an expert Critic and Reviewer specializing in ISO 21500:2021 project management.
Your role is to critically review all previous work and identify gaps or issues.

CONTEXT: You are the FOURTH agent in a 5-agent team.
The PM, Researcher, and Reporter have submitted their work (see previous analysis).
You provide constructive criticism and identify improvement areas.

RESPONSIBILITIES:
1. Review alignment with ISO 21500:2021 requirements
2. Identify gaps in coverage of 5 Process Groups
3. Identify gaps in coverage of 10 Subject Groups
4. Challenge assumptions and identify risks in the analysis
5. Verify completeness of RACI matrix, Risk Register, WBS
6. Suggest improvements to the project plan
7. Flag potential compliance or feasibility issues

OUTPUT FORMAT:
- Start with "CRITICAL REVIEW" heading
- Strengths of the project plan
- Gaps identified (by Process Group and Subject Group)
- Risks not adequately addressed
- Recommended improvements
- Compliance with ISO 21500:2021
- Open questions or concerns

Be constructive but thorough. Identify real issues that need addressing.""",

    "scheduler": """You are an expert Scheduler specializing in resource planning and scheduling in ISO 21500:2021.
Your role is to create a detailed schedule and resource plan for project execution.

CONTEXT: You are the FIFTH and final agent in a 5-agent team.
The PM, Researcher, Reporter, and Critic have provided their analysis (see previous work).
You create the execution schedule and resource plan based on all previous findings.

RESPONSIBILITIES:
1. Create detailed project schedule with phases and milestones
2. Estimate duration for each phase (Initiating, Planning, Implementing, Controlling, Closing)
3. Estimate resources needed: people, hours, skills required
4. Create weekly resourcing plan with resource allocation
5. Identify resource constraints and dependencies
6. Create text-based Gantt chart showing timeline
7. Create resourcing table showing weekly allocation

OUTPUT FORMAT:
- Start with "EXECUTION SCHEDULE & RESOURCING PLAN" heading
- Project timeline overview
- Phase-by-phase breakdown with duration estimates
- TEXT-BASED GANTT CHART (ASCII art timeline)
- RESOURCING TABLE with weekly allocation:
  | Week | Role | Hours | FTE | Task |
  |------|------|-------|-----|------|
  | 1-2  | PM   | 40    | 1.0 | Project Initiation |
  etc.
- Critical path analysis
- Resource constraints and mitigation
- Schedule risks

Always include both the Gantt chart and resourcing table in ASCII format.
Reference the PM, Researcher, Reporter, and Critic's work to inform scheduling.""",
}

# ============================================================================
# SLACK BOT SETUP (Optional - only if valid tokens provided)
# ============================================================================

# Only initialize Slack bot if we have valid tokens (not placeholders)
slack_app = None
if SLACK_BOT_TOKEN and not SLACK_BOT_TOKEN.startswith("xoxb-placeholder"):
    try:
        slack_app = App(token=SLACK_BOT_TOKEN)
    except Exception as e:
        logger.warning(f"Failed to initialize Slack bot: {e}. Continuing with web-only mode.")


# Only register Slack handlers if bot is initialized
if slack_app:
    @slack_app.message("project-briefs")
    def handle_project_brief(message, say, logger):
        """Handle messages in #project-briefs channel using 5-agent pipeline."""
        try:
            brief_text = message.get("text", "")
            if not brief_text:
                return

            # Post initial message indicating processing
            result = say("🤖 Analyzing project brief with 5-agent team...\n_(This may take a moment)_")
            thread_ts = result["ts"]

            # Run 5-agent pipeline synchronously
            run_agent_pipeline(brief_text, say, thread_ts)

        except Exception as e:
            logger.error(f"Error handling project brief: {e}")
            say(f"❌ Error processing brief: {str(e)}")


    @slack_app.message()
    def handle_mention(message, say, logger):
        """Handle @mentions to the bot in any channel."""
        user_id = slack_app.client.auth_test()["user_id"]
        if f"<@{user_id}>" not in message.get("text", ""):
            return

        try:
            text = message.get("text", "").replace(f"<@{user_id}>", "").strip()

            if not text:
                say("Hi! Send me a project brief to analyze with our 5-agent team.")
                return

            # Post initial message
            result = say("🤖 Analyzing with project team...\n_(This may take a moment)_")
            thread_ts = result["ts"]

            # Run 5-agent pipeline
            run_agent_pipeline(text, say, thread_ts)

        except Exception as e:
            logger.error(f"Error handling mention: {e}")
            say(f"❌ Error: {str(e)}")


def run_agent_pipeline(brief: str, say, thread_ts: str):
    """Execute 5-agent pipeline sequentially, streaming responses to Slack thread."""
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    conversation_history = []

    agents = ["pm", "researcher", "reporter", "critic", "scheduler"]
    agent_names = {
        "pm": "Project Manager",
        "researcher": "Researcher & Analyst",
        "reporter": "Report Creator",
        "critic": "Critic & Reviewer",
        "scheduler": "Scheduler",
    }

    for agent_id in agents:
        logger.info(f"Running agent: {agent_id}")

        # Build user message for this agent
        if agent_id == "pm":
            user_msg = f"Please analyze this project brief:\n\n{brief}"
        else:
            user_msg = f"Please continue the analysis based on all previous findings."

        # Add to conversation history
        conversation_history.append({
            "role": "user",
            "content": user_msg
        })

        # Call Claude with streaming
        response_text = ""
        try:
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=AGENT_PROMPTS[agent_id],
                messages=conversation_history
            ) as stream:
                for text in stream.text_stream:
                    response_text += text

        except Exception as e:
            logger.error(f"Error calling Claude for agent {agent_id}: {e}")
            response_text = f"Error: {str(e)}"

        # Add assistant response to history
        conversation_history.append({
            "role": "assistant",
            "content": response_text
        })

        # Post to Slack as thread reply
        agent_name = agent_names[agent_id]
        formatted_response = f"*{agent_name}*\n\n{response_text}"

        try:
            say(formatted_response, thread_ts=thread_ts)
        except Exception as e:
            logger.error(f"Error posting to Slack: {e}")

        logger.info(f"Agent {agent_id} completed")


# ============================================================================
# FASTAPI WEB SERVER
# ============================================================================

web_app = FastAPI(title="Project Team Bot API", version="2.0.0")

# Security
security = HTTPBearer()


def verify_auth_token(credentials: HTTPAuthCredentials = Depends(security)) -> dict:
    """Verify authentication token from Authorization header."""
    token = credentials.credentials
    # Simple token validation - just check if it looks like a valid session token
    if not token or not token.startswith('session_token_'):
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"token": token}


@web_app.post("/auth/verify")
async def verify_password(request_data: dict):
    """Verify password and return access token.

    Expected request body:
    {
        "password": "PM888"
    }
    """
    provided_password = request_data.get("password", "")

    # Verify password matches
    if provided_password != PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")

    # Return simple token (just use the password as token for simplicity)
    return {
        "access_token": "session_token_" + str(datetime.utcnow().timestamp()),
        "token_type": "bearer",
        "expires_in": 86400
    }


async def stream_agent_response(
    brief: str,
    agent_id: str,
    conversation_history: list,
) -> AsyncGenerator[str, None]:
    """Stream response from a single agent using async generator."""
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    # Determine user message
    if agent_id == "pm":
        user_msg = f"Please analyze this project brief:\n\n{brief}"
    else:
        user_msg = f"Please continue the analysis based on all previous findings."

    # Add user message to history
    conversation_history.append({
        "role": "user",
        "content": user_msg
    })

    # Stream start event
    yield f"data: {json.dumps({'agent_id': agent_id, 'type': 'start'})}\n\n"

    response_text = ""
    try:
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=AGENT_PROMPTS[agent_id],
            messages=conversation_history
        ) as stream:
            for text in stream.text_stream:
                response_text += text
                # Stream content blocks
                yield f"data: {json.dumps({'agent_id': agent_id, 'type': 'content_block', 'content': text})}\n\n"

    except Exception as e:
        logger.error(f"Error streaming agent {agent_id}: {e}")
        yield f"data: {json.dumps({'agent_id': agent_id, 'type': 'error', 'error': str(e)})}\n\n"

    # Add response to history
    conversation_history.append({
        "role": "assistant",
        "content": response_text
    })

    # Stream completion event
    yield f"data: {json.dumps({'agent_id': agent_id, 'type': 'message_stop', 'is_final': agent_id == 'scheduler'})}\n\n"


async def run_agent_pipeline_async(brief: str) -> AsyncGenerator[str, None]:
    """Run 5-agent pipeline with async streaming."""
    agents = ["pm", "researcher", "reporter", "critic", "scheduler"]
    conversation_history = []

    for agent_id in agents:
        logger.info(f"Streaming agent: {agent_id}")
        async for event in stream_agent_response(brief, agent_id, conversation_history):
            yield event


@web_app.post("/api/analyze")
async def analyze_brief(
    request_data: dict,
    _: dict = Depends(verify_auth_token)
) -> StreamingResponse:
    """Analyze a project brief using 5-agent pipeline with streaming.

    Expected request body:
    {
        "brief": "Your project brief text here"
    }

    Returns: Server-Sent Events stream with NDJSON events
    """
    brief = request_data.get("brief", "").strip()

    if not brief:
        raise HTTPException(status_code=400, detail="brief is required")

    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY not configured"
        )

    return StreamingResponse(
        run_agent_pipeline_async(brief),
        media_type="text/event-stream"
    )


@web_app.get("/")
async def serve_index():
    """Serve index.html from static files directory."""
    from fastapi.responses import FileResponse

    index_path = os.path.join(
        os.path.dirname(__file__),
        "static",
        "index.html"
    )

    if os.path.exists(index_path):
        return FileResponse(index_path)

    return {
        "message": "Project Team Bot API v2.0",
        "endpoints": {
            "auth": "POST /auth/verify",
            "analyze": "POST /api/analyze",
            "docs": "/docs"
        }
    }


@web_app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# BACKGROUND THREAD SETUP
# ============================================================================

def run_socket_mode():
    """Run Slack Socket Mode in background thread."""
    if not slack_app:
        logger.info("Slack bot not initialized. Running in web-only mode.")
        return

    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        logger.warning("Slack credentials not configured. Slack bot disabled.")
        return

    handler = SocketModeHandler(slack_app, SLACK_APP_TOKEN)
    logger.info("Starting Slack Socket Mode handler...")
    handler.start()


def run_web_server():
    """Run FastAPI web server."""
    logger.info("Starting FastAPI web server on http://0.0.0.0:8000")
    uvicorn.run(
        web_app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Start Slack bot in background thread
    slack_thread = threading.Thread(target=run_socket_mode, daemon=True)
    slack_thread.start()
    logger.info("Slack bot thread started")

    # Start web server in main thread
    run_web_server()
