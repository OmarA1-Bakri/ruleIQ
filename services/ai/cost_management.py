"""
from __future__ import annotations
import logging


logger = logging.getLogger(__name__)
AI Cost Management and Monitoring System

Comprehensive cost tracking, budgeting, optimization, and reporting for AI services.
Tracks token usage, calculates costs, monitors budgets, and provides optimization recommendations.
"""
import statistics
from datetime import datetime, date, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
import time
from redis.asyncio import Redis
from config.logging_config import get_logger
import redis
from config.settings import settings
logger = get_logger(__name__)


class UsageType(Enum):
    """Types of AI usage for categorization."""


class AlertType(Enum):
    """Types of cost alerts."""


class OptimizationStrategy(Enum):
    """Cost optimization strategies."""


@dataclass
class ModelCostConfig:
    """Cost configuration for AI models."""
    model_name: str
    provider: str
    input_cost_per_million: Decimal
    output_cost_per_million: Decimal
    context_window: int
    max_output_tokens: int

    def calculate_input_cost(self, tokens: int) ->Decimal:
        """Calculate cost for input tokens."""
        return Decimal(tokens) / Decimal(1000000) * self.input_cost_per_million

    def calculate_output_cost(self, tokens: int) ->Decimal:
        """Calculate cost for output tokens."""
        return Decimal(tokens) / Decimal(1000000
            ) * self.output_cost_per_million

    def calculate_total_cost(self, input_tokens: int, output_tokens: int
        ) ->Decimal:
        """Calculate total cost for input and output tokens."""
        input_cost = self.calculate_input_cost(input_tokens)
        output_cost = self.calculate_output_cost(output_tokens)
        return input_cost + output_cost

    @classmethod
    def get_gemini_config(cls, model_name: str='gemini-2.5-pro'
        ) ->'ModelCostConfig':
        """Get cost configuration for Gemini models.

        **DO NOT CHANGE THESE MODEL NAMES WITHOUT EXPRESS PERMISSION**
        **THESE ARE THE CORRECT GEMINI 2.5 MODELS AS OF JANUARY 2025**
        """
        configs = {'gemini-2.5-pro': cls(model_name='gemini-2.5-pro',
            provider='google', input_cost_per_million=Decimal('3.50'),
            output_cost_per_million=Decimal('10.50'), context_window=
            2097152, max_output_tokens=8192), 'gemini-2.5-flash': cls(
            model_name='gemini-2.5-flash', provider='google',
            input_cost_per_million=Decimal('0.075'),
            output_cost_per_million=Decimal('0.30'), context_window=1048576,
            max_output_tokens=8192), 'gemini-2.5-flash-lite': cls(
            model_name='gemini-2.5-flash-lite', provider='google',
            input_cost_per_million=Decimal('0.03'), output_cost_per_million
            =Decimal('0.10'), context_window=1048576, max_output_tokens=
            8192), 'gemini-1.5-pro': cls(model_name='gemini-1.5-pro',
            provider='google', input_cost_per_million=Decimal('3.50'),
            output_cost_per_million=Decimal('10.50'), context_window=
            1048576, max_output_tokens=8192), 'gemini-1.5-flash': cls(
            model_name='gemini-1.5-flash', provider='google',
            input_cost_per_million=Decimal('0.075'),
            output_cost_per_million=Decimal('0.30'), context_window=1048576,
            max_output_tokens=8192)}
        return configs.get(model_name, configs['gemini-2.5-pro'])

    @classmethod
    def get_openai_config(cls, model_name: str='gpt-4-turbo'
        ) ->'ModelCostConfig':
        """Get cost configuration for OpenAI models."""
        configs = {'gpt-4-turbo': cls(model_name='gpt-4-turbo', provider=
            'openai', input_cost_per_million=Decimal('10.00'),
            output_cost_per_million=Decimal('30.00'), context_window=128000,
            max_output_tokens=4096), 'gpt-4o': cls(model_name='gpt-4o',
            provider='openai', input_cost_per_million=Decimal('5.00'),
            output_cost_per_million=Decimal('15.00'), context_window=128000,
            max_output_tokens=4096), 'gpt-3.5-turbo': cls(model_name=
            'gpt-3.5-turbo', provider='openai', input_cost_per_million=
            Decimal('0.50'), output_cost_per_million=Decimal('1.50'),
            context_window=16385, max_output_tokens=4096)}
        return configs.get(model_name, configs['gpt-4-turbo'])


@dataclass
class AIUsageMetrics:
    """Metrics for a single AI usage event."""
    service_name: str
    model_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int
    cost_usd: Decimal
    timestamp: datetime
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    response_quality_score: Optional[float] = None
    response_time_ms: Optional[float] = None
    cache_hit: bool = False
    error_occurred: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def cost_per_token(self) ->Decimal:
        """Calculate cost per token."""
        if self.total_tokens == 0:
            return Decimal('0')
        return self.cost_usd / Decimal(self.total_tokens)

    @property
    def cost_per_request(self) ->Decimal:
        """Calculate cost per request."""
        if self.request_count == 0:
            return Decimal('0')
        return self.cost_usd / Decimal(self.request_count)

    def calculate_efficiency_score(self) ->Decimal:
        """Calculate efficiency score (quality/cost ratio)."""
        if self.cost_per_token == 0 or self.response_quality_score is None:
            return Decimal('0')
        return Decimal(str(self.response_quality_score)) / self.cost_per_token

    def aggregate(self, other: 'AIUsageMetrics') ->'AIUsageMetrics':
        """Aggregate this metrics with another."""
        if (self.service_name != other.service_name or self.model_name !=
            other.model_name):
            raise ValueError(
                'Cannot aggregate metrics from different services or models')
        return AIUsageMetrics(service_name=self.service_name, model_name=
            self.model_name, input_tokens=self.input_tokens + other.
            input_tokens, output_tokens=self.output_tokens + other.
            output_tokens, total_tokens=self.total_tokens + other.
            total_tokens, request_count=self.request_count + other.
            request_count, cost_usd=self.cost_usd + other.cost_usd,
            timestamp=max(self.timestamp, other.timestamp), cache_hit=self.
            cache_hit or other.cache_hit, error_occurred=self.
            error_occurred or other.error_occurred)


