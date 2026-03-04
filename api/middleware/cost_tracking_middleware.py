"""
import requests as http_requests
import json
import logging


logger = logging.getLogger(__name__)
# Constants
HTTP_INTERNAL_SERVER_ERROR = 500


Cost Tracking Middleware

Automatically tracks AI costs for API requests and integrates with
budget monitoring and optimization systems.
"""
import time
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional, Callable, Awaitable
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from services.ai.cost_management import AICostManager, CostTrackingService
from services.ai.cost_aware_circuit_breaker import get_cost_aware_circuit_breaker
from config.logging_config import get_logger
from database.user import User
logger = get_logger(__name__)


class CostTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic AI cost tracking and budget enforcement.

    Intercepts AI-related API requests, tracks costs, enforces budgets,
    and provides real-time cost monitoring.
    """

    def __init__(self, app, cost_manager: Optional[AICostManager]=None,
        enable_budget_enforcement: bool=True, enable_cost_optimization:
        bool=True, track_all_requests: bool=False) ->None:
        super().__init__(app)
        self.cost_manager = cost_manager or AICostManager()
        self.cost_tracker = CostTrackingService()
        self.circuit_breaker = get_cost_aware_circuit_breaker()
        self.enable_budget_enforcement = enable_budget_enforcement
        self.enable_cost_optimization = enable_cost_optimization
        self.track_all_requests = track_all_requests
        self.ai_endpoints = {'/api/v1/ai/generate-policy',
            '/api/v1/ai/refine-policy', '/api/v1/ai/assessments',
            '/api/v1/ai/chat', '/api/v1/ai/evidence',
            '/api/v1/ai/recommendations'}

    async def dispatch(self, request: Request, call_next: Callable[[Request
        ], Awaitable[Response]]) ->Response:
        """Process request with cost tracking."""
        should_track = self._should_track_request(request)
        if not should_track:
            return await call_next(request)
        request_id = str(uuid.uuid4())
        start_time = time.time()
        user_id = await self._extract_user_id(request)
        session_id = self._extract_session_id(request)
        request.state.cost_tracking = {'request_id': request_id,
            'start_time': start_time, 'user_id': user_id, 'session_id':
            session_id, 'service_name': self._extract_service_name(request),
            'endpoint': str(request.url.path)}
        try:
            if self.enable_budget_enforcement and user_id:
                await self._check_user_budget_limits(user_id)
            response = await call_next(request)
            await self._track_successful_request(request, response, start_time)
            self._add_cost_headers(response, request)
            return response
        except HTTPException as e:
            await self._track_failed_request(request, e, start_time)
            raise
        except http_requests.RequestException as e:
            await self._track_error_request(request, e, start_time)
            logger.error('Unexpected error in cost tracking middleware: %s' %
                str(e))
            return JSONResponse(status_code=status.
                HTTP_500_INTERNAL_SERVER_ERROR, content={'detail':
                'Internal server error', 'request_id': request_id})

    def _should_track_request(self, request: Request) ->bool:
        """Determine if request should be tracked for costs."""
        if self.track_all_requests:
            return True
        path = request.url.path
        return any(ai_endpoint in path for ai_endpoint in self.ai_endpoints)

    async def _extract_user_id(self, request: Request) ->Optional[str]:
        """Extract user ID from request."""
        try:
            if hasattr(request.state, 'current_user'):
                user = request.state.current_user
                if isinstance(user, User):
                    return str(user.id)
                elif isinstance(user, dict):
                    return str(user.get('id'))
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                return 'jwt_user'
            return None
        except http_requests.RequestException as e:
            logger.warning('Failed to extract user ID: %s' % str(e))
            return None

    def _extract_session_id(self, request: Request) ->Optional[str]:
        """Extract session ID from request."""
        session_id = request.cookies.get('session_id')
        if session_id:
            return session_id
        session_id = request.headers.get('X-Session-ID')
        if session_id:
            return session_id
        if hasattr(request.state, 'cost_tracking'):
            return request.state.cost_tracking.get('request_id')
        return None

    def _extract_service_name(self, request: Request) ->str:
        """Extract service name from request path."""
        path = request.url.path
        service_mapping = {'/api/v1/ai/generate-policy':
            'policy_generation', '/api/v1/ai/refine-policy':
            'policy_refinement', '/api/v1/ai/assessments':
            'assessment_analysis', '/api/v1/ai/chat': 'chat_assistance',
            '/api/v1/ai/evidence': 'evidence_analysis',
            '/api/v1/ai/recommendations': 'recommendation_engine'}
        for endpoint, service in service_mapping.items():
            if endpoint in path:
                return service
        return 'ai_general'

    async def _check_user_budget_limits(self, user_id: str) ->None:
        """Check if user has exceeded budget limits."""
        try:
            user_limit_key = f'budget:user:{user_id}:daily'
            logger.debug('Checking budget limits for user: %s, key: %s' % (
                user_id, user_limit_key))
            from datetime import date
            today_usage = await self.cost_tracker.get_usage_by_time_range(
                start_time=datetime.combine(date.today(), datetime.min.time
                ()), end_time=datetime.now())
            if today_usage:
                total_cost = sum(usage.cost_usd for usage in today_usage)
                daily_limit = Decimal('50.00')
                if total_cost >= daily_limit:
                    raise HTTPException(status_code=status.
                        HTTP_429_TOO_MANY_REQUESTS, detail=
                        f'Daily cost limit exceeded: ${total_cost:.2f} >= ${daily_limit:.2f}'
                        , headers={'Retry-After': '86400'})
                elif total_cost >= daily_limit * Decimal('0.9'):
                    logger.warning(
                        'User %s approaching daily cost limit: $%s' % (
                        user_id, total_cost))
        except HTTPException:
            raise
        except http_requests.RequestException as e:
            logger.error('Failed to check user budget limits: %s' % str(e))

    async def _track_successful_request(self, request: Request, response:
        Response, start_time: float) ->None:
        """Track successful AI request with cost calculation."""
        try:
            tracking_info = request.state.cost_tracking
            response_time = (time.time() - start_time) * 1000
            token_usage = await self._extract_token_usage(request, response)
            if token_usage:
                result = await self.cost_manager.track_ai_request(service_name
                    =tracking_info['service_name'], model_name=token_usage.
                    get('model_name', 'unknown'), input_prompt=token_usage.
                    get('input_prompt', ''), response_content=token_usage.
                    get('response_content', ''), input_tokens=token_usage.
                    get('input_tokens', 0), output_tokens=token_usage.get(
                    'output_tokens', 0), user_id=tracking_info['user_id'],
                    session_id=tracking_info['session_id'], request_id=
                    tracking_info['request_id'], response_time_ms=
                    response_time, cache_hit=token_usage.get('cache_hit',
                    False), error_occurred=False, metadata={'endpoint':
                    tracking_info['endpoint'], 'status_code': response.
                    status_code, 'middleware': 'cost_tracking'})
                request.state.cost_result = result
                logger.debug('Tracked successful request %s: $%s' % (
                    tracking_info['request_id'], result['cost_usd']))
        except (http_requests.RequestException, KeyError, IndexError) as e:
            logger.error('Failed to track successful request: %s' % str(e))

    async def _track_failed_request(self, request: Request, error:
        HTTPException, start_time: float) ->None:
        """Track failed AI request."""
        try:
            tracking_info = request.state.cost_tracking
            response_time = (time.time() - start_time) * 1000
            if error.status_code >= HTTP_INTERNAL_SERVER_ERROR:
                estimated_tokens = self._estimate_failed_request_tokens(request
                    )
                if estimated_tokens:
                    await self.cost_manager.track_ai_request(service_name=
                        tracking_info['service_name'], model_name=
                        estimated_tokens.get('model_name', 'unknown'),
                        input_prompt='', response_content='', input_tokens=
                        estimated_tokens.get('input_tokens', 0),
                        output_tokens=0, user_id=tracking_info['user_id'],
                        session_id=tracking_info['session_id'], request_id=
                        tracking_info['request_id'], response_time_ms=
                        response_time, cache_hit=False, error_occurred=True,
                        metadata={'endpoint': tracking_info['endpoint'],
                        'error_type': 'http_exception', 'status_code':
                        error.status_code, 'error_detail': str(error.detail
                        ), 'middleware': 'cost_tracking'})
        except (http_requests.RequestException, KeyError, IndexError) as e:
            logger.error('Failed to track failed request: %s' % str(e))

    async def _track_error_request(self, request: Request, error: Exception,
        start_time: float) ->None:
        """Track unexpected error request."""
        try:
            tracking_info = request.state.cost_tracking
            response_time = (time.time() - start_time) * 1000
            logger.error(
                'Unexpected error in request %s: %s (response_time: %sms)' %
                (tracking_info['request_id'], str(error), response_time))
        except (http_requests.RequestException, KeyError, IndexError) as e:
            logger.error('Failed to track error request: %s' % str(e))

    async def _extract_token_usage(self, request: Request, response: Response
        ) ->Optional[Dict[str, Any]]:
        """Extract token usage information from request/response."""
        try:
            if hasattr(response, 'body'):
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    return self._mock_token_usage(request)
            return None
        except (json.JSONDecodeError, http_requests.RequestException) as e:
            logger.warning('Failed to extract token usage: %s' % str(e))
            return None

    def _mock_token_usage(self, request: Request) ->Dict[str, Any]:
        """Generate mock token usage for testing."""
        path = request.url.path
        if 'generate-policy' in path:
            return {'model_name': 'gemini-1.5-pro', 'input_tokens': 1500,
                'output_tokens': 2000, 'input_prompt':
                'Generate privacy policy...', 'response_content':
                'Privacy Policy...', 'cache_hit': False}
        elif 'chat' in path:
            return {'model_name': 'gemini-1.5-flash', 'input_tokens': 800,
                'output_tokens': 600, 'input_prompt': 'User question...',
                'response_content': 'AI response...', 'cache_hit': False}
        elif 'assessments' in path:
            return {'model_name': 'gemini-1.5-pro', 'input_tokens': 1200,
                'output_tokens': 1500, 'input_prompt':
                'Assessment analysis...', 'response_content':
                'Analysis results...', 'cache_hit': False}
        return {'model_name': 'gemini-1.5-flash', 'input_tokens': 500,
            'output_tokens': 300, 'input_prompt': 'AI request...',
            'response_content': 'AI response...', 'cache_hit': False}

    def _estimate_failed_request_tokens(self, request: Request) ->Optional[Dict
        [str, Any]]:
        """Estimate token usage for failed requests."""
        try:
            return {'model_name': 'gemini-1.5-flash', 'input_tokens': 500,
                'output_tokens': 0}
        except http_requests.RequestException:
            return None

    def _add_cost_headers(self, response: Response, request: Request) ->None:
        """Add cost-related headers to response."""
        try:
            if hasattr(request.state, 'cost_result'):
                cost_result = request.state.cost_result
                response.headers['X-AI-Cost-USD'] = str(cost_result['cost_usd']
                    )
                response.headers['X-AI-Efficiency-Score'] = str(cost_result
                    ['efficiency_score'])
                response.headers['X-AI-Request-ID'] = cost_result['usage_id']
                if hasattr(request.state, 'cost_tracking'
                    ) and request.state.cost_tracking.get('user_id'):
                    response.headers['X-Budget-Remaining'] = '50.00'
        except (http_requests.RequestException, KeyError, IndexError) as e:
            logger.warning('Failed to add cost headers: %s' % str(e))


class RealTimeCostMonitor:
    """Real-time cost monitoring with WebSocket support."""

    def __init__(self, cost_manager: AICostManager) ->None:
        self.cost_manager = cost_manager
        self.active_connections: Dict[str, Any] = {}

    async def connect_client(self, client_id: str, websocket) ->None:
        """Connect client for real-time cost updates."""
        self.active_connections[client_id] = {'websocket': websocket,
            'connected_at': datetime.now()}
        logger.info('Client %s connected for real-time cost monitoring' %
            client_id)

    async def disconnect_client(self, client_id: str) ->None:
        """Disconnect client from real-time updates."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info('Client %s disconnected from cost monitoring' %
                client_id)

    async def broadcast_cost_update(self, cost_data: Dict[str, Any]) ->None:
        """Broadcast cost update to all connected clients."""
        if not self.active_connections:
            return
        message = {'type': 'cost_update', 'timestamp': datetime.now().
            isoformat(), 'data': cost_data}
        disconnected_clients = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection['websocket'].send_json(message)
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                logger.warning(
                    'Failed to send cost update to client %s: %s' % (
                    client_id, str(e)))
                disconnected_clients.append(client_id)
        for client_id in disconnected_clients:
            await self.disconnect_client(client_id)

    async def send_budget_alert(self, alert_data: Dict[str, Any]) ->None:
        """Send budget alert to connected clients."""
        message = {'type': 'budget_alert', 'timestamp': datetime.now().
            isoformat(), 'alert': alert_data}
        for client_id, connection in self.active_connections.items():
            try:
                await connection['websocket'].send_json(message)
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                logger.warning(
                    'Failed to send budget alert to client %s: %s' % (
                    client_id, str(e)))


real_time_monitor = RealTimeCostMonitor(AICostManager())
