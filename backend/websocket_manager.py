import logging
from typing import Dict, Set
from fastapi import WebSocket
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        # Store active connections
        self.active_connections: Set[WebSocket] = set()
        logger.info("WebSocketManager initialized")
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
        
        # Send welcome message
        await self.send_personal_message(
            websocket,
            {
                "type": "connection",
                "message": "Connected to AI Tool Monitor",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Send a message to a specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        
        # Add timestamp if not present
        if 'timestamp' not in message:
            message['timestamp'] = datetime.utcnow().isoformat()
        
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def broadcast_log(self, log_message: str, level: str = "info", source: str = "system"):
        """Broadcast a log message"""
        await self.broadcast({
            "type": "log",
            "level": level,
            "message": log_message,
            "source": source
        })
    
    async def broadcast_execution_status(self, execution_id: str, status: str, details: dict = None):
        """Broadcast execution status update"""
        await self.broadcast({
            "type": "execution_status",
            "execution_id": execution_id,
            "status": status,
            "details": details or {}
        })
    
    async def broadcast_tool_update(self, tool_id: str, action: str, tool_data: dict = None):
        """Broadcast tool update"""
        await self.broadcast({
            "type": "tool_update",
            "tool_id": tool_id,
            "action": action,
            "data": tool_data or {}
        })
    
    async def broadcast_approval_request(self, approval_data: dict):
        """Broadcast approval request"""
        await self.broadcast({
            "type": "approval_request",
            "data": approval_data
        })
    
    async def broadcast_ai_message(self, message: str, context_id: str = None):
        """Broadcast AI-generated message"""
        await self.broadcast({
            "type": "ai_message",
            "message": message,
            "context_id": context_id
        })
    
    async def broadcast_token(self, token: str, context_id: str = None):
        """Broadcast a single token (for streaming)"""
        await self.broadcast({
            "type": "token",
            "token": token,
            "context_id": context_id
        })
    
    async def broadcast_system_status(self, status_data: dict):
        """Broadcast system status"""
        await self.broadcast({
            "type": "system_status",
            "data": status_data
        })
    
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)