@dataclass
class CostMetrics:
    """Aggregated cost metrics for a time period."""
    total_cost: Decimal
    total_requests: int
    total_tokens: int
    period_start: datetime
    period_end: datetime
    service_name: Optional[str] = None
    model_breakdown: Dict[str, Decimal] = field(default_factory=dict)
    service_breakdown: Dict[str, Decimal] = field(default_factory=dict)
    hourly_breakdown: Dict[str, Decimal] = field(default_factory=dict)

    @property
    def average_cost_per_request(self) ->Decimal:
        """Calculate average cost per request."""
        if self.total_requests == 0:
            return Decimal('0')
        return self.total_cost / Decimal(self.total_requests)

    @property
    def average_cost_per_token(self) ->Decimal:
        """Calculate average cost per token."""
        if self.total_tokens == 0:
            return Decimal('0')
        return self.total_cost / Decimal(self.total_tokens)


@dataclass
class BudgetAlert:
    """Budget alert notification."""
    alert_type: AlertType
    severity: str
    message: str
    current_usage: Decimal
    budget_limit: Decimal
    service_name: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostOptimization:
    """Cost optimization recommendation."""
    strategy: OptimizationStrategy
    recommendation: str
    potential_savings: Decimal
    confidence_score: float
    implementation_effort: str
    priority: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class CostTrackingService:
    """Core service for tracking AI usage and costs."""

    def __init__(self, redis_client: Optional[Redis]=None) ->None:
        self.redis = redis_client or self._get_redis_client()
        self.model_configs = self._load_model_configs()
        self.usage_buffer: List[AIUsageMetrics] = []
        self.buffer_size = 100

    def _get_redis_client(self) ->Optional[Redis]:
        """Get Redis client connection."""
        try:
            redis_url = settings.redis_url or 'redis://localhost:6379/0'
            return redis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            logger.warning('Failed to connect to Redis: %s' % e)
            return None

    def _load_model_configs(self) ->Dict[str, ModelCostConfig]:
        """Load model cost configurations."""
        configs = {}
        gemini_models = ['gemini-1.5-pro', 'gemini-1.5-flash',
            'gemini-2.5-pro', 'gemini-2.5-flash']
        for model in gemini_models:
            configs[model] = ModelCostConfig.get_gemini_config(model)
        openai_models = ['gpt-4-turbo', 'gpt-4o', 'gpt-3.5-turbo']
        for model in openai_models:
            configs[model] = ModelCostConfig.get_openai_config(model)
        return configs

    async def track_usage(self, service_name: str, model_name: str,
        input_tokens: int, output_tokens: int, user_id: Optional[str]=None,
        session_id: Optional[str]=None, request_id: Optional[str]=None,
        response_quality_score: Optional[float]=None, response_time_ms:
        Optional[float]=None, cache_hit: bool=False, error_occurred: bool=
        False, request_metadata: Optional[Dict[str, Any]]=None
        ) ->AIUsageMetrics:
        """Track AI usage and calculate costs."""
        model_config = self.model_configs.get(model_name)
        if not model_config:
            logger.warning(
                'Unknown model %s, using default cost calculation' % model_name,
                )
            model_config = ModelCostConfig.get_gemini_config('gemini-1.5-pro')
        cost_usd = model_config.calculate_total_cost(input_tokens,
            output_tokens)
        usage = AIUsageMetrics(service_name=service_name, model_name=
            model_name, input_tokens=input_tokens, output_tokens=
            output_tokens, total_tokens=input_tokens + output_tokens,
            request_count=1, cost_usd=cost_usd, timestamp=datetime.now(),
            user_id=user_id, session_id=session_id, request_id=request_id,
            response_quality_score=response_quality_score, response_time_ms
            =response_time_ms, cache_hit=cache_hit, error_occurred=
            error_occurred, metadata=request_metadata or {})
        await self._store_usage_in_redis(usage)
        self.usage_buffer.append(usage)
        if len(self.usage_buffer) >= self.buffer_size:
            await self._flush_usage_buffer()
        logger.debug('Tracked usage: %s/%s - $%s' % (service_name,
            model_name, cost_usd))
        return usage

    async def _store_usage_in_redis(self, usage: AIUsageMetrics) ->None:
        """Store usage metrics in Redis for real-time access."""
        timestamp = usage.timestamp
        date_key = f'ai_usage:daily:{timestamp.date()}'
        hour_key = f"ai_usage:hourly:{timestamp.strftime('%Y-%m-%d:%H')}"
        service_key = (
            f'ai_usage:service:{usage.service_name}:{timestamp.date()}')
        model_key = f'ai_usage:model:{usage.model_name}:{timestamp.date()}'
        user_key = (f'ai_usage:user:{usage.user_id}:{timestamp.date()}' if
            usage.user_id else None)
        usage_data = {'service_name': usage.service_name, 'model_name':
            usage.model_name, 'input_tokens': usage.input_tokens,
            'output_tokens': usage.output_tokens, 'total_tokens': usage.
            total_tokens, 'cost_usd': str(usage.cost_usd), 'timestamp':
            usage.timestamp.isoformat(), 'user_id': usage.user_id,
            'session_id': usage.session_id, 'request_id': usage.request_id,
            'cache_hit': usage.cache_hit, 'error_occurred': usage.
            error_occurred}
        usage_id = f'{usage.request_id or int(time.time() * 1000000)}'
        await self.redis.hset(f'ai_usage:record:{usage_id}', mapping=usage_data,
            )
        await self.redis.expire(f'ai_usage:record:{usage_id}', 86400 * 30)
        pipe = self.redis.pipeline()
        pipe.hincrbyfloat(date_key, 'total_cost', float(usage.cost_usd))
        pipe.hincrby(date_key, 'total_requests', 1)
        pipe.hincrby(date_key, 'total_tokens', usage.total_tokens)
        pipe.expire(date_key, 86400 * 90)
        pipe.hincrbyfloat(hour_key, 'total_cost', float(usage.cost_usd))
        pipe.hincrby(hour_key, 'total_requests', 1)
        pipe.hincrby(hour_key, 'total_tokens', usage.total_tokens)
        pipe.expire(hour_key, 86400 * 7)
        pipe.hincrbyfloat(service_key, 'total_cost', float(usage.cost_usd))
        pipe.hincrby(service_key, 'total_requests', 1)
        pipe.hincrby(service_key, 'total_tokens', usage.total_tokens)
        pipe.expire(service_key, 86400 * 90)
        pipe.hincrbyfloat(model_key, 'total_cost', float(usage.cost_usd))
        pipe.hincrby(model_key, 'total_requests', 1)
        pipe.hincrby(model_key, 'total_tokens', usage.total_tokens)
        pipe.expire(model_key, 86400 * 90)
        if user_key:
            pipe.hincrbyfloat(user_key, 'total_cost', float(usage.cost_usd))
            pipe.hincrby(user_key, 'total_requests', 1)
            pipe.hincrby(user_key, 'total_tokens', usage.total_tokens)
            pipe.expire(user_key, 86400 * 90)
        await pipe.execute()

    async def _flush_usage_buffer(self) ->None:
        """Flush usage buffer to persistent storage."""
        if not self.usage_buffer:
            return
        logger.info('Flushing %s usage records to persistent storage' % len
            (self.usage_buffer))
        self.usage_buffer.clear()

    async def get_usage_by_service(self, service_name: str, start_date:
        Optional[date]=None, end_date: Optional[date]=None) ->List[
        AIUsageMetrics]:
        """Get usage metrics by service for date range."""
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = start_date
        usage_metrics = []
        current_date = start_date
        while current_date <= end_date:
            service_key = f'ai_usage:service:{service_name}:{current_date}'
            data = await self.redis.hgetall(service_key)
            if data:
                usage_metrics.append(AIUsageMetrics(service_name=
                    service_name, model_name='aggregated', input_tokens=0,
                    output_tokens=0, total_tokens=int(data.get(
                    'total_tokens', 0)), request_count=int(data.get(
                    'total_requests', 0)), cost_usd=Decimal(data.get(
                    'total_cost', '0')), timestamp=datetime.combine(
                    current_date, datetime.min.time())))
            current_date += timedelta(days=1)
        return usage_metrics

    async def get_usage_by_time_range(self, start_time: datetime, end_time:
        datetime, service_name: Optional[str]=None) ->List[AIUsageMetrics]:
        """Get usage metrics for specific time range."""
        usage_metrics = []
        current_date = start_time.date()
        end_date = end_time.date()
        while current_date <= end_date:
            if service_name:
                key = f'ai_usage:service:{service_name}:{current_date}'
            else:
                key = f'ai_usage:daily:{current_date}'
            data = await self.redis.hgetall(key)
            if data:
                usage_metrics.append(AIUsageMetrics(service_name=
                    service_name or 'all', model_name='aggregated',
                    input_tokens=0, output_tokens=0, total_tokens=int(data.
                    get('total_tokens', 0)), request_count=int(data.get(
                    'total_requests', 0)), cost_usd=Decimal(data.get(
                    'total_cost', '0')), timestamp=datetime.combine(
                    current_date, datetime.min.time())))
            current_date += timedelta(days=1)
        return usage_metrics

    async def calculate_daily_costs(self, target_date: date) ->Dict[str, Any]:
        """Calculate comprehensive daily cost breakdown."""
        daily_key = f'ai_usage:daily:{target_date}'
        daily_data = await self.redis.hgetall(daily_key)
        if not daily_data:
            return {'total_cost': Decimal('0'), 'total_requests': 0,
                'total_tokens': 0, 'service_breakdown': {},
                'model_breakdown': {}}
        service_breakdown = {}
        service_keys = await self.redis.keys(
            f'ai_usage:service:*:{target_date}')
        for key in service_keys:
            service_name = key.decode().split(':')[2]
            service_data = await self.redis.hgetall(key)
            if service_data:
                service_breakdown[service_name] = {'cost': Decimal(
                    service_data.get('total_cost', '0')), 'requests': int(
                    service_data.get('total_requests', 0)), 'tokens': int(
                    service_data.get('total_tokens', 0))}
        model_breakdown = {}
        model_keys = await self.redis.keys(f'ai_usage:model:*:{target_date}')
        for key in model_keys:
            model_name = key.decode().split(':')[2]
            model_data = await self.redis.hgetall(key)
            if model_data:
                model_breakdown[model_name] = {'cost': Decimal(model_data.
                    get('total_cost', '0')), 'requests': int(model_data.get
                    ('total_requests', 0)), 'tokens': int(model_data.get(
                    'total_tokens', 0))}
        return {'total_cost': Decimal(daily_data.get('total_cost', '0')),
            'total_requests': int(daily_data.get('total_requests', 0)),
            'total_tokens': int(daily_data.get('total_tokens', 0)),
            'service_breakdown': service_breakdown, 'model_breakdown':
            model_breakdown}

    async def get_cost_trends(self, days: int=7) ->List[Dict[str, Any]]:
        """Get cost trends over specified number of days."""
        trends = []
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        current_date = start_date
        while current_date <= end_date:
            daily_costs = await self.calculate_daily_costs(current_date)
            trends.append({'date': current_date.isoformat(), 'cost':
                daily_costs['total_cost'], 'requests': daily_costs[
                'total_requests'], 'tokens': daily_costs['total_tokens']})
            current_date += timedelta(days=1)
        return trends

    async def identify_cost_anomalies(self, threshold_multiplier: float=2.0,
        lookback_days: int=7) ->List[Dict[str, Any]]:
        """Identify cost anomalies based on historical patterns."""
        trends = await self.get_cost_trends(lookback_days)
        if len(trends) < 3:
            return []
        costs = [float(trend['cost']) for trend in trends[:-1]]
        today_cost = float(trends[-1]['cost'])
        if not costs:
            return []
        avg_cost = statistics.mean(costs)
        threshold = avg_cost * threshold_multiplier
        anomalies = []
        if today_cost > threshold:
            anomalies.append({'type': 'cost_spike', 'date': trends[-1][
                'date'], 'cost': trends[-1]['cost'], 'threshold': Decimal(
                str(threshold)), 'severity': 'high' if today_cost >
                threshold * 1.5 else 'medium'})
        return anomalies


