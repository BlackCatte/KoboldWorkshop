from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from typing import List, Optional
import asyncio

# Import our modules
from models import (
    Tool, ToolCreate, ToolUpdate,
    Execution, ExecutionCreate,
    Approval, ApprovalCreate, ApprovalResponse,
    Context, ContextCreate, ContextUpdate,
    ChatMessage, ChatResponse,
    LogLevel
)
from kobold_client import KoboldCPPClient
from tool_manager import ToolManager
from execution_engine import ExecutionEngine
from logger_service import LoggerService
from websocket_manager import WebSocketManager
from approval_manager import ApprovalManager
from kobold_monitor import KoboldMonitor

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'ai_tool_monitor')]

# Initialize services
kobold_client = KoboldCPPClient(base_url=os.environ.get('KOBOLDCPP_URL', 'http://localhost:5001'))
tool_manager = ToolManager(db)
execution_engine = ExecutionEngine(db)
logger_service = LoggerService(db)
websocket_manager = WebSocketManager()
approval_manager = ApprovalManager(db)

# Initialize monitor (will start on app startup)
kobold_monitor = KoboldMonitor(
    kobold_client=kobold_client,
    tool_manager=tool_manager,
    execution_engine=execution_engine,
    approval_manager=approval_manager,
    logger_service=logger_service,
    websocket_manager=websocket_manager
)

# Create the main app
app = FastAPI(title="AI Tool Monitor API", version="1.0.0")

# Create API router with /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================
# HEALTH & STATUS ENDPOINTS
# ============================================

@api_router.get("/")
async def root():
    return {"message": "AI Tool Monitor API", "status": "running"}


@api_router.get("/health")
async def health_check():
    """Check system health"""
    kobold_status = await kobold_client.check_connection()
    
    return {
        "status": "healthy",
        "koboldcpp": "connected" if kobold_status else "disconnected",
        "database": "connected",
        "websocket_connections": websocket_manager.get_connection_count()
    }


@api_router.get("/status")
async def system_status():
    """Get detailed system status"""
    kobold_connected = await kobold_client.check_connection()
    model_info = await kobold_client.get_model_info() if kobold_connected else None
    
    approval_stats = await approval_manager.get_approval_stats()
    
    return {
        "koboldcpp": {
            "connected": kobold_connected,
            "model": model_info
        },
        "approvals": approval_stats,
        "websocket_connections": websocket_manager.get_connection_count()
    }


# ============================================
# TOOL ENDPOINTS
# ============================================

@api_router.post("/tools", response_model=Tool)
async def create_tool(tool_data: ToolCreate):
    """Create a new tool"""
    tool = await tool_manager.create_tool(tool_data)
    await logger_service.info(f"Tool created: {tool.name}", source="api")
    await websocket_manager.broadcast_tool_update(tool.id, "created", tool.model_dump())
    return tool


@api_router.get("/tools", response_model=List[Tool])
async def get_tools(status: Optional[str] = None, limit: int = 100):
    """Get all tools"""
    tools = await tool_manager.get_all_tools(status=status, limit=limit)
    return tools


@api_router.get("/tools/{tool_id}", response_model=Tool)
async def get_tool(tool_id: str):
    """Get a specific tool"""
    tool = await tool_manager.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@api_router.put("/tools/{tool_id}", response_model=Tool)
async def update_tool(tool_id: str, tool_update: ToolUpdate):
    """Update a tool"""
    tool = await tool_manager.update_tool(tool_id, tool_update)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    await logger_service.info(f"Tool updated: {tool_id}", source="api")
    await websocket_manager.broadcast_tool_update(tool_id, "updated", tool.model_dump())
    return tool


