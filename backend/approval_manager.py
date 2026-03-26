import logging
from typing import List, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import (
    Approval, ApprovalCreate, ApprovalResponse, 
    ApprovalStatus
)

logger = logging.getLogger(__name__)


class ApprovalManager:
    """Manages approval workflows for tool executions"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.approvals
        logger.info("ApprovalManager initialized")
    
    async def create_approval(self, approval_data: ApprovalCreate) -> Approval:
        """Create a new approval request"""
        
        approval = Approval(
            **approval_data.model_dump(),
            status=ApprovalStatus.PENDING,
            requested_at=datetime.now(timezone.utc)
        )
        
        doc = approval.model_dump()
        doc['requested_at'] = doc['requested_at'].isoformat()
        if doc['responded_at']:
            doc['responded_at'] = doc['responded_at'].isoformat()
        
        await self.collection.insert_one(doc)
        logger.info(f"Created approval request: {approval.id} for execution: {approval.execution_id}")
        
        return approval
    
    async def get_approval(self, approval_id: str) -> Optional[Approval]:
        """Get an approval by ID"""
        doc = await self.collection.find_one({"id": approval_id}, {"_id": 0})
        
        if doc:
            doc['requested_at'] = datetime.fromisoformat(doc['requested_at'])
            if doc.get('responded_at'):
                doc['responded_at'] = datetime.fromisoformat(doc['responded_at'])
            return Approval(**doc)
        
        return None
    
    async def get_approval_by_execution(self, execution_id: str) -> Optional[Approval]:
        """Get approval for a specific execution"""
        doc = await self.collection.find_one({"execution_id": execution_id}, {"_id": 0})
        
        if doc:
            doc['requested_at'] = datetime.fromisoformat(doc['requested_at'])
            if doc.get('responded_at'):
                doc['responded_at'] = datetime.fromisoformat(doc['responded_at'])
            return Approval(**doc)
        
        return None
    
    async def get_pending_approvals(self, limit: int = 50) -> List[Approval]:
        """Get all pending approval requests"""
        
        cursor = self.collection.find(
            {"status": ApprovalStatus.PENDING},
            {"_id": 0}
        ).sort("requested_at", -1).limit(limit)
        
        approvals = []
        async for doc in cursor:
            doc['requested_at'] = datetime.fromisoformat(doc['requested_at'])
            if doc.get('responded_at'):
                doc['responded_at'] = datetime.fromisoformat(doc['responded_at'])
            approvals.append(Approval(**doc))
        
        return approvals
    
    async def respond_to_approval(self, 
                                 approval_id: str, 
                                 response: ApprovalResponse) -> Optional[Approval]:
        """Respond to an approval request"""
        
        status = ApprovalStatus.APPROVED if response.approved else ApprovalStatus.REJECTED
        
        update_data = {
            "status": status,
            "admin_response": response.admin_response,
            "responded_by": response.responded_by,
            "responded_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = await self.collection.update_one(
            {"id": approval_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            action = "approved" if response.approved else "rejected"
            logger.info(f"Approval {approval_id} {action} by {response.responded_by}")
            return await self.get_approval(approval_id)
        
        return None
    
    async def get_all_approvals(self, 
                               status: Optional[ApprovalStatus] = None,
                               limit: int = 100) -> List[Approval]:
        """Get all approvals with optional status filter"""
        
        query = {}
        if status:
            query['status'] = status
        
        cursor = self.collection.find(query, {"_id": 0}).sort("requested_at", -1).limit(limit)
        
        approvals = []
        async for doc in cursor:
            doc['requested_at'] = datetime.fromisoformat(doc['requested_at'])
            if doc.get('responded_at'):
                doc['responded_at'] = datetime.fromisoformat(doc['responded_at'])
            approvals.append(Approval(**doc))
        
        return approvals
    
    async def get_approval_stats(self) -> dict:
        """Get statistics about approvals"""
        
        total = await self.collection.count_documents({})
        pending = await self.collection.count_documents({"status": ApprovalStatus.PENDING})
        approved = await self.collection.count_documents({"status": ApprovalStatus.APPROVED})
        rejected = await self.collection.count_documents({"status": ApprovalStatus.REJECTED})
        
        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected
        }