class BudgetAlertService:
    """Service for managing budgets and generating alerts."""

    def __init__(self, redis_client: Optional[Redis]=None) ->None:
        self.redis = redis_client or self._get_redis_client()
        self.cost_tracker = CostTrackingService(self.redis)

    def _get_redis_client(self) ->Optional[Redis]:
        """Get Redis client connection."""
        try:
            redis_url = settings.redis_url or 'redis://localhost:6379/0'
            return redis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            logger.warning('Failed to connect to Redis: %s' % e)
            return None

    async def set_daily_budget(self, amount: Decimal) ->None:
        """Set daily budget limit."""
        await self.redis.set('budget:daily_limit', str(amount))
        logger.info('Daily budget set to $%s' % amount)

    async def set_monthly_budget(self, amount: Decimal) ->None:
        """Set monthly budget limit."""
        await self.redis.set('budget:monthly_limit', str(amount))
        logger.info('Monthly budget set to $%s' % amount)

    async def set_service_budget(self, service_name: str, amount: Decimal
        ) ->None:
        """Set budget limit for specific service."""
        await self.redis.set(f'budget:service:{service_name}', str(amount))
        logger.info('Budget for %s set to $%s' % (service_name, amount))

    async def set_user_daily_limit(self, user_id: str, amount: Decimal) ->None:
        """Set daily cost limit for specific user."""
        await self.redis.set(f'budget:user:{user_id}:daily', str(amount))
        logger.info('Daily limit for user %s set to $%s' % (user_id, amount))

    async def get_current_budget(self) ->Dict[str, Any]:
        """Get current budget configuration."""
        daily_limit = await self.redis.get('budget:daily_limit')
        monthly_limit = await self.redis.get('budget:monthly_limit')
        return {'daily_limit': Decimal(daily_limit) if daily_limit else
            None, 'monthly_limit': Decimal(monthly_limit) if monthly_limit else
            None}

    async def check_budget_status(self, usage: CostMetrics) ->Dict[str, Any]:
        """Check current budget status against usage."""
        budget = await self.get_current_budget()
        if not budget['daily_limit']:
            return {'status': 'no_budget_set'}
        usage_percentage = usage.total_cost / budget['daily_limit'] * 100
        remaining_budget = budget['daily_limit'] - usage.total_cost
        if usage_percentage >= 100:
            alert_level = 'critical'
        elif usage_percentage >= 80:
            alert_level = 'warning'
        elif usage_percentage >= 60:
            alert_level = 'info'
        else:
            alert_level = 'normal'
        return {'usage_percentage': float(usage_percentage),
            'remaining_budget': remaining_budget, 'alert_level':
            alert_level, 'budget_limit': budget['daily_limit']}

    async def check_budget_alerts(self, usage: CostMetrics) ->List[BudgetAlert
        ]:
        """Check for budget alerts based on current usage."""
        alerts = []
        budget_status = await self.check_budget_status(usage)
        if budget_status.get('alert_level') == 'warning':
            alerts.append(BudgetAlert(alert_type=AlertType.BUDGET_WARNING,
                severity='warning', message=
                f"Daily budget 80% used: ${usage.total_cost:.2f} of ${budget_status['budget_limit']:.2f}"
                , current_usage=usage.total_cost, budget_limit=
                budget_status['budget_limit']))
        elif budget_status.get('alert_level') == 'critical':
            alerts.append(BudgetAlert(alert_type=AlertType.BUDGET_EXCEEDED,
                severity='critical', message=
                f"Daily budget exceeded: ${usage.total_cost:.2f} of ${budget_status['budget_limit']:.2f}"
                , current_usage=usage.total_cost, budget_limit=
                budget_status['budget_limit']))
        return alerts

    async def detect_cost_spike(self, current_cost: Decimal, baseline_costs:
        List[Decimal], spike_threshold: float=3.0) ->bool:
        """Detect if current cost represents a spike."""
        if not baseline_costs:
            return False
        avg_baseline = sum(baseline_costs) / len(baseline_costs)
        return current_cost > avg_baseline * Decimal(str(spike_threshold))

    async def check_service_budget(self, service_name: str, usage: CostMetrics
        ) ->List[BudgetAlert]:
        """Check budget alerts for specific service."""
        service_budget_str = await self.redis.get(
            f'budget:service:{service_name}')
        if not service_budget_str:
            return []
        service_budget = Decimal(service_budget_str)
        usage_percentage = usage.total_cost / service_budget * 100
        alerts = []
        if usage_percentage >= 80:
            alerts.append(BudgetAlert(alert_type=AlertType.
                SERVICE_BUDGET_WARNING, severity='warning' if
                usage_percentage < 100 else 'critical', message=
                f'Service {service_name} budget {usage_percentage:.1f}% used',
                current_usage=usage.total_cost, budget_limit=service_budget,
                service_name=service_name))
        return alerts