@api_router.delete("/tools/{tool_id}")
async def delete_tool(tool_id: str):
    """Delete a tool"""
    success = await tool_manager.delete_tool(tool_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    await logger_service.info(f"Tool deleted: {tool_id}", source="api")
    await websocket_manager.broadcast_tool_update(tool_id, "deleted")
    return {"message": "Tool deleted successfully"}


@api_router.get("/tools/search/{query}", response_model=List[Tool])
async def search_tools(query: str, limit: int = 20):
    """Search tools"""
    tools = await tool_manager.search_tools(query, limit=limit)
    return tools


# ============================================
# EXECUTION ENDPOINTS
# ============================================

@api_router.post("/executions", response_model=Execution)
async def create_execution(exec_data: ExecutionCreate):
    """Create a new execution"""
    execution = await execution_engine.create_execution(exec_data)
    await logger_service.info(f"Execution created: {execution.id}", source="api")
    await websocket_manager.broadcast_execution_status(execution.id, "created")
    return execution


@api_router.get("/executions/{execution_id}", response_model=Execution)
async def get_execution(execution_id: str):
    """Get a specific execution"""
    execution = await execution_engine.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


@api_router.get("/executions", response_model=List[Execution])
async def get_recent_executions(limit: int = 50):
    """Get recent executions"""
    executions = await execution_engine.get_recent_executions(limit=limit)
    return executions


@api_router.post("/executions/{execution_id}/execute")
async def execute_tool_endpoint(execution_id: str):
    """Execute a tool (requires prior approval if needed)"""
    execution = await execution_engine.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    tool = await tool_manager.get_tool(execution.tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    # Check if approval exists and is approved
    approval = await approval_manager.get_approval_by_execution(execution_id)
    if approval and approval.status != "approved":
        raise HTTPException(status_code=403, detail="Execution not approved")
    
    # Execute in background
    asyncio.create_task(execution_engine.execute_tool(tool, execution))
    
    await websocket_manager.broadcast_execution_status(execution_id, "started")
    
    return {"message": "Execution started", "execution_id": execution_id}


@api_router.post("/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: str):
    """Cancel a running execution"""
    success = await execution_engine.cancel_execution(execution_id)
    if not success:
        raise HTTPException(status_code=404, detail="Execution not found or not running")
    
    await websocket_manager.broadcast_execution_status(execution_id, "cancelled")
    return {"message": "Execution cancelled"}


# ============================================
# APPROVAL ENDPOINTS
# ============================================

@api_router.post("/approvals", response_model=Approval)
async def create_approval(approval_data: ApprovalCreate):
    """Create an approval request"""
    approval = await approval_manager.create_approval(approval_data)
    await logger_service.info(f"Approval requested: {approval.id}", source="api")
    await websocket_manager.broadcast_approval_request(approval.model_dump())
    return approval


@api_router.get("/approvals/pending", response_model=List[Approval])
async def get_pending_approvals(limit: int = 50):
    """Get pending approval requests"""
    approvals = await approval_manager.get_pending_approvals(limit=limit)
    return approvals


@api_router.get("/approvals/{approval_id}", response_model=Approval)
async def get_approval(approval_id: str):
    """Get a specific approval"""
    approval = await approval_manager.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


@api_router.post("/approvals/{approval_id}/respond", response_model=Approval)
async def respond_to_approval(approval_id: str, response: ApprovalResponse):
    """Respond to an approval request"""
    approval = await approval_manager.respond_to_approval(approval_id, response)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    action = "approved" if response.approved else "rejected"
    await logger_service.info(f"Approval {action}: {approval_id}", source="api")
    
    # Broadcast approval response
    await websocket_manager.broadcast({
        "type": "approval_response",
        "approval_id": approval_id,
        "action": action,
        "execution_id": approval.execution_id
    })
    
    # If approved, trigger execution
    if response.approved:
        await execute_tool_endpoint(approval.execution_id)
    
    return approval


@api_router.get("/approvals", response_model=List[Approval])
async def get_all_approvals(limit: int = 100):
    """Get all approvals"""
    approvals = await approval_manager.get_all_approvals(limit=limit)
    return approvals


# ============================================
# AI CHAT ENDPOINTS
# ============================================

@api_router.post("/chat")
async def chat_with_ai(message: ChatMessage):
    """Chat with AI (non-streaming)"""
    
    # Check KoboldCPP connection
    if not await kobold_client.check_connection():
        raise HTTPException(status_code=503, detail="KoboldCPP not available")
    
    # Generate response
    response_text = await kobold_client.generate(
        prompt=message.message,
        max_length=200
    )
    
    if not response_text:
        raise HTTPException(status_code=500, detail="Failed to generate response")
    
    # Detect tool calls
    tool_calls = await kobold_client.detect_tool_calls(response_text)
    
    await logger_service.info(f"AI response generated", source="koboldcpp")
    
    return ChatResponse(
        response=response_text,
        context_id=message.context_id or message.session_id,
        tool_calls=tool_calls
    )


@api_router.post("/chat/stream")
async def chat_with_ai_stream(message: ChatMessage):
    """Chat with AI (streaming via SSE)"""
    
    # Check KoboldCPP connection
    if not await kobold_client.check_connection():
        raise HTTPException(status_code=503, detail="KoboldCPP not available")
    
    async def generate_stream():
        """Generator for streaming response"""
        try:
            async for token in kobold_client.generate_stream(prompt=message.message):
                # Send token via SSE format
                yield f"data: {token}\n\n"
                
                # Also broadcast via WebSocket
                await websocket_manager.broadcast_token(token, message.context_id)
            
            # Send completion signal
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: [ERROR: {str(e)}]\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============================================
# LOG ENDPOINTS
# ============================================

@api_router.get("/logs")
async def get_logs(
    execution_id: Optional[str] = None,
    level: Optional[LogLevel] = None,
    source: Optional[str] = None,
    limit: int = 100
):
    """Get logs with filters"""
    logs = await logger_service.get_logs(
        execution_id=execution_id,
        level=level,
        source=source,
        limit=limit
    )
    return logs


@api_router.get("/logs/recent")
async def get_recent_logs(limit: int = 100):
    """Get recent logs"""
    logs = await logger_service.get_recent_logs(limit=limit)
    return logs


# ============================================
# MONITOR ENDPOINTS
# ============================================

@api_router.get("/monitor/status")
async def get_monitor_status():
    """Get monitoring service status"""
    return kobold_monitor.get_status()


@api_router.post("/monitor/start")
async def start_monitor():
    """Start the KoboldCPP monitoring service"""
    await kobold_monitor.start()
    return {"message": "Monitor started", "status": kobold_monitor.get_status()}


@api_router.post("/monitor/stop")
async def stop_monitor():
    """Stop the KoboldCPP monitoring service"""
    await kobold_monitor.stop()
    return {"message": "Monitor stopped", "status": kobold_monitor.get_status()}


@api_router.post("/monitor/analyze")
async def analyze_text(data: dict):
    """Manually analyze text for tool patterns"""
    text = data.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    analysis = await kobold_monitor.analyze_response(text, context_id="manual")
    
    if analysis.get("detected") and data.get("auto_create", False):
        approval_id = await kobold_monitor.handle_detected_tool(analysis)
        analysis["approval_id"] = approval_id
    
    return analysis


# ============================================
# WEBSOCKET ENDPOINT
# ============================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket_manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive and receive messages
            data = await websocket.receive_text()
            
            # Echo back (you can handle client messages here)
            await websocket_manager.send_personal_message(
                websocket,
                {"type": "echo", "data": data}
            )
            
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        websocket_manager.disconnect(websocket)


# ============================================
# INCLUDE ROUTER AND MIDDLEWARE
# ============================================

# Include the router in the main app
app.include_router(api_router)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# STARTUP & SHUTDOWN EVENTS
# ============================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("🚀 AI Tool Monitor starting up...")
    
    # Check KoboldCPP connection
    kobold_status = await kobold_client.check_connection()
    if kobold_status:
        logger.info("✅ KoboldCPP connected")
        model_info = await kobold_client.get_model_info()
        if model_info:
            logger.info(f"✅ Model loaded: {model_info.get('result', 'Unknown')}")
        
        # Auto-start monitor if KoboldCPP is connected
        await kobold_monitor.start()
    else:
        logger.warning("⚠️  KoboldCPP not connected - make sure it's running on port 5001")
        logger.info("💡 Monitor will auto-start when KoboldCPP connects")
    
    logger.info("✅ Database connected")
    logger.info("✅ All services initialized")
    logger.info("📡 WebSocket ready for connections")
    logger.info("🎯 AI Tool Monitor ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down AI Tool Monitor...")
    
    # Stop monitor
    await kobold_monitor.stop()
    
    client.close()
    logger.info("Database connection closed")
