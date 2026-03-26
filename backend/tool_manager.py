import logging
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from models import Tool, ToolCreate, ToolUpdate, ToolType

logger = logging.getLogger(__name__)


class ToolManager:
    """Manages tool registry and operations"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.tools
    
    async def create_tool(self, tool_data: ToolCreate, created_by: str = "user") -> Tool:
        """Create a new tool"""
        tool_dict = tool_data.model_dump()
        if tool_dict.get('config') is None:
            from models import ToolConfig
            tool_dict['config'] = ToolConfig()
        
        tool = Tool(
            **tool_dict,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        doc = tool.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        doc['updated_at'] = doc['updated_at'].isoformat()
        doc['config'] = dict(doc['config'])  # Convert ToolConfig to dict
        
        await self.collection.insert_one(doc)
        logger.info(f"Created tool: {tool.name} (ID: {tool.id})")
        
        return tool
    
    async def get_tool(self, tool_id: str) -> Optional[Tool]:
        """Get a tool by ID"""
        doc = await self.collection.find_one({"id": tool_id}, {"_id": 0})
        
        if doc:
            # Convert ISO strings back to datetime
            doc['created_at'] = datetime.fromisoformat(doc['created_at'])
            doc['updated_at'] = datetime.fromisoformat(doc['updated_at'])
            return Tool(**doc)
        
        return None
    
    async def get_all_tools(self, 
                           status: Optional[str] = None,
                           tool_type: Optional[ToolType] = None,
                           limit: int = 100) -> List[Tool]:
        """Get all tools with optional filters"""
        query = {}
        
        if status:
            query['status'] = status
        
        if tool_type:
            query['type'] = tool_type
        
        cursor = self.collection.find(query, {"_id": 0}).limit(limit)
        tools = []
        
        async for doc in cursor:
            doc['created_at'] = datetime.fromisoformat(doc['created_at'])
            doc['updated_at'] = datetime.fromisoformat(doc['updated_at'])
            tools.append(Tool(**doc))
        
        return tools
    
    async def update_tool(self, tool_id: str, tool_update: ToolUpdate) -> Optional[Tool]:
        """Update a tool"""
        update_data = tool_update.model_dump(exclude_unset=True)
        
        if update_data:
            update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # Increment version on code change
            if 'code' in update_data:
                current_tool = await self.get_tool(tool_id)
                if current_tool:
                    update_data['version'] = current_tool.version + 1
            
            if 'config' in update_data and update_data['config']:
                update_data['config'] = dict(update_data['config'])
            
            result = await self.collection.update_one(
                {"id": tool_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"Updated tool: {tool_id}")
                return await self.get_tool(tool_id)
        
        return None
    
    async def delete_tool(self, tool_id: str) -> bool:
        """Delete a tool (soft delete by setting status)"""
        result = await self.collection.update_one(
            {"id": tool_id},
            {"$set": {
                "status": "deleted",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        if result.modified_count > 0:
            logger.info(f"Deleted tool: {tool_id}")
            return True
        
        return False
    
    async def search_tools(self, query: str, limit: int = 20) -> List[Tool]:
        """Search tools by name or description"""
        search_query = {
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
                {"tags": {"$in": [query]}}
            ],
            "status": "active"
        }
        
        cursor = self.collection.find(search_query, {"_id": 0}).limit(limit)
        tools = []
        
        async for doc in cursor:
            doc['created_at'] = datetime.fromisoformat(doc['created_at'])
            doc['updated_at'] = datetime.fromisoformat(doc['updated_at'])
            tools.append(Tool(**doc))
        
        return tools
    
    async def get_tools_by_type(self, tool_type: ToolType) -> List[Tool]:
        """Get all tools of a specific type"""
        return await self.get_all_tools(tool_type=tool_type, status="active")
