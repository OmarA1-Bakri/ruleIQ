"""
import logging


logger = logging.getLogger(__name__)
Webhook Handler Router

Handles incoming webhooks from external services with signature verification
"""
from typing import Any, Dict
import json
from fastapi import APIRouter, Request, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from database.db_setup import get_db
from services.webhook_verification import WebhookVerificationService
from database.redis_client import get_redis_client
from config.logging_config import get_logger
logger = get_logger(__name__)
router = APIRouter(prefix='/api/v1/webhooks', tags=['Webhooks'], responses=
    {(404): {'description': 'Not found'}})


async def handle_stripe_event(event_type: str, data: dict, db: AsyncSession
    ) ->None:
    """Handle Stripe webhook events."""
    logger.info('Processing Stripe event: %s' % event_type)
    if event_type == 'payment_intent.succeeded':
        payment_intent = data.get('object', {})
        customer_id = payment_intent.get('customer')
        amount = payment_intent.get('amount', 0) / 100
        logger.info('Payment succeeded for customer %s: $%s' % (customer_id,
            amount))
    elif event_type == 'customer.subscription.created':
        subscription = data.get('object', {})
        customer_id = subscription.get('customer')
        status = subscription.get('status')
        logger.info('Subscription created for customer %s: %s' % (
            customer_id, status))
    elif event_type == 'customer.subscription.deleted':
        subscription = data.get('object', {})
        customer_id = subscription.get('customer')
        logger.info('Subscription cancelled for customer %s' % customer_id)
    elif event_type == 'invoice.payment_failed':
        invoice = data.get('object', {})
        customer_id = invoice.get('customer')
        logger.warning('Payment failed for customer %s' % customer_id)
    else:
        logger.info('Unhandled Stripe event type: %s' % event_type)


async def handle_github_event(event_type: str, data: dict, db: AsyncSession
    ) ->None:
    """Handle GitHub webhook events."""
    logger.info('Processing GitHub event: %s' % event_type)
    if event_type == 'push':
        repository = data.get('repository', {}).get('full_name')
        pusher = data.get('pusher', {}).get('name')
        logger.info('Code pushed to %s by %s' % (repository, pusher))
    elif event_type == 'pull_request':
        action = data.get('action')
        pr_number = data.get('pull_request', {}).get('number')
        logger.info('Pull request #%s %s' % (pr_number, action))
    elif event_type == 'issues':
        action = data.get('action')
        issue_number = data.get('issue', {}).get('number')
        logger.info('Issue #%s %s' % (issue_number, action))
    else:
        logger.info('Unhandled GitHub event type: %s' % event_type)


async def handle_sendgrid_event(events: list, db: AsyncSession) ->None:
    """Handle SendGrid webhook events."""
    for event in events:
        event_type = event.get('event')
        email = event.get('email')
        logger.info('Processing SendGrid event: %s for %s' % (event_type,
            email))
        if event_type == 'delivered':
            logger.info('Email delivered to %s' % email)
        elif event_type == 'bounce':
            reason = event.get('reason', 'Unknown')
            logger.warning('Email bounced for %s: %s' % (email, reason))
        elif event_type == 'spam_report':
            logger.warning('Email marked as spam by %s' % email)
        elif event_type == 'unsubscribe':
            logger.info('User unsubscribed: %s' % email)