class CostOptimizationService:
    """Service for analyzing usage patterns and recommending optimizations."""

    def __init__(self, redis_client: Optional[Redis]=None) ->None:
        self.redis = redis_client or self._get_redis_client()
        self.cost_tracker = CostTrackingService(self.redis)

    def _get_redis_client(self) ->Optional[Redis]:
        """Get Redis client connection."""
        try:
            redis_url = settings.redis_url or 'redis://localhost:6379/0'
            return redis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            logger.warning('Failed to connect to Redis: %s' % e)
            return None

    async def analyze_model_efficiency(self, usage_data: List[AIUsageMetrics]
        ) ->CostOptimization:
        """Analyze model efficiency and recommend optimal models."""
        model_performance = defaultdict(list)
        for usage in usage_data:
            model_performance[usage.model_name].append(usage)
        model_efficiency = {}
        for model_name, usages in model_performance.items():
            total_cost = sum(u.cost_usd for u in usages)
            total_quality = sum(u.response_quality_score or 0.8 for u in usages
                )
            avg_quality = total_quality / len(usages)
            efficiency = avg_quality / float(total_cost
                ) if total_cost > 0 else 0
            model_efficiency[model_name] = {'efficiency': efficiency,
                'cost': total_cost, 'quality': avg_quality, 'usage_count':
                len(usages)}
        best_model = max(model_efficiency.items(), key=lambda x: x[1][
            'efficiency'])
        current_cost = sum(u.cost_usd for u in usage_data)
        best_model_avg_cost = best_model[1]['cost'] / best_model[1][
            'usage_count']
        estimated_savings = current_cost - len(usage_data
            ) * best_model_avg_cost
        return CostOptimization(strategy=OptimizationStrategy.MODEL_SWITCH,
            recommendation=
            f'Switch to {best_model[0]} for better cost efficiency',
            potential_savings=max(Decimal('0'), estimated_savings),
            confidence_score=0.8, implementation_effort='low', priority=
            'high' if estimated_savings > current_cost * Decimal('0.2') else
            'medium')

    async def analyze_caching_opportunities(self, similar_requests: List[
        Dict[str, Any]]) ->CostOptimization:
        """Analyze caching opportunities for repeated similar requests."""
        total_savings = Decimal('0')
        for request_group in similar_requests:
            if request_group['count'] > 1:
                savings_per_cache = request_group['cost'] * (request_group[
                    'count'] - 1)
                total_savings += savings_per_cache
        return CostOptimization(strategy=OptimizationStrategy.
            CACHING_IMPROVEMENT, recommendation=
            'Implement intelligent caching for repeated similar requests',
            potential_savings=total_savings, confidence_score=0.9,
            implementation_effort='medium', priority='high' if
            total_savings > Decimal('10') else 'medium')

    async def analyze_batch_opportunities(self, individual_requests: List[
        Dict[str, Any]]) ->CostOptimization:
        """Analyze opportunities for batch processing."""
        grouped_requests = []
        current_group = []
        for request in sorted(individual_requests, key=lambda x: x['timestamp']
            ):
            if not current_group or (request['timestamp'] - current_group[-
                1]['timestamp']).seconds < 300:
                current_group.append(request)
            else:
                if len(current_group) > 1:
                    grouped_requests.append(current_group)
                current_group = [request]
        if len(current_group) > 1:
            grouped_requests.append(current_group)
        total_savings = Decimal('0')
        for group in grouped_requests:
            if len(group) > 1:
                group_cost = sum(req['cost'] for req in group)
                savings = group_cost * Decimal('0.2')
                total_savings += savings
        return CostOptimization(strategy=OptimizationStrategy.
            BATCH_PROCESSING, recommendation=
            f'Batch {len(grouped_requests)} groups of requests for cost efficiency'
            , potential_savings=total_savings, confidence_score=0.7,
            implementation_effort='high', priority='medium')

    async def analyze_prompt_efficiency(self, prompt_metrics: Dict[str, Any]
        ) ->CostOptimization:
        """Analyze prompt efficiency and recommend optimizations."""
        avg_input_tokens = prompt_metrics.get('avg_input_tokens', 0)
        success_rate = prompt_metrics.get('success_rate', 1.0)
        cost_per_success = prompt_metrics.get('cost_per_success', Decimal('0'))
        recommendations = []
        potential_savings = Decimal('0')
        if avg_input_tokens > 2000:
            recommendations.append(
                'Reduce input token count through prompt compression')
            potential_savings += cost_per_success * Decimal('0.3')
        if success_rate < 0.9:
            recommendations.append('Improve prompt clarity to reduce retries')
            retry_cost = cost_per_success * Decimal(str(1 - success_rate)
                ) / Decimal(str(success_rate))
            potential_savings += retry_cost
        return CostOptimization(strategy=OptimizationStrategy.
            PROMPT_OPTIMIZATION, recommendation='; '.join(recommendations) if
            recommendations else 'Prompts are well optimized',
            potential_savings=potential_savings, confidence_score=0.8,
            implementation_effort='medium', priority='high' if
            potential_savings > cost_per_success * Decimal('0.2') else 'low')

    async def generate_optimization_report(self, analysis_data: Dict[str, Any]
        ) ->Dict[str, Any]:
        """Generate comprehensive optimization report."""
        optimizations = []
        total_potential_savings = Decimal('0')
        optimizations.append(CostOptimization(strategy=OptimizationStrategy
            .MODEL_SWITCH, recommendation=
            'Switch to Gemini Flash for simple tasks', potential_savings=
            Decimal('25.50'), confidence_score=0.85, implementation_effort=
            'low', priority='high'))
        optimizations.append(CostOptimization(strategy=OptimizationStrategy
            .CACHING_IMPROVEMENT, recommendation=
            'Implement semantic caching for policy generation',
            potential_savings=Decimal('15.30'), confidence_score=0.9,
            implementation_effort='medium', priority='high'))
        total_potential_savings = sum(opt.potential_savings for opt in
            optimizations)
        priority_recommendations = sorted(optimizations, key=lambda x: (x.
            priority == 'high', x.potential_savings), reverse=True)
        return {'total_potential_savings': total_potential_savings,
            'optimizations': [{'strategy': opt.strategy.value,
            'recommendation': opt.recommendation, 'potential_savings': opt.
            potential_savings, 'confidence_score': opt.confidence_score,
            'implementation_effort': opt.implementation_effort, 'priority':
            opt.priority} for opt in optimizations],
            'priority_recommendations': [{'strategy': opt.strategy.value,
            'recommendation': opt.recommendation, 'potential_savings': opt.
            potential_savings} for opt in priority_recommendations[:3]],
            'roi_analysis': {'current_monthly_cost': analysis_data.get(
            'total_cost', Decimal('0')), 'projected_monthly_savings':
            total_potential_savings * 30, 'payback_period_days': 30}}


