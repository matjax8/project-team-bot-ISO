#!/usr/bin/env python3
"""
Configuration module for Project Team Bot v2
Centralizes all configurable settings
"""

import os
from typing import Dict, List

# ============================================================================
# MODEL CONFIGURATION
# ============================================================================

# Claude model to use for all agents
LLM_MODEL = "claude-sonnet-4-6"

# Maximum tokens per agent response
MAX_TOKENS = 2000

# Temperature for model responses (0.0 = deterministic, 1.0 = creative)
TEMPERATURE = 0.7

# ============================================================================
# API CONFIGURATION
# ============================================================================

# FastAPI server settings
API_HOST = "0.0.0.0"
API_PORT = int(os.getenv("API_PORT", 8000))
API_WORKERS = int(os.getenv("API_WORKERS", 1))
API_LOG_LEVEL = os.getenv("API_LOG_LEVEL", "info")

# Enable CORS for web UI
ENABLE_CORS = os.getenv("ENABLE_CORS", "false").lower() == "true"

# ============================================================================
# SLACK CONFIGURATION
# ============================================================================

# Slack bot tokens
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

# Slack channel configuration
SLACK_CHANNELS_TO_MONITOR = {
    "project-briefs": "Dedicated project brief analysis channel",
    "general": "Optional: also monitor general channel"
}

# Mention patterns the bot responds to
SLACK_BOT_NAME = "ProjectTeamBot"

# Thread timeout (seconds) before bot gives up waiting for message
SLACK_MESSAGE_TIMEOUT = 300

# ============================================================================
# ANTHROPIC CONFIGURATION
# ============================================================================

# Anthropic API key
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Request timeout in seconds
ANTHROPIC_TIMEOUT = 60

# Retry configuration
ANTHROPIC_MAX_RETRIES = 3
ANTHROPIC_RETRY_DELAY = 1  # seconds

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# Password authentication
PASSWORD_HASH = os.getenv("PASSWORD_HASH")

# Rate limiting
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 3600  # seconds (1 hour)

# CORS allowed origins
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# ============================================================================
# AGENT CONFIGURATION
# ============================================================================

# Agent execution order (must be in sequence)
AGENT_EXECUTION_ORDER = [
    "pm",
    "researcher",
    "reporter",
    "critic",
    "scheduler"
]

# Agent display names
AGENT_DISPLAY_NAMES = {
    "pm": "Project Manager",
    "researcher": "Researcher & Analyst",
    "reporter": "Report Creator",
    "critic": "Critic & Reviewer",
    "scheduler": "Scheduler",
}

# Agent descriptions
AGENT_DESCRIPTIONS = {
    "pm": "Creates project charter, identifies stakeholders, defines work breakdown structure",
    "researcher": "Analyzes risks, feasibility, and creates RACI matrix",
    "reporter": "Synthesizes findings into formal project documentation",
    "critic": "Critically reviews for gaps and ISO 21500 compliance",
    "scheduler": "Creates execution schedule and resource allocation plan",
}

# ============================================================================
# ISO 21500 CONFIGURATION
# ============================================================================

# 5 Process Groups defined in ISO 21500:2021
ISO_PROCESS_GROUPS = [
    "Initiating",
    "Planning",
    "Implementing",
    "Controlling",
    "Closing"
]

# 10 Subject Groups defined in ISO 21500:2021
ISO_SUBJECT_GROUPS = [
    "Integration",
    "Stakeholders",
    "Scope",
    "Resources",
    "Time",
    "Cost",
    "Risk",
    "Quality",
    "Procurement",
    "Communication"
]

