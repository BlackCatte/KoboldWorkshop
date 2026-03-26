import asyncio
import logging
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

# Import new detection engine
from detectors.detection_engine import DetectionEngine

logger = logging.getLogger(__name__)


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
        
        # Initialize new detection engine
        self.detection_engine = DetectionEngine(confidence_threshold=0.7)
        
        # Conversation context
        self.last_response_text = ""
        
        # Monitor settings
        self.monitor_interval = 2.0  # seconds
        self.enabled = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        logger.info("KoboldMonitor initialized with advanced pattern detection")
    
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
        """
        Analyze AI response using advanced pattern intelligence
        Uses new detection engine - no ML required
        """
        
        # Use the new detection engine
        detection = await self.detection_engine.analyze(response_text, context_id)
        
        # Convert to old format for compatibility
        results = {
            "detected": detection.detected,
            "confidence": detection.confidence,
            "tool_type": detection.tool_type,
            "tool_name": detection.tool_name,
            "language": detection.language,
            "code": detection.code,
            "description": detection.description,
            "patterns_matched": detection.patterns_matched,
            "reasoning": detection.reasoning,
            "metadata": detection.metadata
        }
        
        # Update last response
        self.last_response_text = response_text
        
        # Log detection
        if detection.detected:
            await self.logger_service.info(
                f"Tool detected! Confidence: {detection.confidence:.2f}, "
                f"Type: {detection.tool_type}, Language: {detection.language}",
                source="monitor",
                metadata=results
            )
            
            # Broadcast detection with full details
            await self.websocket_manager.broadcast({
                "type": "tool_detected",
                "data": results,
                "response_text": response_text[:500]  # First 500 chars
            })
        else:
            logger.debug(f"No tool detected (confidence: {detection.confidence:.2f})")
        
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
        """Get monitor status with detection engine stats"""
        detection_stats = self.detection_engine.get_stats()
        
        return {
            "enabled": self.enabled,
            "monitor_interval": self.monitor_interval,
            "processed_count": detection_stats['processed_count'],
            "detection_threshold": detection_stats['threshold'],
            "kobold_connected": asyncio.run(self.kobold.check_connection())
        }
