"""
AI Cost monitoring router using Pusher for real-time updates.
Replaces WebSocket implementation with Pusher REST API triggers.
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, date

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.dependencies.auth import get_current_user
from models.ai_cost_models import UserModel
from services.ai_cost_manager import AICostManager
from services.cost_tracking_service import CostTrackingService
from services.realtime import get_pusher_client, Channels, Events

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/realtime", tags=["realtime"])


class PusherAuthRequest(BaseModel):
    """Request model for Pusher channel authentication."""

    socket_id: str = Field(..., description="Pusher socket ID")
    channel_name: str = Field(..., description="Channel to authenticate")


class PusherTriggerRequest(BaseModel):
    """Request model for triggering Pusher events."""

    channel: str = Field(..., description="Channel name")
    event: str = Field(..., description="Event name")
    data: Dict[str, Any] = Field(..., description="Event data")
    socket_id: Optional[str] = Field(None, description="Socket ID to exclude")


class RealtimeCostService:
    """Service for managing real-time cost updates via Pusher."""

    def __init__(self) -> None:
        self.pusher_client = get_pusher_client()
        self.cost_manager = AICostManager()
        self.cost_tracker = CostTrackingService()
        self._background_tasks = []

    async def authenticate_channel(
        self, socket_id: str, channel_name: str, user: UserModel
    ) -> Dict[str, Any]:
        """
        Authenticate user for private/presence channels.

        Args:
            socket_id: Pusher socket ID
            channel_name: Channel to authenticate
            user: Current user

        Returns:
            Authentication response
        """
        # Validate channel access based on user
        if channel_name.startswith("private-"):
            # Private channel - check user permissions
            if channel_name == Channels.COST_DASHBOARD and not user.has_dashboard_access:
                raise HTTPException(status_code=403, detail="Access denied to cost dashboard")

            if channel_name == Channels.BUDGET_ALERTS and not user.has_budget_access:
                raise HTTPException(status_code=403, detail="Access denied to budget alerts")

            # Generate auth token
            auth = self.pusher_client.authenticate(channel=channel_name, socket_id=socket_id)
            return auth

        elif channel_name.startswith("presence-"):
            # Presence channel - include user data
            user_data = {
                "user_id": str(user.id),
                "user_info": {"name": user.name, "email": user.email, "role": user.role},
            }

            auth = self.pusher_client.authenticate(
                channel=channel_name, socket_id=socket_id, custom_data=user_data
            )
            return auth

        else:
            # Public channel - no auth needed
            raise HTTPException(
                status_code=400, detail="Public channels don't require authentication"
            )

    async def send_initial_data(self, user_id: str) -> None:
        """Send initial cost data to user's private channel."""
        try:
            today = date.today()

            # Gather initial data
            daily_summary = await self.cost_manager.get_daily_summary(today)
            trends = await self.cost_tracker.get_cost_trends(7)
            budget_config = await self.cost_manager.budget_service.get_current_budget()

            # Format data
            initial_data = {
                "type": "initial_data",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "daily_summary": {
                        "total_cost": str(daily_summary["total_cost"]),
                        "total_requests": daily_summary["total_requests"],
                        "total_tokens": daily_summary["total_tokens"],
                        "service_breakdown": {
                            k: {
                                "cost": str(v["cost"]) if isinstance(v, dict) else str(v),
                                "requests": v.get("requests", 0) if isinstance(v, dict) else 0,
                            }
                            for k, v in daily_summary.get("service_breakdown", {}).items()
                        },
                    },
                    "cost_trends": [
                        {
                            "date": trend["date"],
                            "cost": str(trend["cost"]),
                            "requests": trend["requests"],
                        }
                        for trend in trends
                    ],
                    "budget_status": {
                        "daily_limit": str(budget_config.get("daily_limit"))
                        if budget_config.get("daily_limit")
                        else None,
                        "monthly_limit": str(budget_config.get("monthly_limit"))
                        if budget_config.get("monthly_limit")
                        else None,
                    },
                },
            }

            # Send to user's private channel
            user_channel = f"private-user-{user_id}"
            self.pusher_client.trigger(
                channel=user_channel, event="initial-data", data=initial_data
            )

        except Exception as e:
            logger.error(f"Failed to send initial data to user {user_id}: {str(e)}")

    async def broadcast_cost_update(
        self, cost_data: Dict[str, Any], channel: str = Channels.COST_DASHBOARD
    ) -> None:
        """Broadcast cost update to specified channel."""
        try:
            message = {
                "type": "cost_update",
                "timestamp": datetime.now().isoformat(),
                "data": cost_data,
            }

            self.pusher_client.trigger(channel=channel, event=Events.COST_UPDATE, data=message)

        except Exception as e:
            logger.error(f"Failed to broadcast cost update: {str(e)}")

    async def send_budget_alert(
        self, alert_data: Dict[str, Any], user_id: Optional[str] = None
    ) -> None:
        """Send budget alert to specific user or broadcast."""
        try:
            message = {
                "type": "budget_alert",
                "timestamp": datetime.now().isoformat(),
                "severity": alert_data.get("severity", "info"),
                "data": alert_data,
            }

            if user_id:
                # Send to specific user
                channel = f"private-user-{user_id}"
            else:
                # Broadcast to alerts channel
                channel = Channels.BUDGET_ALERTS

            self.pusher_client.trigger(channel=channel, event=Events.BUDGET_ALERT, data=message)

        except Exception as e:
            logger.error(f"Failed to send budget alert: {str(e)}")

    def start_background_tasks(self):
        """Start background tasks for periodic updates."""
        # Note: In serverless, these should be moved to scheduled functions
        logger.info("Background tasks should be handled by Vercel Cron/QStash")

    def stop_background_tasks(self):
        """Stop background tasks."""
        for task in self._background_tasks:
            task.cancel()
        self._background_tasks.clear()


