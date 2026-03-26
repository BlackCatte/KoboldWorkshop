from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import uuid


class ToolType(str, Enum):
    """Types of tools that can be created"""
    FUNCTION = "function"
    SCRIPT = "script"
    DOCKER_CONTAINER = "docker_container"
    API_CALL = "api_call"


class ExecutionStatus(str, Enum):
    """Status of tool execution"""
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(str, Enum):
    """Status of approval requests"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Tool Models
class ToolConfig(BaseModel):
    """Configuration for a tool"""
    timeout: int = Field(default=300, description="Timeout in seconds")
    max_memory_mb: int = Field(default=512, description="Max memory in MB")
    max_cpu_percent: float = Field(default=50.0, description="Max CPU usage %")
    network_enabled: bool = Field(default=False, description="Allow network access")
    environment_vars: Dict[str, str] = Field(default_factory=dict)


class Tool(BaseModel):
    """Tool definition"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Tool name")
    type: ToolType = Field(..., description="Type of tool")
    description: str = Field(default="", description="Tool description")
    code: str = Field(..., description="Tool code/script")
    config: ToolConfig = Field(default_factory=ToolConfig)
    status: str = Field(default="active", description="Tool status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="system")
    tags: List[str] = Field(default_factory=list)
    version: int = Field(default=1)


class ToolCreate(BaseModel):
    """Request to create a tool"""
    name: str
    type: ToolType
    description: str = ""
    code: str
    config: Optional[ToolConfig] = None
    tags: List[str] = Field(default_factory=list)


class ToolUpdate(BaseModel):
    """Request to update a tool"""
    name: Optional[str] = None
    description: Optional[str] = None
    code: Optional[str] = None
    config: Optional[ToolConfig] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None


# Execution Models
class ResourceUsage(BaseModel):
    """Resource usage statistics"""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    disk_mb: float = 0.0
    duration_seconds: float = 0.0


class Execution(BaseModel):
    """Tool execution record"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_id: str = Field(..., description="ID of the tool being executed")
    status: ExecutionStatus = Field(default=ExecutionStatus.PENDING)
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = None
    logs: List[str] = Field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    resource_usage: ResourceUsage = Field(default_factory=ResourceUsage)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="ai")
    context_id: Optional[str] = None


class ExecutionCreate(BaseModel):
    """Request to create an execution"""
    tool_id: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    context_id: Optional[str] = None
    created_by: str = "ai"


class ExecutionUpdate(BaseModel):
    """Request to update an execution"""
    status: Optional[ExecutionStatus] = None
    output_data: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    error: Optional[str] = None


# Approval Models
class Approval(BaseModel):
    """Approval request for tool execution"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = Field(..., description="ID of execution to approve")
    tool_id: str = Field(..., description="ID of the tool")
    tool_name: str = Field(..., description="Name of the tool")
    tool_code: str = Field(..., description="Code to be executed")
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    requester_note: str = Field(default="", description="Why this tool is needed")
    admin_response: Optional[str] = None
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    responded_at: Optional[datetime] = None
    requested_by: str = Field(default="ai")
    responded_by: Optional[str] = None


class ApprovalCreate(BaseModel):
    """Request to create an approval"""
    execution_id: str
    tool_id: str
    tool_name: str
    tool_code: str
    requester_note: str = ""
    requested_by: str = "ai"


class ApprovalResponse(BaseModel):
    """Response to an approval request"""
    approved: bool
    admin_response: str = ""
    responded_by: str = "admin"


# Context Models
class Message(BaseModel):
    """Chat message"""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Context(BaseModel):
    """AI conversation context and focus management"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(..., description="Session identifier")
    focus_area: str = Field(default="", description="Current focus/goal")
    messages: List[Message] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextCreate(BaseModel):
    """Request to create a context"""
    session_id: str
    focus_area: str = ""
    goals: List[str] = Field(default_factory=list)


class ContextUpdate(BaseModel):
    """Request to update a context"""
    focus_area: Optional[str] = None
    goals: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


# Log Models
class Log(BaseModel):
    """System log entry"""
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: Optional[str] = None
    level: LogLevel = Field(default=LogLevel.INFO)
    message: str = Field(..., description="Log message")
    source: str = Field(default="system", description="Source of log")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LogCreate(BaseModel):
    """Request to create a log"""
    execution_id: Optional[str] = None
    level: LogLevel = LogLevel.INFO
    message: str
    source: str = "system"
    metadata: Dict[str, Any] = Field(default_factory=dict)


# AI Chat Models
class ChatMessage(BaseModel):
    """Chat message for AI interaction"""
    message: str
    context_id: Optional[str] = None
    session_id: str


class ChatResponse(BaseModel):
    """Response from AI"""
    response: str
    context_id: str
    tokens_generated: int = 0
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
