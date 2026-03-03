"""
Approval Workflow Engine for Trust Level 0 Agents

Manages the approval process for agent suggestions, including:
- Request creation and tracking
- Timeout handling
- State management
- Approval/rejection flow
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import uuid4
from enum import Enum
import asyncio
from dataclasses import dataclass, field


class ApprovalState(Enum):
    """States for approval requests"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    """Represents an approval request"""
    id: str = field(default_factory=lambda: str(uuid4()))
    suggestion_id: str = ""
    user_id: str = ""
    action: str = ""
    description: str = ""
    rationale: str = ""
    risk_level: str = "low"
    requested_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    state: ApprovalState = ApprovalState.PENDING
    approved_by: Optional[str] = None
    approval_note: Optional[str] = None
    rejected_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ApprovalWorkflow:
    """
    Manages approval workflows for L0 agent actions
    """

    def __init__(self) -> None:
        """Initialize approval workflow engine"""
        self.pending_requests: Dict[str, ApprovalRequest] = {}
        self.completed_requests: List[ApprovalRequest] = []
        self.approval_callbacks: Dict[str, asyncio.Event] = {}
        self.timeout_tasks: Dict[str, asyncio.Task] = {}

        # Configuration
        self.max_pending_requests = 10
        self.default_timeout = timedelta(minutes=5)
        self.allow_bulk_approval = True

    async def create_request(
        self,
        suggestion_id: str,
        user_id: str,
        action: str,
        description: str,
        rationale: str,
        risk_level: str = "low",
        timeout: Optional[timedelta] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ApprovalRequest:
        """
        Create a new approval request

        Args:
            suggestion_id: ID of the suggestion requiring approval
            user_id: ID of the user to request approval from
            action: Type of action requiring approval
            description: Human-readable description
            rationale: Explanation of why this action is needed
            risk_level: Risk level assessment
            timeout: Optional custom timeout
            metadata: Additional metadata

        Returns:
            Created ApprovalRequest

        Raises:
            ValueError: If max pending requests exceeded
        """
        # Check pending request limit
        if len(self.pending_requests) >= self.max_pending_requests:
            raise ValueError(f"Maximum pending requests ({self.max_pending_requests}) exceeded")

        # Create request
        timeout = timeout or self.default_timeout
        request = ApprovalRequest(
            suggestion_id=suggestion_id,
            user_id=user_id,
            action=action,
            description=description,
            rationale=rationale,
            risk_level=risk_level,
            expires_at=datetime.utcnow() + timeout,
            metadata=metadata or {}
        )

        # Store request
        self.pending_requests[request.id] = request

        # Create event for this request
        self.approval_callbacks[request.id] = asyncio.Event()

        # Schedule timeout
        self.timeout_tasks[request.id] = asyncio.create_task(
            self._handle_timeout(request.id, timeout)
        )

        return request

    async def approve_request(
        self,
        request_id: str,
        approved_by: str,
        approval_note: Optional[str] = None
    ) -> bool:
        """
        Approve a pending request

        Args:
            request_id: ID of the request to approve
            approved_by: ID of the approving user
            approval_note: Optional approval note

        Returns:
            True if approved successfully
        """
        if request_id not in self.pending_requests:
            return False

        request = self.pending_requests[request_id]

        # Check if request is still valid
        if request.state != ApprovalState.PENDING:
            return False

        if datetime.utcnow() > request.expires_at:
            request.state = ApprovalState.TIMEOUT
            return False

        # Update request
        request.state = ApprovalState.APPROVED
        request.approved_by = approved_by
        request.approval_note = approval_note

        # Cancel timeout task
        if request_id in self.timeout_tasks:
            self.timeout_tasks[request_id].cancel()
            del self.timeout_tasks[request_id]

        # Move to completed
        self._complete_request(request_id)

        # Signal approval
        if request_id in self.approval_callbacks:
            self.approval_callbacks[request_id].set()

        return True

    async def reject_request(
        self,
        request_id: str,
        rejected_by: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Reject a pending request

        Args:
            request_id: ID of the request to reject
            rejected_by: ID of the rejecting user
            reason: Optional rejection reason

        Returns:
            True if rejected successfully
        """
        if request_id not in self.pending_requests:
            return False

        request = self.pending_requests[request_id]

        # Check if request is still valid
        if request.state != ApprovalState.PENDING:
            return False

        # Update request
        request.state = ApprovalState.REJECTED
        request.approved_by = rejected_by
        request.rejected_reason = reason

        # Cancel timeout task
        if request_id in self.timeout_tasks:
            self.timeout_tasks[request_id].cancel()
            del self.timeout_tasks[request_id]

        # Move to completed
        self._complete_request(request_id)

        # Signal rejection
        if request_id in self.approval_callbacks:
            self.approval_callbacks[request_id].set()

        return True

    async def cancel_request(self, request_id: str) -> bool:
        """
        Cancel a pending request

        Args:
            request_id: ID of the request to cancel

        Returns:
            True if cancelled successfully
        """
        if request_id not in self.pending_requests:
            return False

        request = self.pending_requests[request_id]

        # Check if request is still pending
        if request.state != ApprovalState.PENDING:
            return False

        # Update state
        request.state = ApprovalState.CANCELLED

        # Cancel timeout task
        if request_id in self.timeout_tasks:
            self.timeout_tasks[request_id].cancel()
            del self.timeout_tasks[request_id]

        # Move to completed
        self._complete_request(request_id)

        # Signal cancellation
        if request_id in self.approval_callbacks:
            self.approval_callbacks[request_id].set()

        return True

    async def bulk_approve(
        self,
        request_ids: List[str],
        approved_by: str,
        approval_note: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Approve multiple requests at once

        Args:
            request_ids: List of request IDs to approve
            approved_by: ID of the approving user
            approval_note: Optional approval note for all

        Returns:
            Dictionary mapping request IDs to success status
        """
        if not self.allow_bulk_approval:
            raise ValueError("Bulk approval is disabled")

        results = {}
        for request_id in request_ids:
            results[request_id] = await self.approve_request(
                request_id, approved_by, approval_note
            )

        return results

    async def wait_for_approval(
        self,
        request_id: str,
        timeout: Optional[timedelta] = None
    ) -> ApprovalState:
        """
        Wait for a request to be approved or rejected

        Args:
            request_id: ID of the request to wait for
            timeout: Optional timeout override

        Returns:
            Final ApprovalState
        """
        if request_id not in self.pending_requests:
            raise ValueError(f"Request {request_id} not found")

        if request_id not in self.approval_callbacks:
            raise ValueError(f"No callback registered for request {request_id}")

        event = self.approval_callbacks[request_id]

        # Wait for event or timeout
        try:
            if timeout:
                await asyncio.wait_for(event.wait(), timeout.total_seconds())
            else:
                await event.wait()
        except asyncio.TimeoutError:
            # Mark as timeout if we hit the wait timeout
            if request_id in self.pending_requests:
                self.pending_requests[request_id].state = ApprovalState.TIMEOUT
                self._complete_request(request_id)

        # Get final state
        if request_id in self.completed_requests:
            request = next(r for r in self.completed_requests if r.id == request_id)
        else:
            request = self.pending_requests.get(request_id)

        return request.state if request else ApprovalState.TIMEOUT

    async def _handle_timeout(self, request_id: str, timeout: timedelta):
        """Handle request timeout"""
        await asyncio.sleep(timeout.total_seconds())

        if request_id in self.pending_requests:
            request = self.pending_requests[request_id]
            if request.state == ApprovalState.PENDING:
                request.state = ApprovalState.TIMEOUT
                self._complete_request(request_id)

                # Signal timeout
                if request_id in self.approval_callbacks:
                    self.approval_callbacks[request_id].set()

    def _complete_request(self, request_id: str):
        """Move request from pending to completed"""
        if request_id in self.pending_requests:
            request = self.pending_requests[request_id]
            self.completed_requests.append(request)
            del self.pending_requests[request_id]

            # Clean up callback
            if request_id in self.approval_callbacks:
                del self.approval_callbacks[request_id]

    def get_pending_requests(
        self,
        user_id: Optional[str] = None,
        risk_level: Optional[str] = None
    ) -> List[ApprovalRequest]:
        """
        Get pending approval requests

        Args:
            user_id: Optional filter by user
            risk_level: Optional filter by risk level

        Returns:
            List of pending requests
        """
        requests = list(self.pending_requests.values())

        if user_id:
            requests = [r for r in requests if r.user_id == user_id]

        if risk_level:
            requests = [r for r in requests if r.risk_level == risk_level]

        return requests

    def get_request_history(
        self,
        user_id: Optional[str] = None,
        state: Optional[ApprovalState] = None,
        limit: int = 100
    ) -> List[ApprovalRequest]:
        """
        Get historical approval requests

        Args:
            user_id: Optional filter by user
            state: Optional filter by state
            limit: Maximum number of results

        Returns:
            List of historical requests
        """
        requests = self.completed_requests[-limit:]

        if user_id:
            requests = [r for r in requests if r.user_id == user_id]

        if state:
            requests = [r for r in requests if r.state == state]

        return requests

    def cancel_all_pending(self) -> int:
        """
        Cancel all pending requests (emergency stop)

        Returns:
            Number of requests cancelled
        """
        cancelled = 0
        request_ids = list(self.pending_requests.keys())

        for request_id in request_ids:
            if asyncio.run(self.cancel_request(request_id)):
                cancelled += 1

        return cancelled

    def get_statistics(self) -> Dict[str, Any]:
        """Get workflow statistics"""
        total_completed = len(self.completed_requests)

        if total_completed == 0:
            return {
                "pending": len(self.pending_requests),
                "completed": 0,
                "approved": 0,
                "rejected": 0,
                "timeout": 0,
                "cancelled": 0,
                "approval_rate": 0.0
            }

        approved = sum(1 for r in self.completed_requests if r.state == ApprovalState.APPROVED)
        rejected = sum(1 for r in self.completed_requests if r.state == ApprovalState.REJECTED)
        timeout = sum(1 for r in self.completed_requests if r.state == ApprovalState.TIMEOUT)
        cancelled = sum(1 for r in self.completed_requests if r.state == ApprovalState.CANCELLED)

        return {
            "pending": len(self.pending_requests),
            "completed": total_completed,
            "approved": approved,
            "rejected": rejected,
            "timeout": timeout,
            "cancelled": cancelled,
            "approval_rate": approved / total_completed if total_completed > 0 else 0.0
        }
