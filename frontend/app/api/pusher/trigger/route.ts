/**
 * API route for triggering Pusher events from the client.
 * Validates permissions and rate limits before triggering events.
 */

import { NextRequest, NextResponse } from 'next/server';
import Pusher from 'pusher';
import jwt from 'jsonwebtoken';
import { kv } from '@vercel/kv';

// Initialize Pusher server instance
const pusher = new Pusher({
  appId: process.env.PUSHER_APP_ID!,
  key: process.env.NEXT_PUBLIC_PUSHER_KEY!,
  secret: process.env.PUSHER_SECRET!,
  cluster: process.env.NEXT_PUBLIC_PUSHER_CLUSTER!,
  useTLS: true,
});

/**
 * Rate limiting configuration for event triggering.
 */
const TRIGGER_RATE_LIMIT_WINDOW = 60; // 60 seconds
const TRIGGER_RATE_LIMIT_MAX = 10; // 10 triggers per minute

/**
 * Check trigger rate limit for a user using Vercel KV.
 */
async function checkTriggerRateLimit(userId: string): Promise<boolean> {
  try {
    // If KV is not configured, allow the request (fail open for development)
    if (!process.env.KV_URL) {
      console.warn('Vercel KV not configured, skipping rate limiting');
      return true;
    }

    const key = `ratelimit:trigger:${userId}`;

    // Increment the counter and set expiry if new
    const count = await kv.incr(key);

    // If this is the first request, set the expiry
    if (count === 1) {
      await kv.expire(key, TRIGGER_RATE_LIMIT_WINDOW);
    }

    // Check if limit exceeded
    if (count > TRIGGER_RATE_LIMIT_MAX) {
      return false;
    }

    return true;
  } catch (error) {
    console.error('Rate limit check failed:', error);
    // Fail open - allow the request if rate limiting fails
    return true;
  }
}

/**
 * Validate user permission to trigger events on a channel.
 */
function validateTriggerPermission(
  channel: string,
  event: string,
  userId: string,
  userRole: string
): boolean {
  // Admin can trigger any event
  if (userRole === 'admin') {
    return true;
  }

  // Users can trigger events on their own channel
  if (channel === `private-user-${userId}`) {
    return true;
  }

  // Specific event permissions
  const allowedEvents = {
    'user-action': ['manager', 'viewer'],
    'request-update': ['manager', 'viewer'],
    'feedback': ['manager', 'viewer'],
  };

  if (allowedEvents[event as keyof typeof allowedEvents]?.includes(userRole)) {
    return true;
  }

  // Default deny
  return false;
}

/**
 * Sanitize event data to prevent injection attacks.
 */
function sanitizeEventData(data: any): any {
  if (typeof data === 'string') {
    // Remove any script tags or dangerous content
    return data.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
  }
  
  if (typeof data === 'object' && data !== null) {
    const sanitized: any = Array.isArray(data) ? [] : {};
    for (const key in data) {
      if (Object.hasOwn(data, key)) {
        sanitized[key] = sanitizeEventData(data[key]);
      }
    }
    return sanitized;
  }
  
  return data;
}

/**
 * POST /api/pusher/trigger
 * Trigger a Pusher event from the client.
 */
export async function POST(req: NextRequest) {
  try {
    // Use JWT-only authentication (NextAuth removed from project)
    console.log('Using JWT-only authentication');

    // Validate JWT token from Authorization header
    let userId: string | null = null;
    let userRole: string = 'viewer';

    const authHeader = req.headers.get('authorization');
    if (authHeader?.startsWith('Bearer ')) {
      const token = authHeader.substring(7);
      try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET || 'default-secret-change-in-production') as any;
        userId = decoded.userId || decoded.sub;
        userRole = decoded.role || 'viewer';
      } catch (error) {
        console.error('JWT validation failed:', error);
      }
    }

    // Check authentication
    if (!userId) {
      return NextResponse.json(
        { error: 'Authentication required' },
        { status: 401 }
      );
    }

    // Check rate limit
    if (!(await checkTriggerRateLimit(userId))) {
      return NextResponse.json(
        { error: 'Rate limit exceeded. Please wait before triggering more events.' },
        { status: 429 }
      );
    }

    // Parse request body
    const body = await req.json();
    const { channel, event, data, socket_id } = body;

    // Validate required parameters
    if (!channel || !event || !data) {
      return NextResponse.json(
        { error: 'Missing required parameters: channel, event, and data are required' },
        { status: 400 }
      );
    }

    // Validate channel name format
    if (!/^[a-zA-Z0-9_\-=@.,;]+$/.test(channel)) {
      return NextResponse.json(
        { error: 'Invalid channel name format' },
        { status: 400 }
      );
    }

    // Validate event name format
    if (!/^[a-zA-Z0-9_\-=@.,;]+$/.test(event)) {
      return NextResponse.json(
        { error: 'Invalid event name format' },
        { status: 400 }
      );
    }

    // Check permission to trigger event
    if (!validateTriggerPermission(channel, event, userId, userRole)) {
      return NextResponse.json(
        { error: 'You do not have permission to trigger this event' },
        { status: 403 }
      );
    }

    // Sanitize event data
    const sanitizedData = sanitizeEventData(data);

    // Add metadata to event
    const enrichedData = {
      ...sanitizedData,
      _metadata: {
        triggered_by: userId,
        triggered_at: new Date().toISOString(),
        user_role: userRole,
      },
    };

    // Trigger the event
    try {
      await pusher.trigger(channel, event, enrichedData, {
        socket_id: socket_id || undefined,
      });

      // Log the event trigger
      console.log(`User ${userId} triggered event '${event}' on channel '${channel}'`);

      return NextResponse.json({
        success: true,
        message: 'Event triggered successfully',
      });
    } catch (pusherError) {
      console.error('Failed to trigger Pusher event:', pusherError);
      return NextResponse.json(
        { error: 'Failed to trigger event' },
        { status: 500 }
      );
    }
  } catch (error) {
    console.error('Pusher trigger error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * OPTIONS /api/pusher/trigger
 * Handle CORS preflight requests.
 */
export async function OPTIONS(_req: NextRequest) {
  return new NextResponse(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      'Access-Control-Max-Age': '86400',
    },
  });
}