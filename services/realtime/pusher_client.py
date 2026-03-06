"""
Pusher client wrapper for server-side real-time event publishing.
Replaces native WebSocket broadcasts with Pusher REST API triggers.
"""

import os
import json
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime
import pusher
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PusherConfig(BaseModel):
    """Pusher configuration model."""

    app_id: str
    key: str
    secret: str
    cluster: str
    ssl: bool = True

    @classmethod
    def from_env(cls) -> "PusherConfig":
        """Load configuration from environment variables."""
        return cls(
            app_id=os.getenv("PUSHER_APP_ID", ""),
            key=os.getenv("PUSHER_KEY", ""),
            secret=os.getenv("PUSHER_SECRET", ""),
            cluster=os.getenv("PUSHER_CLUSTER", "eu"),
        )


class PusherClient:
    """
    Wrapper for Pusher REST API client.
    Handles server-side event triggering and channel management.
    """

    def __init__(self, config: Optional[PusherConfig] = None) -> None:
        """Initialize Pusher client with configuration."""
        self.config = config or PusherConfig.from_env()
        self.client = None

        if self.config.app_id and self.config.key and self.config.secret:
            self.client = pusher.Pusher(
                app_id=self.config.app_id,
                key=self.config.key,
                secret=self.config.secret,
                cluster=self.config.cluster,
                ssl=self.config.ssl,
            )
            logger.info(f"Pusher client initialized for cluster: {self.config.cluster}")
        else:
            logger.warning("Pusher credentials not found. Real-time features disabled.")

    def trigger(self, channel: str, event: str, data: Any, socket_id: Optional[str] = None) -> bool:
        """
        Trigger an event on a channel.

        Args:
            channel: Channel name (e.g., 'private-costs', 'presence-dashboard')
            event: Event name (e.g., 'cost-update', 'budget-alert')
            data: Event data to send
            socket_id: Optional socket ID to exclude from receiving the event

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            logger.debug("Pusher client not configured. Skipping event trigger.")
            return False

        try:
            # Serialize data if needed
            if isinstance(data, BaseModel):
                data = data.dict()
            elif hasattr(data, "__dict__"):
                data = data.__dict__

            # Add timestamp if not present
            if isinstance(data, dict) and "timestamp" not in data:
                data["timestamp"] = datetime.utcnow().isoformat()

            # Trigger the event
            self.client.trigger(
                channels=channel,
                event_name=event,
                data=json.dumps(data) if not isinstance(data, str) else data,
                socket_id=socket_id,
            )

            logger.debug(f"Event '{event}' triggered on channel '{channel}'")
            return True

        except Exception as e:
            logger.error(f"Failed to trigger Pusher event: {e}")
            return False

    def trigger_batch(self, events: List[Dict[str, Any]]) -> bool:
        """
        Trigger multiple events in a single API call.

        Args:
            events: List of event dictionaries with 'channel', 'name', and 'data'

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            return False

        try:
            # Format events for batch trigger
            formatted_events = []
            for event in events:
                formatted_events.append(
                    {
                        "channel": event["channel"],
                        "name": event["name"],
                        "data": json.dumps(event["data"])
                        if not isinstance(event["data"], str)
                        else event["data"],
                    }
                )

            self.client.trigger_batch(formatted_events)
            logger.debug(f"Batch triggered {len(events)} events")
            return True

        except Exception as e:
            logger.error(f"Failed to batch trigger Pusher events: {e}")
            return False

    def authenticate(
        self, channel: str, socket_id: str, custom_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate authentication response for private/presence channels.

        Args:
            channel: Channel name to authenticate
            socket_id: Client socket ID
            custom_data: Optional user data for presence channels

        Returns:
            Authentication response dict
        """
        if not self.client:
            raise ValueError("Pusher client not configured")

        try:
            if channel.startswith("presence-"):
                # Presence channel authentication
                if not custom_data:
                    raise ValueError("User data required for presence channels")

                auth = self.client.authenticate(
                    channel=channel, socket_id=socket_id, custom_data=custom_data
                )
            else:
                # Private channel authentication
                auth = self.client.authenticate(channel=channel, socket_id=socket_id)

            return auth

        except Exception as e:
            logger.error(f"Failed to authenticate Pusher channel: {e}")
            raise

    def get_channel_info(self, channel: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a channel.

        Args:
            channel: Channel name

        Returns:
            Channel information or None
        """
        if not self.client:
            return None

        try:
            info = self.client.channels_info(channel, ["user_count", "subscription_count"])
            return info
        except Exception as e:
            logger.error(f"Failed to get channel info: {e}")
            return None

    def close(self):
        """Close the Pusher client connection."""
        # Pusher client doesn't need explicit closing
        logger.info("Pusher client closed")


# Singleton instance
_pusher_client: Optional[PusherClient] = None


def get_pusher_client() -> PusherClient:
    """Get or create the singleton Pusher client instance."""
    global _pusher_client
    if _pusher_client is None:
        _pusher_client = PusherClient()
    return _pusher_client


# Channel name constants
class Channels:
    """Pusher channel name constants."""

    COST_DASHBOARD = "private-cost-dashboard"
    BUDGET_ALERTS = "private-budget-alerts"
    SERVICE_MONITORING = "private-service-monitoring"
    PRESENCE_DASHBOARD = "presence-dashboard"
    PUBLIC_UPDATES = "public-updates"


# Event name constants
class Events:
    """Pusher event name constants."""

    COST_UPDATE = "cost-update"
    BUDGET_ALERT = "budget-alert"
    COST_SPIKE = "cost-spike"
    SERVICE_STATS = "service-stats"
    FORECAST_UPDATE = "forecast-update"
    CONNECTION_UPDATE = "connection-update"
    USER_JOINED = "user-joined"
    USER_LEFT = "user-left"
