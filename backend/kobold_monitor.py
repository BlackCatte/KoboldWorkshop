import asyncio
import logging
import re
from typing import Dict, Set, Optional, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

from kobold_client import KoboldCPPClient
from tool_manager import ToolManager
from execution_engine import ExecutionEngine
from approval_manager import ApprovalManager
from logger_service import LoggerService
from websocket_manager import WebSocketManager
from models import (
    ToolCreate, ToolType, ToolConfig,
    ExecutionCreate, ApprovalCreate
)

logger = logging.getLogger(__name__)


class ToolPattern:
    """Patterns for detecting tool creation/execution requests"""
    
    # Pattern for detecting code blocks
    CODE_BLOCK = r'```(?:python|bash|sh|javascript|js)?\n(.*?)```'
    
    # Pattern for detecting tool creation intent
    TOOL_CREATION_KEYWORDS = [
        r'(?:create|write|make)\s+(?:a\s+)?(?:script|tool|function|program)',
        r'(?:I\'ll|I will|let me)\s+(?:create|write|make)',
        r'here\'s\s+(?:a|the)\s+(?:script|tool|function|code)',
    ]
    
    # Pattern for detecting execution intent
    EXECUTION_KEYWORDS = [
        r'(?:execute|run|launch|start)\s+(?:this|the)',
        r'let me\s+(?:execute|run)',
        r'executing|running',
    ]
    
    # Pattern for detecting function calls
    FUNCTION_CALL = r'([a-zA-Z_][a-zA-Z0-9_]*)\(([^)]*)\)'
    
    # Pattern for Docker container requests
    DOCKER_KEYWORDS = [
        r'(?:create|start|run)\s+(?:a\s+)?(?:docker\s+)?container',
        r'spin\s+up\s+(?:a\s+)?container',
    ]


