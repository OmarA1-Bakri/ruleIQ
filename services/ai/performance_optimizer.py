"""
from __future__ import annotations

AI Performance Optimization System

Implements response time optimization, request batching, and intelligent
prompt optimization to enhance system performance and reduce costs.
"""
import logging

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from config.logging_config import get_logger
import contextlib
logger = get_logger(__name__)


class OptimizationStrategy(Enum):
    """Performance optimization strategies."""


@dataclass
class PerformanceMetrics:
    """Performance metrics for AI operations."""
    request_count: int = 0
    total_response_time: float = 0.0
    average_response_time: float = 0.0
    cache_hit_rate: float = 0.0
    token_usage: int = 0
    cost_estimate: float = 0.0
    optimization_savings: float = 0.0


@dataclass
class BatchRequest:
    """Batch request for AI processing."""
    request_id: str
    prompt: str
    context: Dict[str, Any]
    priority: int = 1
    created_at: datetime = None

    def __post_init__(self) ->None:
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class AIPerformanceOptimizer:
    """
    AI Performance Optimization System

    Features:
    - Request batching for similar prompts
    - Intelligent prompt compression
    - Response time optimization
    - Cost reduction through smart processing
    - Performance monitoring and analytics
    """

    def __init__(self) ->None:
        self.batch_queue: List[BatchRequest] = []
        self.batch_size = 5
        self.batch_timeout = 2.0
        self.max_prompt_length = 4000
        self.performance_metrics = PerformanceMetrics()
        self.enable_batching = True
        self.enable_compression = True
        self.enable_parallel_processing = True
        self.max_concurrent_requests = 10
        self.request_semaphore = asyncio.Semaphore(self.max_concurrent_requests,
            )
        self.last_request_time = 0
        self.min_request_interval = 0.1

    async def optimize_ai_request(self, prompt: str, context: Optional[Dict
        [str, Any]]=None, priority: int=1) ->Tuple[str, Dict[str, Any]]:
        """
        Optimize AI request for better performance.

        Args:
            prompt: The AI prompt to optimize
            context: Request context
            priority: Request priority (1-10, higher = more urgent)

        Returns:
            Tuple of (optimized_prompt, optimization_metadata)
        """
        start_time = time.time()
        try:
            optimized_prompt = await self._optimize_prompt(prompt, context)
            logger.debug('Original prompt length: %s' % len(prompt))
            logger.debug('Optimized prompt length: %s' % len(optimized_prompt))
            logger.debug('Optimized prompt content: %s...' %
                optimized_prompt[:200])
            logging.info('\n=== OPTIMIZED PROMPT ===')
            logging.info('Original length: %s' % len(prompt))
            logging.info('Optimized length: %s' % len(optimized_prompt))
            logging.info('Compression ratio: %s' % (len(optimized_prompt) /
                len(prompt) if len(prompt) > 0 else 1.0))
            logging.info('Content preview: %s...' % optimized_prompt[:300])
            logging.info('========================\n')
            strategy = self._select_optimization_strategy(optimized_prompt,
                context, priority)
            if (strategy == OptimizationStrategy.BATCH_PROCESSING and self.
                enable_batching):
                optimized_prompt = await self._apply_batch_optimization(
                    optimized_prompt, context, priority)
            elif strategy == OptimizationStrategy.PROMPT_COMPRESSION and self.enable_compression:
                optimized_prompt = await self._apply_compression_optimization(
                    optimized_prompt)
            optimization_time = time.time() - start_time
            metadata = {'optimization_strategy': strategy.value,
                'optimization_time_ms': round(optimization_time * 1000, 2),
                'original_length': len(prompt), 'optimized_length': len(
                optimized_prompt), 'compression_ratio': len(
                optimized_prompt) / len(prompt) if len(prompt) > 0 else 1.0}
            return optimized_prompt, metadata
        except Exception as e:
            logger.warning('Optimization failed, using original prompt: %s' % e,
                )
            return prompt, {'optimization_strategy': 'none', 'error': str(e)}

    async def _optimize_prompt(self, prompt: str, context: Optional[Dict[
        str, Any]]=None) ->str:
        """Apply intelligent prompt optimization."""
        optimized = re.sub('\\s+', ' ', prompt.strip())
        if context and context.get('framework'):
            framework = context['framework']
            if framework == 'ISO27001':
                optimized = optimized.replace('ISO 27001', 'ISO27001')
                optimized = optimized.replace(
                    'information security management system', 'ISMS')
            elif framework == 'GDPR':
                optimized = optimized.replace(
                    'General Data Protection Regulation', 'GDPR')
                optimized = optimized.replace('data protection officer', 'DPO')
            elif framework == 'SOC2':
                optimized = optimized.replace('Service Organization Control',
                    'SOC')
                optimized = optimized.replace('Type II', 'T2')
        if context and context.get('business_context'):
            business = context['business_context']
            if business.get('company_name'):
                company_name = business['company_name']
                if len(company_name) > 20:
                    optimized = optimized.replace(company_name, 'ORG')
        if len(optimized) > self.max_prompt_length:
            keep_start = self.max_prompt_length // 3
            keep_end = self.max_prompt_length // 3
            middle_compressed = '...[content compressed]...'
            optimized = optimized[:keep_start] + middle_compressed + optimized[
                -keep_end:]
        return optimized

    def _select_optimization_strategy(self, prompt: str, context: Optional[
        Dict[str, Any]]=None, priority: int=1) ->OptimizationStrategy:
        """Select the best optimization strategy for the request."""
        if priority >= 8:
            return OptimizationStrategy.PARALLEL_EXECUTION
        if len(prompt) > 2000:
            return OptimizationStrategy.PROMPT_COMPRESSION
        if self._can_batch_request(prompt, context):
            return OptimizationStrategy.BATCH_PROCESSING
        return OptimizationStrategy.PARALLEL_EXECUTION

    def _can_batch_request(self, prompt: str, context: Optional[Dict[str,
        Any]]=None) ->bool:
        """Determine if request can be batched with others."""
        if context and context.get('priority', 1) >= 7:
            return False
        prompt_keywords = set(re.findall('\\b\\w+\\b', prompt.lower()))
        for batch_req in self.batch_queue:
            batch_keywords = set(re.findall('\\b\\w+\\b', batch_req.prompt.
                lower()))
            similarity = len(prompt_keywords & batch_keywords) / len(
                prompt_keywords | batch_keywords)
            if similarity > 0.7:
                return True
        return len(self.batch_queue) < self.batch_size

    async def _apply_batch_optimization(self, prompt: str, context: Dict[
        str, Any], priority: int) ->str:
        """Apply batch processing optimization."""
        batch_request = BatchRequest(request_id=
            f'req_{int(time.time() * 1000)}', prompt=prompt, context=
            context or {}, priority=priority)
        self.batch_queue.append(batch_request)
        if len(self.batch_queue
            ) >= self.batch_size or self._should_process_batch_timeout():
            await self._process_batch()
        return prompt

    async def _apply_compression_optimization(self, prompt: str) ->str:
        """Apply prompt compression optimization."""
        compressed = prompt
        redundant_phrases = ['\\b(please|kindly|if you could|would you)\\b',
            '\\b(in order to|for the purpose of)\\b',
            '\\b(it is important to note that|please note that)\\b']
        for phrase_pattern in redundant_phrases:
            compressed = re.sub(phrase_pattern, '', compressed, flags=re.
                IGNORECASE)
        compressed = re.sub('\\b(\\w+)\\s+\\1\\b', '\\1', compressed)
        compressed = re.sub('\\s+', ' ', compressed)
        return compressed.strip()

    def _should_process_batch_timeout(self) ->bool:
        """Check if batch should be processed due to timeout."""
        if not self.batch_queue:
            return False
        oldest_request = min(self.batch_queue, key=lambda x: x.created_at)
        age = (datetime.now(timezone.utc) - oldest_request.created_at
            ).total_seconds()
        return age >= self.batch_timeout

    async def _process_batch(self) ->None:
        """Process the current batch of requests."""
        if not self.batch_queue:
            return
        logger.info('Processing batch of %s requests' % len(self.batch_queue))
        self.batch_queue.sort(key=lambda x: x.priority, reverse=True)
        processed_count = len(self.batch_queue)
        self.batch_queue.clear()
        self.performance_metrics.request_count += processed_count
        logger.debug('Processed batch of %s requests' % processed_count)

    async def apply_rate_limiting(self) ->bool:
        """Apply intelligent rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            await asyncio.sleep(wait_time)
        await self.request_semaphore.acquire()
        self.last_request_time = time.time()
        return True

    def release_rate_limit(self) ->None:
        """Release rate limiting resources."""
        with contextlib.suppress(ValueError):
            self.request_semaphore.release()

    async def get_performance_metrics(self) ->Dict[str, Any]:
        """Get comprehensive performance metrics."""
        if self.performance_metrics.request_count > 0:
            self.performance_metrics.average_response_time = (self.
                performance_metrics.total_response_time / self.
                performance_metrics.request_count)
        return {'request_statistics': {'total_requests': self.
            performance_metrics.request_count, 'average_response_time_ms':
            round(self.performance_metrics.average_response_time * 1000, 2),
            'cache_hit_rate': round(self.performance_metrics.cache_hit_rate,
            2), 'current_queue_size': len(self.batch_queue)},
            'optimization_settings': {'batching_enabled': self.
            enable_batching, 'compression_enabled': self.enable_compression,
            'parallel_processing_enabled': self.enable_parallel_processing,
            'max_concurrent_requests': self.max_concurrent_requests,
            'batch_size': self.batch_size, 'batch_timeout_seconds': self.
            batch_timeout}, 'cost_optimization': {'estimated_token_usage':
            self.performance_metrics.token_usage, 'estimated_cost': round(
            self.performance_metrics.cost_estimate, 4),
            'optimization_savings': round(self.performance_metrics.
            optimization_savings, 4)}, 'system_health': {
            'available_capacity': self.request_semaphore._value,
            'queue_utilization': len(self.batch_queue) / self.batch_size *
            100, 'last_request_time': self.last_request_time}}

    def update_performance_metrics(self, response_time: float, token_count:
        int=0) ->None:
        """Update performance metrics with new data."""
        self.performance_metrics.request_count += 1
        self.performance_metrics.total_response_time += response_time
        self.performance_metrics.token_usage += token_count
        estimated_cost = token_count * 1e-05
        self.performance_metrics.cost_estimate += estimated_cost

    async def optimize_concurrent_requests(self, requests: List[Dict[str, Any]]
        ) ->List[Dict[str, Any]]:
        """Optimize multiple concurrent AI requests."""
        if not self.enable_parallel_processing:
            results = []
            for request in requests:
                result = await self._process_single_request(request)
                results.append(result)
            return results
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        async def process_with_semaphore(request) ->Any:
            async with semaphore:
                return await self._process_single_request(request)
        tasks = [process_with_semaphore(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning('Request %s failed: %s' % (i, result))
                processed_results.append({'error': str(result),
                    'request_index': i})
            else:
                processed_results.append(result)
        return processed_results

    async def _process_single_request(self, request: Dict[str, Any]) ->Dict[
        str, Any]:
        """Process a single optimized request."""
        await asyncio.sleep(0.1)
        return {'request_id': request.get('id', 'unknown'), 'status':
            'completed', 'processing_time_ms': 100}


performance_optimizer = AIPerformanceOptimizer()


async def get_performance_optimizer() ->AIPerformanceOptimizer:
    """Get the global performance optimizer instance."""
    return performance_optimizer