# Initialize service
realtime_service = RealtimeCostService()


@router.post("/pusher/auth")
async def pusher_auth(
    request: PusherAuthRequest, current_user: UserModel = Depends(get_current_user)
) -> JSONResponse:
    """
    Authenticate Pusher channel subscription.

    This endpoint is called by Pusher client library when subscribing
    to private or presence channels.
    """
    try:
        auth_response = await realtime_service.authenticate_channel(
            socket_id=request.socket_id, channel_name=request.channel_name, user=current_user
        )

        return JSONResponse(content=auth_response)

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Pusher auth error: {str(e)}")
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.post("/pusher/trigger")
async def trigger_event(
    request: PusherTriggerRequest, current_user: UserModel = Depends(get_current_user)
) -> JSONResponse:
    """
    Trigger a Pusher event from the server.

    This endpoint allows server-side code to trigger events on channels.
    Requires appropriate permissions.
    """
    try:
        # Validate user has permission to trigger events
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")

        # Trigger the event
        success = realtime_service.pusher_client.trigger(
            channel=request.channel,
            event=request.event,
            data=request.data,
            socket_id=request.socket_id,
        )

        return JSONResponse(content={"success": success})

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to trigger event: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to trigger event")


@router.post("/connect")
async def connect(current_user: UserModel = Depends(get_current_user)) -> JSONResponse:
    """
    Initialize connection and send initial data.

    Called when client first connects to establish real-time updates.
    """
    try:
        # Send initial data
        await realtime_service.send_initial_data(str(current_user.id))

        # Return connection info
        return JSONResponse(
            content={
                "success": True,
                "user_channel": f"private-user-{current_user.id}",
                "available_channels": [
                    Channels.COST_DASHBOARD,
                    Channels.BUDGET_ALERTS,
                    Channels.SERVICE_MONITORING,
                ],
            }
        )

    except Exception as e:
        logger.error(f"Connection initialization failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initialize connection")


@router.get("/stats")
async def get_connection_stats(current_user: UserModel = Depends(get_current_user)) -> JSONResponse:
    """Get real-time connection statistics."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        # Get channel info from Pusher
        stats = {"channels": {}}

        for channel in [Channels.COST_DASHBOARD, Channels.BUDGET_ALERTS]:
            info = realtime_service.pusher_client.get_channel_info(channel)
            if info:
                stats["channels"][channel] = info

        return JSONResponse(content=stats)

    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")


# Export for scheduled tasks (to be called by Vercel Cron)
async def scheduled_cost_update():
    """Scheduled task to broadcast cost updates."""
    try:
        today = date.today()
        daily_summary = await realtime_service.cost_manager.get_daily_summary(today)

        await realtime_service.broadcast_cost_update(
            cost_data={
                "total_cost": str(daily_summary["total_cost"]),
                "total_requests": daily_summary["total_requests"],
                "period": "daily",
            }
        )

    except Exception as e:
        logger.error(f"Scheduled cost update failed: {str(e)}")


async def scheduled_budget_check():
    """Scheduled task to check budget limits."""
    try:
        # Check budget status
        budget_status = await realtime_service.cost_manager.check_budget_status()

        if budget_status.get("alert_needed"):
            await realtime_service.send_budget_alert(alert_data=budget_status)

    except Exception as e:
        logger.error(f"Scheduled budget check failed: {str(e)}")
