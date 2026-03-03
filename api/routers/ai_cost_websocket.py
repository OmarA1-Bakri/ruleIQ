"""
import logging


logger = logging.getLogger(__name__)
Real-time AI Cost Monitoring WebSocket API

Provides WebSocket endpoints for real-time cost monitoring, budget alerts,
and live cost analytics dashboards.
"""
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from api.dependencies.auth import verify_websocket_token
from api.dependencies.websocket_auth import (
    verify_websocket_token_from_headers
)
from middleware.websocket_security import websocket_security
from fastapi.websockets import WebSocketState
from pydantic import BaseModel
from services.ai.cost_management import AICostManager, CostTrackingService
from config.logging_config import get_logger
import contextlib
logger = get_logger(__name__)
router = APIRouter(tags=['AI Cost WebSocket'])


class WebSocketMessage(BaseModel):
    """Base WebSocket message structure."""
    type: str
    timestamp: str
    data: Dict[str, Any]


class CostUpdateMessage(WebSocketMessage):
    """Real-time cost update message."""
    type: str = 'cost_update'


class BudgetAlertMessage(WebSocketMessage):
    """Budget alert message."""
    type: str = 'budget_alert'


class ConnectionManager:
    """Manages WebSocket connections for real-time cost monitoring."""

    def __init__(self) ->None:
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        self.user_connections: Dict[str, List[str]] = {}
        self.cost_manager = AICostManager()
        self.cost_tracker = CostTrackingService()

    async def connect(self, websocket: WebSocket, user_id: str,
        connection_type: str='dashboard') ->str:
        """Accept new WebSocket connection."""
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        self.active_connections[connection_id] = {'websocket': websocket,
            'user_id': user_id, 'connection_type': connection_type,
            'connected_at': datetime.now(), 'last_ping': datetime.now(),
            'subscriptions': set()}
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(connection_id)
        logger.info('WebSocket connection %s established for user %s' % (
            connection_id, user_id))
        await self._send_initial_data(connection_id)
        return connection_id

    async def disconnect(self, connection_id: str) ->None:
        """Remove WebSocket connection."""
        if connection_id in self.active_connections:
            connection = self.active_connections[connection_id]
            user_id = connection['user_id']
            if user_id in self.user_connections:
                self.user_connections[user_id] = [cid for cid in self.
                    user_connections[user_id] if cid != connection_id]
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            del self.active_connections[connection_id]
            logger.info('WebSocket connection %s disconnected' % connection_id)

    async def _send_initial_data(self, connection_id: str) ->None:
        """Send initial cost data to newly connected client."""
        try:
            connection = self.active_connections[connection_id]
            connection['user_id']
            from datetime import date
            today = date.today()
            daily_summary = await self.cost_manager.get_daily_summary(today)
            trends = await self.cost_tracker.get_cost_trends(7)
            budget_config = (await self.cost_manager.budget_service.
                get_current_budget())
            initial_data = {'daily_summary': {'total_cost': str(
                daily_summary['total_cost']), 'total_requests':
                daily_summary['total_requests'], 'total_tokens':
                daily_summary['total_tokens'], 'service_breakdown': {k: {
                'cost': str(v['cost']) if isinstance(v, dict) else str(v),
                'requests': v.get('requests', 0) if isinstance(v, dict) else
                0} for k, v in daily_summary.get('service_breakdown', {}).
                items()}}, 'cost_trends': [{'date': trend['date'], 'cost':
                str(trend['cost']), 'requests': trend['requests']} for
                trend in trends], 'budget_status': {'daily_limit': str(
                budget_config.get('daily_limit')) if budget_config.get(
                'daily_limit') else None, 'monthly_limit': str(
                budget_config.get('monthly_limit')) if budget_config.get(
                'monthly_limit') else None}}
            await self.send_personal_message(connection_id, {'type':
                'initial_data', 'timestamp': datetime.now().isoformat(),
                'data': initial_data})
        except Exception as e:
            logger.error('Failed to send initial data to %s: %s' % (
                connection_id, str(e)))

    async def send_personal_message(self, connection_id: str, message: Dict
        [str, Any]) ->None:
        """Send message to specific connection."""
        if connection_id in self.active_connections:
            try:
                websocket = self.active_connections[connection_id]['websocket']
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(json.dumps(message))
                else:
                    await self.disconnect(connection_id)
            except Exception as e:
                logger.error('Failed to send message to %s: %s' % (
                    connection_id, str(e)))
                await self.disconnect(connection_id)

    async def send_to_user(self, user_id: str, message: Dict[str, Any]) ->None:
        """Send message to all connections for a specific user."""
        if user_id in self.user_connections:
            for connection_id in self.user_connections[user_id].copy():
                await self.send_personal_message(connection_id, message)

    async def broadcast(self, message: Dict[str, Any], connection_type:
        Optional[str]=None) ->None:
        """Broadcast message to all connections or specific connection type."""
        disconnected = []
        for connection_id, connection in self.active_connections.items():
            if connection_type and connection['connection_type'
                ] != connection_type:
                continue
            try:
                websocket = connection['websocket']
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(json.dumps(message))
                else:
                    disconnected.append(connection_id)
            except Exception as e:
                logger.error('Failed to broadcast to %s: %s' % (
                    connection_id, str(e)))
                disconnected.append(connection_id)
        for connection_id in disconnected:
            await self.disconnect(connection_id)

    async def subscribe_to_events(self, connection_id: str, event_types:
        List[str]) ->None:
        """Subscribe connection to specific event types."""
        if connection_id in self.active_connections:
            self.active_connections[connection_id]['subscriptions'].update(
                event_types)

    async def unsubscribe_from_events(self, connection_id: str, event_types:
        List[str]) ->None:
        """Unsubscribe connection from specific event types."""
        if connection_id in self.active_connections:
            for event_type in event_types:
                self.active_connections[connection_id]['subscriptions'
                    ].discard(event_type)

    async def ping_connections(self) ->None:
        """Send ping to all connections to keep them alive."""
        ping_message = {'type': 'ping', 'timestamp': datetime.now().
            isoformat(), 'data': {}}
        await self.broadcast(ping_message)

    def get_connection_stats(self) ->Dict[str, Any]:
        """Get statistics about active connections."""
        total_connections = len(self.active_connections)
        users_connected = len(self.user_connections)
        connection_types = {}
        for connection in self.active_connections.values():
            conn_type = connection['connection_type']
            connection_types[conn_type] = connection_types.get(conn_type, 0
                ) + 1
        return {'total_connections': total_connections, 'users_connected':
            users_connected, 'connection_types': connection_types,
            'connections_by_user': {user_id: len(connections) for user_id,
            connections in self.user_connections.items()}}


