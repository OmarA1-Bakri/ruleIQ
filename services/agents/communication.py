"""
Agent Communication Service - Handles inter-agent messaging and protocols.

Implements message routing, validation, and async communication.
"""

from typing import Dict, List, Optional, Any, Callable
from uuid import UUID, uuid4
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages agents can exchange."""

    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    BROADCAST = "broadcast"
    HANDOFF = "handoff"
    SYNC = "sync"
    ERROR = "error"


class MessagePriority(Enum):
    """Message priority levels."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Message:
    """Represents a message between agents."""

    message_id: UUID = field(default_factory=uuid4)
    from_agent: UUID = None
    to_agent: Optional[UUID] = None  # None for broadcasts
    message_type: MessageType = MessageType.REQUEST
    priority: MessagePriority = MessagePriority.NORMAL
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    requires_ack: bool = False
    correlation_id: Optional[UUID] = None


class CommunicationProtocol:
    """Defines communication protocol between agents."""

    def __init__(self, max_retries: int = 3, timeout: float = 30.0) -> None:
        """Initialize communication protocol."""
        self.max_retries = max_retries
        self.timeout = timeout
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.pending_messages: Dict[UUID, Message] = {}
        self.message_handlers: Dict[MessageType, List[Callable]] = defaultdict(list)
        self.agent_channels: Dict[UUID, asyncio.Queue] = {}
        self.acknowledgments: Dict[UUID, asyncio.Event] = {}

    async def send_message(self, message: Message, wait_for_ack: bool = False) -> Optional[UUID]:
        """Send a message to an agent or broadcast."""
        try:
            # Validate message
            if not self._validate_message(message):
                logger.error(f"Invalid message: {message.message_id}")
                return None

            # Add to pending if acknowledgment required
            if message.requires_ack or wait_for_ack:
                self.pending_messages[message.message_id] = message
                self.acknowledgments[message.message_id] = asyncio.Event()

            # Route message
            if message.to_agent:
                # Direct message
                if message.to_agent in self.agent_channels:
                    await self.agent_channels[message.to_agent].put(message)
                    logger.info(f"Sent message {message.message_id} to agent {message.to_agent}")
                else:
                    logger.warning(f"Agent {message.to_agent} has no channel")
                    return None
            else:
                # Broadcast message
                for agent_id, channel in self.agent_channels.items():
                    if agent_id != message.from_agent:
                        await channel.put(message)
                logger.info(
                    f"Broadcast message {message.message_id} from agent {message.from_agent}"
                )

            # Wait for acknowledgment if required
            if wait_for_ack:
                try:
                    await asyncio.wait_for(
                        self.acknowledgments[message.message_id].wait(), timeout=self.timeout
                    )
                    logger.info(f"Message {message.message_id} acknowledged")
                except asyncio.TimeoutError:
                    logger.warning(f"Message {message.message_id} acknowledgment timeout")
                    return None

            return message.message_id

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return None

    async def receive_message(
        self, agent_id: UUID, timeout: Optional[float] = None
    ) -> Optional[Message]:
        """Receive a message for an agent."""
        try:
            # Ensure agent has a channel
            if agent_id not in self.agent_channels:
                self.agent_channels[agent_id] = asyncio.Queue()

            channel = self.agent_channels[agent_id]

            # Wait for message
            if timeout:
                message = await asyncio.wait_for(channel.get(), timeout=timeout)
            else:
                message = await channel.get()

            # Check if message expired
            if message.expires_at and datetime.utcnow() > message.expires_at:
                logger.warning(f"Message {message.message_id} expired")
                return None

            # Send acknowledgment if required
            if message.requires_ack:
                await self.acknowledge_message(message.message_id)

            logger.info(f"Agent {agent_id} received message {message.message_id}")
            return message

        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Failed to receive message: {e}")
            return None

    async def acknowledge_message(self, message_id: UUID):
        """Acknowledge receipt of a message."""
        if message_id in self.acknowledgments:
            self.acknowledgments[message_id].set()
            del self.pending_messages[message_id]
            del self.acknowledgments[message_id]
            logger.info(f"Acknowledged message {message_id}")

    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register a handler for a message type."""
        self.message_handlers[message_type].append(handler)
        logger.info(f"Registered handler for {message_type}")

    async def process_message(self, message: Message) -> Optional[Message]:
        """Process a message using registered handlers."""
        handlers = self.message_handlers.get(message.message_type, [])

        response = None
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(message)
                else:
                    result = handler(message)

                if result:
                    response = result
                    break

            except Exception as e:
                logger.error(f"Handler error for message {message.message_id}: {e}")

        return response

    def _validate_message(self, message: Message) -> bool:
        """Validate message structure and content."""
        if not message.from_agent:
            logger.error("Message missing from_agent")
            return False

        if message.message_type not in MessageType:
            logger.error(f"Invalid message type: {message.message_type}")
            return False

        if message.priority not in MessagePriority:
            logger.error(f"Invalid priority: {message.priority}")
            return False

        return True

    async def request_response(
        self,
        from_agent: UUID,
        to_agent: UUID,
        request_payload: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Optional[Dict[str, Any]]:
        """Send a request and wait for response."""
        # Create request message
        request = Message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.REQUEST,
            payload=request_payload,
            requires_ack=True,
        )

        # Send request
        message_id = await self.send_message(request, wait_for_ack=True)
        if not message_id:
            return None

        # Wait for response
        try:
            response_event = asyncio.Event()
            response_data = {}

            async def response_handler(msg: Message):
                if msg.correlation_id == message_id:
                    response_data.update(msg.payload)
                    response_event.set()

            self.register_handler(MessageType.RESPONSE, response_handler)

            await asyncio.wait_for(response_event.wait(), timeout=timeout)
            return response_data

        except asyncio.TimeoutError:
            logger.warning(f"Request {message_id} timeout")
            return None

    async def broadcast_notification(
        self,
        from_agent: UUID,
        notification: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> bool:
        """Broadcast a notification to all agents."""
        message = Message(
            from_agent=from_agent,
            to_agent=None,
            message_type=MessageType.BROADCAST,
            priority=priority,
            payload=notification,
            requires_ack=False,
        )

        result = await self.send_message(message)
        return result is not None

    async def handoff_session(
        self, from_agent: UUID, to_agent: UUID, session_data: Dict[str, Any]
    ) -> bool:
        """Hand off a session from one agent to another."""
        handoff_message = Message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.HANDOFF,
            priority=MessagePriority.HIGH,
            payload={
                "session_data": session_data,
                "handoff_time": datetime.utcnow().isoformat(),
                "reason": session_data.get("handoff_reason", ""),
            },
            requires_ack=True,
        )

        result = await self.send_message(handoff_message, wait_for_ack=True)

        if result:
            logger.info(f"Session handed off from {from_agent} to {to_agent}")
            return True
        else:
            logger.error(f"Failed to hand off session from {from_agent} to {to_agent}")
            return False

    def create_agent_channel(self, agent_id: UUID) -> asyncio.Queue:
        """Create a communication channel for an agent."""
        if agent_id not in self.agent_channels:
            self.agent_channels[agent_id] = asyncio.Queue()
            logger.info(f"Created channel for agent {agent_id}")

        return self.agent_channels[agent_id]

    def close_agent_channel(self, agent_id: UUID):
        """Close an agent's communication channel."""
        if agent_id in self.agent_channels:
            del self.agent_channels[agent_id]
            logger.info(f"Closed channel for agent {agent_id}")

    async def sync_agents(
        self, agent_ids: List[UUID], sync_data: Dict[str, Any]
    ) -> Dict[UUID, bool]:
        """Synchronize data across multiple agents."""
        results = {}

        sync_message = Message(
            from_agent=UUID(int=0),  # System message
            message_type=MessageType.SYNC,
            priority=MessagePriority.HIGH,
            payload=sync_data,
            requires_ack=True,
        )

        for agent_id in agent_ids:
            sync_message.to_agent = agent_id
            result = await self.send_message(sync_message, wait_for_ack=True)
            results[agent_id] = result is not None

        successful = sum(1 for success in results.values() if success)
        logger.info(f"Synchronized {successful}/{len(agent_ids)} agents")

        return results

    def get_pending_messages(self, agent_id: Optional[UUID] = None) -> List[Message]:
        """Get pending messages for an agent or all agents."""
        if agent_id:
            return [msg for msg in self.pending_messages.values() if msg.to_agent == agent_id]
        return list(self.pending_messages.values())

    async def retry_message(self, message_id: UUID, max_retries: Optional[int] = None) -> bool:
        """Retry sending a failed message."""
        if message_id not in self.pending_messages:
            logger.warning(f"Message {message_id} not found in pending")
            return False

        message = self.pending_messages[message_id]
        retries = max_retries or self.max_retries

        for attempt in range(retries):
            logger.info(f"Retry attempt {attempt + 1}/{retries} for message {message_id}")
            result = await self.send_message(message)

            if result:
                return True

            await asyncio.sleep(2**attempt)  # Exponential backoff

        logger.error(f"Failed to retry message {message_id} after {retries} attempts")
        return False