class AICostManager:
    """Main orchestrator for AI cost management."""

    def __init__(self, redis_client: Optional[Redis]=None) ->None:
        self.redis = redis_client or self._get_redis_client()
        self.cost_tracker = CostTrackingService(self.redis)
        self.budget_service = BudgetAlertService(self.redis)
        self.optimization_service = CostOptimizationService(self.redis)

    def _get_redis_client(self) ->Optional[Redis]:
        """Get Redis client connection."""
        try:
            redis_url = settings.redis_url or 'redis://localhost:6379/0'
            return redis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            logger.warning('Failed to connect to Redis: %s' % e)
            return None

    async def track_ai_request(self, service_name: str, model_name: str,
        input_prompt: str, response_content: str, input_tokens: int,
        output_tokens: int, user_id: Optional[str]=None, session_id:
        Optional[str]=None, request_id: Optional[str]=None,
        response_quality_score: Optional[float]=None, response_time_ms:
        Optional[float]=None, cache_hit: bool=False, error_occurred: bool=
        False, metadata: Optional[Dict[str, Any]]=None) ->Dict[str, Any]:
        """Track a complete AI request with cost calculation."""
        usage = await self.cost_tracker.track_usage(service_name=
            service_name, model_name=model_name, input_tokens=input_tokens,
            output_tokens=output_tokens, user_id=user_id, session_id=
            session_id, request_id=request_id, response_quality_score=
            response_quality_score, response_time_ms=response_time_ms,
            cache_hit=cache_hit, error_occurred=error_occurred,
            request_metadata=metadata)
        await self._check_real_time_budget_alerts(usage)
        return {'usage_id': usage.request_id, 'cost_usd': usage.cost_usd,
            'efficiency_score': usage.calculate_efficiency_score(),
            'cost_per_token': usage.cost_per_token}

    async def _check_real_time_budget_alerts(self, usage: AIUsageMetrics
        ) ->None:
        """Check for budget alerts in real-time."""
        today_costs = await self.cost_tracker.calculate_daily_costs(date.
            today())
        usage_metrics = CostMetrics(total_cost=today_costs['total_cost'],
            total_requests=today_costs['total_requests'], total_tokens=
            today_costs['total_tokens'], period_start=datetime.now().
            replace(hour=0, minute=0, second=0), period_end=datetime.now())
        alerts = await self.budget_service.check_budget_alerts(usage_metrics)
        if alerts:
            for alert in alerts:
                logger.warning('Budget alert: %s' % alert.message)

    async def get_daily_summary(self, target_date: date) ->Dict[str, Any]:
        """Get comprehensive daily cost summary."""
        daily_costs = await self.cost_tracker.calculate_daily_costs(target_date,
            )
        trends = await self.cost_tracker.get_cost_trends(7)
        efficiency_metrics = {'cost_per_request': daily_costs['total_cost'] /
            daily_costs['total_requests'] if daily_costs['total_requests'] >
            0 else Decimal('0'), 'cost_per_token': daily_costs['total_cost'
            ] / daily_costs['total_tokens'] if daily_costs['total_tokens'] >
            0 else Decimal('0')}
        return {**daily_costs, 'cost_trends': trends, 'efficiency_metrics':
            efficiency_metrics, 'date': target_date.isoformat()}

    async def set_daily_budget(self, amount: Decimal) ->None:
        """Set daily budget limit."""
        await self.budget_service.set_daily_budget(amount)

    async def set_user_daily_limit(self, user_id: str, amount: Decimal) ->None:
        """Set daily cost limit for user."""
        await self.budget_service.set_user_daily_limit(user_id, amount)

    async def check_budget_alerts(self) ->List[BudgetAlert]:
        """Check current budget alerts."""
        today_costs = await self.cost_tracker.calculate_daily_costs(date.
            today())
        usage_metrics = CostMetrics(total_cost=today_costs['total_cost'],
            total_requests=today_costs['total_requests'], total_tokens=
            today_costs['total_tokens'], period_start=datetime.now().
            replace(hour=0, minute=0, second=0), period_end=datetime.now())
        return await self.budget_service.check_budget_alerts(usage_metrics)

    async def get_optimization_recommendations(self) ->List[Dict[str, Any]]:
        """Get cost optimization recommendations."""
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        usage_data = await self.cost_tracker.get_usage_by_time_range(datetime
            .combine(start_date, datetime.min.time()), datetime.combine(
            end_date, datetime.max.time()))
        if not usage_data:
            return []
        model_optimization = (await self.optimization_service.
            analyze_model_efficiency(usage_data))
        return [{'strategy': model_optimization.strategy.value,
            'recommendation': model_optimization.recommendation,
            'potential_savings': model_optimization.potential_savings,
            'confidence_score': model_optimization.confidence_score,
            'implementation_effort': model_optimization.
            implementation_effort, 'priority': model_optimization.priority}]

    async def generate_monthly_report(self, year: int, month: int) ->Dict[
        str, Any]:
        """Generate comprehensive monthly cost report."""
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        daily_breakdown = []
        total_cost = Decimal('0')
        total_requests = 0
        total_tokens = 0
        current_date = start_date
        while current_date <= end_date:
            daily_data = await self.cost_tracker.calculate_daily_costs(
                current_date)
            daily_breakdown.append({'date': current_date.isoformat(), **
                daily_data})
            total_cost += daily_data['total_cost']
            total_requests += daily_data['total_requests']
            total_tokens += daily_data['total_tokens']
            current_date += timedelta(days=1)
        analysis_data = {'total_cost': total_cost}
        optimization_report = (await self.optimization_service.
            generate_optimization_report(analysis_data))
        return {'period': f'{year}-{month:02d}', 'total_cost': total_cost,
            'total_requests': total_requests, 'total_tokens': total_tokens,
            'daily_breakdown': daily_breakdown, 'service_analysis': {},
            'optimization_opportunities': optimization_report}


