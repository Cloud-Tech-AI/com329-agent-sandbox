"""Data models for the code change agent."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of events emitted during agent execution."""
    TOOL = "tool"
    THINKING = "thinking"
    FILE_CHANGE = "file_change"
    DIFF = "diff"
    DONE = "done"
    ERROR = "error"
    INFO = "info"
    METRICS = "metrics"


class Runtime(str, Enum):
    """Container runtime for execution."""
    RUNC = "runc"
    GVISOR = "gvisor"


class AgentEvent(BaseModel):
    """Event emitted during agent execution."""
    type: EventType
    text: str
    metadata: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FileChange(BaseModel):
    """Represents a change to a file."""
    path: str
    action: str  # "created", "modified", "deleted"
    diff: Optional[str] = None
    lines_added: int = 0
    lines_removed: int = 0


class RunMetrics(BaseModel):
    """Metrics collected during a run."""
    duration_seconds: float
    tokens_used: int = 0
    files_changed: int = 0
    tools_called: int = 0
    errors: int = 0


class RunRequest(BaseModel):
    """Request to start an agent run."""
    github_repo: str = Field(..., description="GitHub repository (owner/name)")
    task: str = Field(..., description="Task description")
    runtime: Optional[Runtime] = Field(
        default=None,
        description="Target runtime (runc or gvisor). If None, runs on both."
    )


class RunResponse(BaseModel):
    """Response when starting a run."""
    id: str
    runtime: Optional[Runtime] = None
    dual_mode: bool = False  # True if running on both runtimes


class DemoScenario(BaseModel):
    """Pre-configured demo scenario."""
    id: str
    name: str
    description: str
    repo: str
    task: str
    category: str  # "security", "testing", "refactoring", "performance"
    estimated_duration: str
    difficulty: str  # "easy", "medium", "hard"