class KoboldMonitor:
    """Monitors KoboldCPP conversations and auto-detects tool usage"""
    
    def __init__(self,
                 kobold_client: KoboldCPPClient,
                 tool_manager: ToolManager,
                 execution_engine: ExecutionEngine,
                 approval_manager: ApprovalManager,
                 logger_service: LoggerService,
                 websocket_manager: WebSocketManager):
        
        self.kobold = kobold_client
        self.tool_manager = tool_manager
        self.execution_engine = execution_engine
        self.approval_manager = approval_manager
        self.logger_service = logger_service
        self.websocket_manager = websocket_manager
        
        # Track processed responses to avoid duplicates
        self.processed_responses: Set[str] = set()
        
        # Conversation context
        self.last_response_text = ""
        
        # Monitor settings
        self.monitor_interval = 2.0  # seconds
        self.enabled = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        logger.info("KoboldMonitor initialized")
    
    async def start(self):
        """Start the monitoring service"""
        if self.enabled:
            logger.warning("Monitor already running")
            return
        
        self.enabled = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        
        await self.logger_service.info(
            "KoboldCPP monitoring started - watching for tool requests",
            source="monitor"
        )
        
        await self.websocket_manager.broadcast({
            "type": "monitor_status",
            "status": "started",
            "message": "Now monitoring KoboldCPP for tool suggestions"
        })
        
        logger.info("🔍 KoboldCPP monitoring started")
    
    async def stop(self):
        """Stop the monitoring service"""
        if not self.enabled:
            return
        
        self.enabled = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        await self.logger_service.info(
            "KoboldCPP monitoring stopped",
            source="monitor"
        )
        
        await self.websocket_manager.broadcast({
            "type": "monitor_status",
            "status": "stopped"
        })
        
        logger.info("🛑 KoboldCPP monitoring stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Monitor loop started")
        
        while self.enabled:
            try:
                # Check KoboldCPP connection
                if not await self.kobold.check_connection():
                    await asyncio.sleep(self.monitor_interval)
                    continue
                
                # Get recent generations (this would be from KoboldCPP's history)
                # For now, we'll simulate by monitoring the latest generation
                # In a real implementation, you'd fetch from KoboldCPP's API
                
                # Note: Since KoboldCPP doesn't have a direct "recent history" endpoint,
                # we'll monitor by tracking the conversation state
                # This is a placeholder - actual implementation would depend on
                # how you're interacting with KoboldCPP
                
                await asyncio.sleep(self.monitor_interval)
                
            except asyncio.CancelledError:
                logger.info("Monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(self.monitor_interval)
    
    async def analyze_response(self, response_text: str, context_id: str = "monitor") -> Dict[str, Any]:
        """Analyze AI response for tool creation/execution patterns"""
        
        # Create a hash to avoid processing duplicates
        import hashlib
        response_hash = hashlib.md5(response_text.encode()).hexdigest()
        
        if response_hash in self.processed_responses:
            return {"detected": False, "reason": "already_processed"}
        
        self.processed_responses.add(response_hash)
        self.last_response_text = response_text
        
        results = {
            "detected": False,
            "tool_type": None,
            "tool_name": None,
            "code": None,
            "description": None,
            "execution_intent": False,
            "patterns_matched": []
        }
        
        # 1. Check for code blocks
        code_blocks = re.findall(ToolPattern.CODE_BLOCK, response_text, re.DOTALL)
        if code_blocks:
            results["code"] = code_blocks[0].strip()
            results["detected"] = True
            results["patterns_matched"].append("code_block")
        
        # 2. Check for tool creation keywords
        for pattern in ToolPattern.TOOL_CREATION_KEYWORDS:
            if re.search(pattern, response_text, re.IGNORECASE):
                results["detected"] = True
                results["patterns_matched"].append("tool_creation")
                break
        
        # 3. Check for execution intent
        for pattern in ToolPattern.EXECUTION_KEYWORDS:
            if re.search(pattern, response_text, re.IGNORECASE):
                results["execution_intent"] = True
                results["patterns_matched"].append("execution_intent")
                break
        
        # 4. Check for Docker container requests
        for pattern in ToolPattern.DOCKER_KEYWORDS:
            if re.search(pattern, response_text, re.IGNORECASE):
                results["detected"] = True
                results["tool_type"] = ToolType.DOCKER_CONTAINER
                results["patterns_matched"].append("docker_container")
                break
        
        # 5. Check for function calls
        function_calls = re.findall(ToolPattern.FUNCTION_CALL, response_text)
        if function_calls:
            results["detected"] = True
            results["patterns_matched"].append("function_call")
            results["function_calls"] = [
                {"name": name, "args": args} 
                for name, args in function_calls
            ]
        
        # 6. Determine tool type if not already set
        if results["detected"] and not results["tool_type"]:
            if results["code"]:
                # Detect language from code
                if "def " in results["code"] or "import " in results["code"]:
                    results["tool_type"] = ToolType.SCRIPT
                elif "function " in results["code"] or "const " in results["code"]:
                    results["tool_type"] = ToolType.SCRIPT
                else:
                    results["tool_type"] = ToolType.SCRIPT
            else:
                results["tool_type"] = ToolType.FUNCTION
        
        # 7. Extract tool name (simple heuristic)
        if results["detected"]:
            name_match = re.search(r'(?:called|named)\s+["\']?([a-zA-Z_][a-zA-Z0-9_]*)["\']?', response_text)
            if name_match:
                results["tool_name"] = name_match.group(1)
            else:
                # Generate a name based on timestamp
                results["tool_name"] = f"ai_tool_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 8. Extract description (first sentence or line)
        if results["detected"]:
            sentences = re.split(r'[.!?]\s+', response_text)
            if sentences:
                results["description"] = sentences[0][:200]  # First 200 chars
        
        # Log detection
        if results["detected"]:
            await self.logger_service.info(
                f"Tool pattern detected: {results['patterns_matched']}",
                source="monitor",
                metadata=results
            )
            
            # Broadcast detection
            await self.websocket_manager.broadcast({
                "type": "tool_detected",
                "data": results,
                "response_text": response_text[:500]  # First 500 chars
            })
        
        return results
    
    async def handle_detected_tool(self, analysis: Dict[str, Any], auto_create: bool = True) -> Optional[str]:
        """Handle a detected tool request"""
        
        if not analysis.get("detected"):
            return None
        
        try:
            # Create tool
            tool_data = ToolCreate(
                name=analysis.get("tool_name", "ai_generated_tool"),
                type=analysis.get("tool_type", ToolType.SCRIPT),
                description=analysis.get("description", "AI-generated tool"),
                code=analysis.get("code", "# No code provided"),
                tags=["ai_generated", "monitored"]
            )
            
            tool = await self.tool_manager.create_tool(tool_data, created_by="ai_monitor")
            
            await self.logger_service.info(
                f"Auto-created tool: {tool.name} (ID: {tool.id})",
                source="monitor"
            )
            
            # Create execution
            execution_data = ExecutionCreate(
                tool_id=tool.id,
                created_by="ai_monitor",
                context_id="monitor"
            )
            
            execution = await self.execution_engine.create_execution(execution_data)
            
            # Create approval request
            approval_data = ApprovalCreate(
                execution_id=execution.id,
                tool_id=tool.id,
                tool_name=tool.name,
                tool_code=tool.code,
                requester_note=f"AI suggested this tool. Patterns: {', '.join(analysis['patterns_matched'])}",
                requested_by="ai_monitor"
            )
            
            approval = await self.approval_manager.create_approval(approval_data)
            
            # Broadcast approval request
            await self.websocket_manager.broadcast_approval_request({
                "approval_id": approval.id,
                "tool_name": tool.name,
                "tool_type": tool.type,
                "description": tool.description,
                "code_preview": tool.code[:300],
                "patterns": analysis["patterns_matched"],
                "auto_detected": True
            })
            
            await self.logger_service.info(
                f"Approval request created: {approval.id} for tool: {tool.name}",
                source="monitor"
            )
            
            return approval.id
            
        except Exception as e:
            logger.error(f"Error handling detected tool: {e}")
            await self.logger_service.error(
                f"Failed to create tool from detection: {str(e)}",
                source="monitor"
            )
            return None
    
    async def inject_execution_result(self, execution_id: str) -> bool:
        """Inject execution results back into KoboldCPP context"""
        
        execution = await self.execution_engine.get_execution(execution_id)
        if not execution or not execution.result:
            return False
        
        # Format the result for injection
        result_text = f"\n\n[Tool Execution Result]\n"
        result_text += f"Tool: {execution.tool_id}\n"
        result_text += f"Status: {execution.status}\n"
        result_text += f"Output:\n{execution.result}\n"
        result_text += f"[End of Result]\n\n"
        
        # Inject into KoboldCPP
        success = await self.kobold.inject_context(result_text)
        
        if success:
            await self.logger_service.info(
                f"Injected execution result into KoboldCPP context",
                source="monitor",
                execution_id=execution_id
            )
        else:
            await self.logger_service.warning(
                f"Failed to inject execution result",
                source="monitor",
                execution_id=execution_id
            )
        
        return success
    
    def get_status(self) -> Dict[str, Any]:
        """Get monitor status"""
        return {
            "enabled": self.enabled,
            "monitor_interval": self.monitor_interval,
            "processed_count": len(self.processed_responses),
            "kobold_connected": asyncio.run(self.kobold.check_connection())
        }