connection_manager = ConnectionManager()


@router.websocket('/realtime-dashboard')
async def realtime_cost_dashboard(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description='JWT token for authentication (deprecated - use headers)'),
    dashboard_type: str = Query('general', description='Type of dashboard (general, admin, service)')
) -> None:
    """
    WebSocket endpoint for real-time cost monitoring dashboard.

    Provides live updates of cost metrics, budget status, and alerts.
    Requires JWT authentication via headers (preferred) or query parameter (deprecated).

    Authentication Headers:
    - Authorization: Bearer <token>
    - X-Auth-Token: <token>
    - Sec-WebSocket-Protocol: token.<token>
    """
    connection_id = str(uuid.uuid4())

    # Validate connection security
    if not await websocket_security.validate_connection(websocket, connection_id):
        return

    # Authenticate user - prefer headers, fallback to query for compatibility
    try:
        # Try header authentication first
        user = await verify_websocket_token_from_headers(websocket)

        # Fallback to query parameter if header auth fails
        if not user and token:
            logger.warning("Using deprecated query parameter authentication for WebSocket")
            user = await verify_websocket_token(websocket, token)

        if not user:
            logger.warning("WebSocket authentication failed")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        user_id = str(user.id)
    except Exception as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        connection_id = await connection_manager.connect(websocket=
            websocket, user_id=user_id, connection_type=
            f'dashboard_{dashboard_type}')
        logger.info('User %s connected to real-time cost dashboard (%s)' %
            (user_id, dashboard_type))
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(),
                    timeout=30.0)
                data = json.loads(message)
                await handle_websocket_message(connection_id, data)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({'type': 'ping',
                    'timestamp': datetime.now().isoformat(), 'data': {}}))
            except WebSocketDisconnect:
                logger.info('User %s disconnected from cost dashboard' %
                    user_id)
                break
    except Exception as e:
        logger.error('Error in realtime cost dashboard for user %s: %s' % (
            user_id, str(e)))
    finally:
        if connection_id:
            await connection_manager.disconnect(connection_id)