# Key ISO 21500 artifacts each agent should reference
ISO_ARTIFACTS = {
    "pm": [
        "Project Charter",
        "Stakeholder Register",
        "Work Breakdown Structure",
        "Project Constraints and Assumptions"
    ],
    "researcher": [
        "Risk Register",
        "RACI Matrix",
        "Resource Requirements",
        "Feasibility Assessment"
    ],
    "reporter": [
        "Project Plan",
        "Quality Criteria",
        "Communication Plan",
        "Resource Plan"
    ],
    "critic": [
        "Gap Analysis",
        "Compliance Checklist",
        "Improvement Recommendations",
        "Open Issues Log"
    ],
    "scheduler": [
        "Project Schedule",
        "Resource Plan",
        "Gantt Chart",
        "Critical Path Analysis"
    ]
}

# ============================================================================
# STREAMING CONFIGURATION
# ============================================================================

# SSE streaming buffer size
STREAM_BUFFER_SIZE = 1024

# Heartbeat interval for SSE (seconds)
SSE_HEARTBEAT_INTERVAL = 30

# Maximum concurrent streams
MAX_CONCURRENT_STREAMS = 10

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = os.getenv("LOG_FILE", "logs/bot.log")

# Create logs directory if it doesn't exist
LOG_DIR = os.path.dirname(LOG_FILE)
if LOG_DIR and not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

# ============================================================================
# DATABASE CONFIGURATION (if needed for future enhancement)
# ============================================================================

# Database URL (optional - for storing analysis history)
DATABASE_URL = os.getenv("DATABASE_URL")

# Enable analysis caching
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "false").lower() == "true"
CACHE_TTL_HOURS = 24

# ============================================================================
# FEATURE FLAGS
# ============================================================================

# Enable Slack bot integration
ENABLE_SLACK_BOT = bool(SLACK_BOT_TOKEN and SLACK_APP_TOKEN)

# Enable web API
ENABLE_WEB_API = True

# Enable async mode (recommended for production)
ENABLE_ASYNC = True

# Enable metrics/monitoring
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "false").lower() == "true"

# ============================================================================
# OUTPUT CONFIGURATION
# ============================================================================

# Format for agent outputs
OUTPUT_FORMAT = "markdown"  # or "plain_text", "json"

# Include ISO 21500 references in output
INCLUDE_ISO_REFERENCES = True

# Include process group mapping in output
INCLUDE_PROCESS_GROUPS = True

# Include subject group mapping in output
INCLUDE_SUBJECT_GROUPS = True

# ============================================================================
# VALIDATION
# ============================================================================

def validate_config() -> bool:
    """Validate critical configuration values."""
    errors = []

    if not ANTHROPIC_API_KEY:
        errors.append("ANTHROPIC_API_KEY not set")

    if not PASSWORD_HASH:
        errors.append("PASSWORD_HASH not set")

    if not JWT_SECRET or JWT_SECRET == "change-me-in-production":
        errors.append("JWT_SECRET not configured (must be changed from default)")

    if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
        print("WARNING: Slack credentials not set - Slack bot will be disabled")

    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

    return True


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_agent_prompt_intro(agent_id: str) -> str:
    """Get introduction text for an agent."""
    position = AGENT_EXECUTION_ORDER.index(agent_id) + 1
    total = len(AGENT_EXECUTION_ORDER)

    return f"Agent {position}/{total}: {AGENT_DISPLAY_NAMES[agent_id]}"


def get_iso_references_text() -> str:
    """Get formatted text about ISO 21500:2021 standards."""
    return f"""
REFERENCE: ISO 21500:2021 Project Management Standard

Process Groups:
{chr(10).join(f"  • {pg}" for pg in ISO_PROCESS_GROUPS)}

Subject Groups:
{chr(10).join(f"  • {sg}" for sg in ISO_SUBJECT_GROUPS)}
"""


def get_environment_info() -> Dict[str, any]:
    """Get current environment configuration (non-sensitive)."""
    return {
        "model": LLM_MODEL,
        "max_tokens": MAX_TOKENS,
        "api_port": API_PORT,
        "agents": AGENT_EXECUTION_ORDER,
        "slack_enabled": ENABLE_SLACK_BOT,
        "web_api_enabled": ENABLE_WEB_API,
        "cache_enabled": ENABLE_CACHE,
    }
