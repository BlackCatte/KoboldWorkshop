import logging
from typing import Optional, List
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import Log, LogCreate, LogLevel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class LoggerService:
    """Centralized logging service with database storage"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.logs
        logger.info("LoggerService initialized")
    
    async def log(self, 
                 message: str,
                 level: LogLevel = LogLevel.INFO,
                 source: str = "system",
                 execution_id: Optional[str] = None,
                 metadata: Optional[dict] = None):
        """Create a log entry"""
        
        log_entry = Log(
            message=message,
            level=level,
            source=source,
            execution_id=execution_id,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc)
        )
        
        # Store in database
        doc = log_entry.model_dump()
        doc['timestamp'] = doc['timestamp'].isoformat()
        await self.collection.insert_one(doc)
        
        # Also log to console
        log_func = getattr(logger, level.value, logger.info)
        log_func(f"[{source}] {message}")
    
    async def get_logs(self,
                      execution_id: Optional[str] = None,
                      level: Optional[LogLevel] = None,
                      source: Optional[str] = None,
                      limit: int = 100) -> List[Log]:
        """Retrieve logs with filters"""
        
        query = {}
        
        if execution_id:
            query['execution_id'] = execution_id
        
        if level:
            query['level'] = level
        
        if source:
            query['source'] = source
        
        cursor = self.collection.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit)
        
        logs = []
        async for doc in cursor:
            doc['timestamp'] = datetime.fromisoformat(doc['timestamp'])
            logs.append(Log(**doc))
        
        return logs
    
    async def get_recent_logs(self, limit: int = 100) -> List[Log]:
        """Get most recent logs"""
        return await self.get_logs(limit=limit)
    
    async def clear_old_logs(self, days: int = 30) -> int:
        """Clear logs older than specified days"""
        from datetime import timedelta
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff_date.isoformat()
        
        result = await self.collection.delete_many({
            "timestamp": {"$lt": cutoff_str}
        })
        
        logger.info(f"Cleared {result.deleted_count} old logs")
        return result.deleted_count
    
    async def info(self, message: str, source: str = "system", **kwargs):
        """Convenience method for INFO level"""
        await self.log(message, LogLevel.INFO, source, **kwargs)
    
    async def warning(self, message: str, source: str = "system", **kwargs):
        """Convenience method for WARNING level"""
        await self.log(message, LogLevel.WARNING, source, **kwargs)
    
    async def error(self, message: str, source: str = "system", **kwargs):
        """Convenience method for ERROR level"""
        await self.log(message, LogLevel.ERROR, source, **kwargs)
    
    async def debug(self, message: str, source: str = "system", **kwargs):
        """Convenience method for DEBUG level"""
        await self.log(message, LogLevel.DEBUG, source, **kwargs)
    
    async def critical(self, message: str, source: str = "system", **kwargs):
        """Convenience method for CRITICAL level"""
        await self.log(message, LogLevel.CRITICAL, source, **kwargs)