@router.websocket('/budget-alerts')
async def budget_alerts_websocket(websocket: WebSocket) ->None:
    """
    WebSocket endpoint for real-time budget alerts.

    Sends immediate notifications when budget thresholds are exceeded.
    Requires JWT authentication via headers.

    Authentication Headers:
    - Authorization: Bearer <token>
    - X-Auth-Token: <token>
    - Sec-WebSocket-Protocol: token.<token>
    """
    connection_id = None

    # Authenticate user via headers
    try:
        user = await verify_websocket_token_from_headers(websocket)
        if not user:
            logger.warning("Budget alerts WebSocket authentication failed")
            return

        user_id = str(user.id)
        connection_id = await connection_manager.connect(websocket=
            websocket, user_id=user_id, connection_type='budget_alerts')
        await connection_manager.subscribe_to_events(connection_id, [
            'budget_alert', 'cost_spike'])
        logger.info('User %s connected to budget alerts WebSocket' % user_id)
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(),
                    timeout=60.0)
                data = json.loads(message)
                if data.get('type') == 'subscribe':
                    event_types = data.get('events', [])
                    await connection_manager.subscribe_to_events(connection_id,
                        event_types)
                elif data.get('type') == 'unsubscribe':
                    event_types = data.get('events', [])
                    await connection_manager.unsubscribe_from_events(
                        connection_id, event_types)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({'type': 'ping',
                    'timestamp': datetime.now().isoformat(), 'data': {}}))
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error('Error in budget alerts WebSocket for user %s: %s' % (
            user_id, str(e)))
    finally:
        if connection_id:
            await connection_manager.disconnect(connection_id)


@router.websocket('/service-monitoring/{service_name}')
async def service_cost_monitoring(websocket: WebSocket, service_name: str) ->None:
    """
    WebSocket endpoint for monitoring specific service costs.

    Provides real-time cost updates for a specific AI service.
    Requires JWT authentication via headers.

    Authentication Headers:
    - Authorization: Bearer <token>
    - X-Auth-Token: <token>
    - Sec-WebSocket-Protocol: token.<token>
    """
    connection_id = None

    # Authenticate user via headers
    try:
        user = await verify_websocket_token_from_headers(websocket)
        if not user:
            logger.warning(f"Service monitoring WebSocket authentication failed for {service_name}")
            return

        user_id = str(user.id)
        connection_id = await connection_manager.connect(websocket=
            websocket, user_id=user_id, connection_type=
            f'service_{service_name}')
        logger.info('User %s connected to service monitoring for %s' % (
            user_id, service_name))
        await send_service_initial_data(connection_id, service_name)
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(),
                    timeout=30.0)
                data = json.loads(message)
                if data.get('type') == 'get_service_stats':
                    await send_service_stats(connection_id, service_name)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({'type': 'ping',
                    'timestamp': datetime.now().isoformat(), 'data': {}}))
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error('Error in service monitoring WebSocket for %s: %s' % (
            service_name, str(e)))
    finally:
        if connection_id:
            await connection_manager.disconnect(connection_id)


async def handle_websocket_message(connection_id: str, message: Dict[str, Any]
    ) ->None:
    """Handle incoming WebSocket messages."""
    message_type = message.get('type')
    if message_type == 'subscribe':
        event_types = message.get('events', [])
        await connection_manager.subscribe_to_events(connection_id, event_types,
            )
    elif message_type == 'unsubscribe':
        event_types = message.get('events', [])
        await connection_manager.unsubscribe_from_events(connection_id,
            event_types)
    elif message_type == 'get_current_stats':
        await send_current_stats(connection_id)
    elif message_type == 'get_cost_forecast':
        await send_cost_forecast(connection_id)
    elif message_type == 'pong':
        if connection_id in connection_manager.active_connections:
            connection_manager.active_connections[connection_id]['last_ping'
                ] = datetime.now()


async def send_current_stats(connection_id: str) ->None:
    """Send current cost statistics to connection."""
    try:
        from datetime import date
        today = date.today()
        daily_summary = (await connection_manager.cost_manager.
            get_daily_summary(today))
        hourly_costs = {}
        stats_message = {'type': 'current_stats', 'timestamp': datetime.now
            ().isoformat(), 'data': {'daily_total': str(daily_summary[
            'total_cost']), 'hourly_breakdown': hourly_costs,
            'top_services': daily_summary.get('service_breakdown', {}),
            'efficiency_metrics': daily_summary.get('efficiency_metrics', {})}}
        await connection_manager.send_personal_message(connection_id,
            stats_message)
    except Exception as e:
        logger.error('Failed to send current stats: %s' % str(e))


async def send_cost_forecast(connection_id: str) ->None:
    """Send cost forecast to connection."""
    try:
        forecast_data = {'next_7_days': [{'date': (datetime.now() +
            timedelta(days=i)).date().isoformat(), 'predicted_cost':
            f'{25.0 + i * 2.5:.2f}'} for i in range(7)], 'confidence_level':
            85.5, 'factors': ['increasing usage', 'new user onboarding',
            'seasonal patterns']}
        forecast_message = {'type': 'cost_forecast', 'timestamp': datetime.
            now().isoformat(), 'data': forecast_data}
        await connection_manager.send_personal_message(connection_id,
            forecast_message)
    except Exception as e:
        logger.error('Failed to send cost forecast: %s' % str(e))