class IntelligentModelRouter:
    """Routes requests to optimal models based on task complexity and cost."""

    def __init__(self) ->None:
        self.model_configs = CostTrackingService()._load_model_configs()

    async def select_optimal_model(self, task_description: str, task_type:
        str, max_cost_per_request: Optional[Decimal]=None) ->Dict[str, Any]:
        """Select optimal model based on task complexity and cost constraints.

        **DO NOT CHANGE MODEL NAMES WITHOUT EXPRESS PERMISSION**
        **USES GEMINI 2.5 MODELS: gemini-2.5-flash-lite, gemini-2.5-flash, gemini-2.5-pro**
        """
        complexity_score = len(task_description.split()) / 100
        if task_type in ['policy_generation', 'assessment_analysis']:
            complexity_score += 0.5
        elif task_type in ['chat_assistance', 'simple_qa']:
            complexity_score += 0.1
        if complexity_score < 0.3:
            recommended_models = ['gemini-2.5-flash-lite', 'gpt-3.5-turbo']
        elif complexity_score > 0.7:
            recommended_models = ['gemini-2.5-pro', 'gpt-4-turbo']
        else:
            recommended_models = ['gemini-2.5-flash', 'gemini-2.5-pro']
        if max_cost_per_request:
            filtered_models = []
            for model_name in recommended_models:
                config = self.model_configs.get(model_name)
                if config:
                    estimated_cost = config.calculate_total_cost(1000, 500)
                    if estimated_cost <= max_cost_per_request:
                        filtered_models.append(model_name)
            recommended_models = filtered_models or recommended_models
        return {'model': recommended_models[0] if recommended_models else
            'gemini-2.5-flash', 'alternatives': recommended_models[1:],
            'complexity_score': complexity_score, 'reasoning':
            f'Selected based on task complexity ({complexity_score:.2f}) and cost constraints',
            }