@router.post('/stripe', include_in_schema=False)
async def stripe_webhook(request: Request, background_tasks:
    BackgroundTasks, db: AsyncSession=Depends(get_db), redis_client: redis.
    Redis=Depends(get_redis_client)) ->Dict[str, Any]:
    """
    Handle Stripe webhooks with signature verification.

    Configure webhook endpoint in Stripe dashboard:
    https://dashboard.stripe.com/webhooks
    """
    try:
        payload = await request.body()
        service = WebhookVerificationService(redis_client)
        is_valid, error = await service.verify_webhook(request=request,
            provider='stripe', payload=payload)
        if not is_valid:
            logger.warning('Invalid Stripe webhook signature: %s' % error)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Invalid webhook signature')
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid JSON payload')
        event_type = data.get('type')
        event_data = data.get('data', {})
        background_tasks.add_task(handle_stripe_event, event_type,
            event_data, db)
        await service.log_webhook_attempt(provider='stripe', endpoint=
            '/webhooks/stripe', is_valid=True, metadata={'event_type':
            event_type})
        return {'received': True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error('Stripe webhook error: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail='Webhook processing failed')


@router.post('/github', include_in_schema=False)
async def github_webhook(request: Request, background_tasks:
    BackgroundTasks, db: AsyncSession=Depends(get_db), redis_client: redis.
    Redis=Depends(get_redis_client)) ->Dict[str, Any]:
    """
    Handle GitHub webhooks with signature verification.

    Configure webhook in repository settings:
    https://github.com/[owner]/[repo]/settings/hooks
    """
    try:
        payload = await request.body()
        service = WebhookVerificationService(redis_client)
        is_valid, error = await service.verify_webhook(request=request,
            provider='github', payload=payload)
        if not is_valid:
            logger.warning('Invalid GitHub webhook signature: %s' % error)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Invalid webhook signature')
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid JSON payload')
        event_type = request.headers.get('X-GitHub-Event', 'unknown')
        background_tasks.add_task(handle_github_event, event_type, data, db)
        await service.log_webhook_attempt(provider='github', endpoint=
            '/webhooks/github', is_valid=True, metadata={'event_type':
            event_type})
        return {'received': True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error('GitHub webhook error: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail='Webhook processing failed')


@router.post('/sendgrid', include_in_schema=False)
async def sendgrid_webhook(request: Request, background_tasks:
    BackgroundTasks, db: AsyncSession=Depends(get_db), redis_client: redis.
    Redis=Depends(get_redis_client)) ->Dict[str, Any]:
    """
    Handle SendGrid email event webhooks.

    Configure webhook in SendGrid settings:
    https://app.sendgrid.com/settings/mail_settings/event_notification
    """
    try:
        payload = await request.body()
        service = WebhookVerificationService(redis_client)
        is_valid, error = await service.verify_webhook(request=request,
            provider='sendgrid', payload=payload)
        if not is_valid:
            logger.warning('Invalid SendGrid webhook signature: %s' % error)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Invalid webhook signature')
        try:
            events = json.loads(payload)
            if not isinstance(events, list):
                events = [events]
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid JSON payload')
        background_tasks.add_task(handle_sendgrid_event, events, db)
        await service.log_webhook_attempt(provider='sendgrid', endpoint=
            '/webhooks/sendgrid', is_valid=True, metadata={'event_count':
            len(events)})
        return {'received': True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error('SendGrid webhook error: %s' % e)
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail='Webhook processing failed')


@router.post('/custom/{webhook_id}', include_in_schema=False)
async def custom_webhook(webhook_id: str, request: Request,
    background_tasks: BackgroundTasks, db: AsyncSession=Depends(get_db),
    redis_client: redis.Redis=Depends(get_redis_client)) ->Dict[str, Any]:
    """
    Handle custom webhooks with signature verification.

    Use this for any service that doesn't have a dedicated endpoint.
    Requires webhook configuration with signature secret.
    """
    try:
        payload = await request.body()
        webhook_secret = None
        service = WebhookVerificationService(redis_client)
        is_valid, error = await service.verify_webhook(request=request,
            provider='custom', secret=webhook_secret, payload=payload)
        if not is_valid:
            logger.warning('Invalid custom webhook signature for %s: %s' %
                (webhook_id, error))
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                detail='Invalid webhook signature')
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid JSON payload')
        logger.info('Received custom webhook %s: %s' % (webhook_id, data))
        await service.log_webhook_attempt(provider='custom', endpoint=
            f'/webhooks/custom/{webhook_id}', is_valid=True, metadata={
            'webhook_id': webhook_id})
        return {'received': True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error('Custom webhook error for %s: %s' % (webhook_id, e))
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail='Webhook processing failed')


@router.get('/test/generate-signature')
async def test_generate_signature(payload: str='{"test": "data"}', secret:
    str='test_secret', provider: str='custom') ->Dict[str, Any]:
    """
    Test endpoint to generate webhook signatures for testing.

    Only available in development/test environments.
    """
    import os
    if os.getenv('ENVIRONMENT', 'production').lower() not in ['development',
        'test', 'local']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=
            'This endpoint is only available in development')
    service = WebhookVerificationService()
    signature = await service.generate_webhook_signature(payload=payload,
        secret=secret, provider=provider)
    return {'provider': provider, 'signature': signature, 'header_name':
        WebhookVerificationService.PROVIDERS[provider]['header'], 'payload':
        payload}