async def send_service_initial_data(connection_id: str, service_name: str
    ) ->None:
    """Send initial data for service monitoring."""
    try:
        from datetime import date, timedelta
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        service_usage = (await connection_manager.cost_tracker.
            get_usage_by_service(service_name=service_name, start_date=
            start_date, end_date=end_date))
        total_cost = sum(usage.cost_usd for usage in service_usage)
        total_requests = sum(usage.request_count for usage in service_usage)
        service_data = {'service_name': service_name, 'total_cost_7d': str(
            total_cost), 'total_requests_7d': total_requests,
            'average_cost_per_request': str(total_cost / total_requests) if
            total_requests > 0 else '0', 'daily_breakdown': [{'date': usage
            .timestamp.date().isoformat(), 'cost': str(usage.cost_usd),
            'requests': usage.request_count} for usage in service_usage]}
        message = {'type': 'service_initial_data', 'timestamp': datetime.
            now().isoformat(), 'data': service_data}
        await connection_manager.send_personal_message(connection_id, message)
    except Exception as e:
        logger.error('Failed to send service initial data: %s' % str(e))


async def send_service_stats(connection_id: str, service_name: str) ->None:
    """Send current service statistics."""
    try:
        stats = {'current_hour_cost': '12.45', 'requests_this_hour': 156,
            'average_response_time': 1250.5, 'error_rate': 2.3,
            'cache_hit_rate': 78.5}
        message = {'type': 'service_stats', 'timestamp': datetime.now().
            isoformat(), 'data': {'service_name': service_name, **stats}}
        await connection_manager.send_personal_message(connection_id, message)
    except Exception as e:
        logger.error('Failed to send service stats: %s' % str(e))


async def broadcast_cost_updates() ->None:
    """Background task to broadcast real-time cost updates."""
    while True:
        try:
            from datetime import date
            today = date.today()
            daily_summary = (await connection_manager.cost_manager.
                get_daily_summary(today))
            update_message = {'type': 'cost_update', 'timestamp': datetime.
                now().isoformat(), 'data': {'current_daily_cost': str(
                daily_summary['total_cost']), 'requests_today':
                daily_summary['total_requests'], 'last_hour_cost': '5.25',
                'cost_trend': 'stable'}}
            await connection_manager.broadcast(update_message, 'dashboard')
            await asyncio.sleep(30)
        except Exception as e:
            logger.error('Error in broadcast cost updates: %s' % str(e))
            await asyncio.sleep(60)


_background_task: Optional[asyncio.Task] = None


async def start_websocket_background_tasks() ->None:
    """Start background tasks for WebSocket cost monitoring.

    This should be called during application startup.
    """
    global _background_task
    if _background_task is None or _background_task.done():
        _background_task = asyncio.create_task(broadcast_cost_updates())
        logger.info('Started WebSocket cost monitoring background task')
    else:
        logger.warning('WebSocket background task already running')


async def stop_websocket_background_tasks() ->None:
    """Stop background tasks for WebSocket cost monitoring.

    This should be called during application shutdown.
    """
    global _background_task
    if _background_task and not _background_task.done():
        _background_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _background_task
        logger.info('Stopped WebSocket cost monitoring background task')


@router.post('/admin/background-tasks/start')
async def start_background_tasks() ->Dict[str, Any]:
    """Start WebSocket background tasks manually."""
    await start_websocket_background_tasks()
    return {'message': 'Background tasks started'}


@router.post('/admin/background-tasks/stop')
async def stop_background_tasks() ->Dict[str, Any]:
    """Stop WebSocket background tasks manually."""
    await stop_websocket_background_tasks()
    return {'message': 'Background tasks stopped'}


@router.get('/connections/stats')
async def get_connection_stats() ->Any:
    """Get statistics about active WebSocket connections."""
    return connection_manager.get_connection_stats()


@router.post('/broadcast/alert')
async def broadcast_budget_alert(alert_data: Dict[str, Any]) ->Dict[str, Any]:
    """Broadcast budget alert to all connected clients."""
    alert_message = {'type': 'budget_alert', 'timestamp': datetime.now().
        isoformat(), 'data': alert_data}
    await connection_manager.broadcast(alert_message, 'dashboard')
    await connection_manager.broadcast(alert_message, 'budget_alerts')
    return {'message': 'Alert broadcasted successfully'}


@router.post('/broadcast/cost-spike')
async def broadcast_cost_spike(spike_data: Dict[str, Any]) ->Dict[str, Any]:
    """Broadcast cost spike alert to connected clients."""
    spike_message = {'type': 'cost_spike', 'timestamp': datetime.now().
        isoformat(), 'data': spike_data}
    await connection_manager.broadcast(spike_message)
    return {'message': 'Cost spike alert broadcasted successfully'}