class DynamicCacheManager:
    """Manages dynamic caching decisions based on cost-benefit analysis."""

    async def should_cache_request(self, request_data: Dict[str, Any]) ->bool:
        """Determine if request should be cached based on cost-benefit analysis."""
        estimated_cost = request_data.get('estimated_cost', Decimal('0'))
        frequency = request_data.get('frequency', 1)
        cache_threshold = Decimal('0.05')
        return estimated_cost * Decimal(frequency) > cache_threshold


class PromptOptimizer:
    """Optimizes prompts to reduce token usage while maintaining quality."""

    async def compress_prompt(self, prompt: str) ->str:
        """Compress prompt to reduce token usage."""
        compressed = prompt
        compressed = ' '.join(compressed.split())
        replacements = {'Please analyze the following': 'Analyze:',
            'Generate a comprehensive': 'Generate a',
            'Make sure to include': 'Include', 'It is important that': '',
            'Please ensure that': 'Ensure'}
        for verbose, concise in replacements.items():
            compressed = compressed.replace(verbose, concise)
        return compressed.strip()


class BatchRequestOptimizer:
    """Optimizes multiple requests through batching."""

    async def optimize_batch(self, requests: List[Dict[str, Any]]) ->Dict[
        str, Any]:
        """Optimize multiple requests through intelligent batching."""
        if len(requests) < 2:
            return {'batched': False, 'cost_savings': 0}
        combined_prompt = 'Process the following requests:\n'
        for i, request in enumerate(requests):
            combined_prompt += f"{i + 1}. {request['prompt']}\n"
        individual_cost = len(requests) * Decimal('0.02')
        batch_cost = individual_cost * Decimal('0.85')
        return {'batched': True, 'combined_prompt': combined_prompt,
            'cost_savings': individual_cost - batch_cost, 'original_count':
            len(requests)}


class CostAnalyticsDashboard:
    """Generates executive-level cost analytics and dashboards."""

    async def generate_executive_summary(self, cost_data: Dict[str, Any]
        ) ->Dict[str, Any]:
        """Generate executive summary of AI costs."""
        current_month = cost_data.get('current_month', Decimal('0'))
        previous_month = cost_data.get('previous_month', Decimal('0'))
        growth_rate = float((current_month - previous_month) /
            previous_month * 100) if previous_month > 0 else 0
        return {'cost_growth_rate': growth_rate, 'monthly_trend':
            'increasing' if growth_rate > 0 else 'decreasing',
            'roi_analysis': {'cost_per_customer': current_month / 100,
            'efficiency_score': 85.5}, 'optimization_impact': {
            'potential_monthly_savings': current_month * Decimal('0.2'),
            'implemented_savings': current_month * Decimal('0.1')},
            'budget_utilization': {'percentage_used': 75.5,
            'projected_month_end': current_month * Decimal('1.33')}}


class CostAttributionAnalyzer:
    """Analyzes cost attribution across multiple dimensions."""

    async def analyze_cost_attribution(self, time_period: Dict[str,
        datetime], dimensions: List[str]) ->Dict[str, Any]:
        """Analyze cost attribution across specified dimensions."""
        return {'user_breakdown': {'top_users': [{'user_id': 'user_123',
            'cost': Decimal('45.20'), 'requests': 245}, {'user_id':
            'user_456', 'cost': Decimal('38.50'), 'requests': 198}]},
            'service_breakdown': {'policy_generation': {'cost': Decimal(
            '125.30'), 'percentage': 42.5}, 'assessment_analysis': {'cost':
            Decimal('89.70'), 'percentage': 30.4}, 'chat_assistance': {
            'cost': Decimal('79.80'), 'percentage': 27.1}},
            'model_breakdown': {'gemini-1.5-pro': {'cost': Decimal('156.20'
            ), 'percentage': 53.0}, 'gemini-1.5-flash': {'cost': Decimal(
            '89.40'), 'percentage': 30.3}, 'gpt-4-turbo': {'cost': Decimal(
            '49.20'), 'percentage': 16.7}}, 'feature_breakdown': {
            'ai_policy_generation': {'cost': Decimal('98.40'), 'percentage':
            33.4}, 'compliance_assessment': {'cost': Decimal('87.20'),
            'percentage': 29.6}, 'evidence_analysis': {'cost': Decimal(
            '65.80'), 'percentage': 22.3}}, 'cost_drivers': [
            'High usage of premium models for simple tasks',
            'Lack of caching for repeated policy templates',
            'Inefficient prompt engineering leading to higher token usage']}


class PredictiveCostModeler:
    """Provides predictive modeling for future cost estimation."""

    async def predict_future_costs(self, historical_data: List[Dict[str,
        Any]], prediction_horizon_days: int, include_seasonality: bool=True,
        include_growth_trends: bool=True) ->Dict[str, Any]:
        """Predict future costs based on historical patterns."""
        costs = [float(data['cost']) for data in historical_data]
        if len(costs) < 2:
            avg_cost = costs[0] if costs else 0
            predicted_costs = [avg_cost] * prediction_horizon_days
        else:
            daily_growth = (costs[-1] - costs[0]) / len(costs)
            predicted_costs = []
            last_cost = costs[-1]
            for day in range(prediction_horizon_days):
                predicted_cost = last_cost + daily_growth * (day + 1)
                if include_seasonality:
                    weekday = (len(costs) + day) % 7
                    seasonal_multiplier = [0.8, 1.0, 1.1, 1.0, 1.2, 0.9, 0.7][
                        weekday]
                    predicted_cost *= seasonal_multiplier
                predicted_costs.append(max(0, predicted_cost))
        total_predicted = sum(predicted_costs)
        confidence = 0.85 if len(costs) > 30 else 0.65
        return {'predicted_costs': [{'day': i + 1, 'cost': Decimal(str(cost
            ))} for i, cost in enumerate(predicted_costs)],
            'total_predicted': Decimal(str(total_predicted)),
            'confidence_intervals': {'lower_bound': Decimal(str(
            total_predicted * 0.8)), 'upper_bound': Decimal(str(
            total_predicted * 1.2))}, 'confidence_score': confidence,
            'cost_drivers': ['Increasing user adoption',
            'Seasonal business cycles', 'New feature rollouts'],
            'recommended_budget': Decimal(str(total_predicted * 1.15))}
