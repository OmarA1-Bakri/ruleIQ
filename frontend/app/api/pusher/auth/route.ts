/**
 * API route for Pusher channel authentication.
 * Handles authentication for private and presence channels.
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
 * Rate limiting configuration.
 */
const RATE_LIMIT_WINDOW = 60; // 60 seconds
const RATE_LIMIT_MAX = 20; // 20 requests per minute

/**
 * Check rate limit for a user using Vercel KV.
 */
async function checkRateLimit(userId: string): Promise<boolean> {
  try {
    // If KV is not configured, allow the request (fail open for development)
    if (!process.env.KV_URL) {
      console.warn('Vercel KV not configured, skipping rate limiting');
      return true;
    }

    const key = `ratelimit:auth:${userId}`;

    // Increment the counter and set expiry if new
    const count = await kv.incr(key);

    // If this is the first request, set the expiry
    if (count === 1) {
      await kv.expire(key, RATE_LIMIT_WINDOW);
    }

    // Check if limit exceeded
    if (count > RATE_LIMIT_MAX) {
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
 * Validate user access to a channel.
 */
async function validateChannelAccess(
  channelName: string,
  userId: string,
  userRole: string
): Promise<boolean> {
  // Public channels don't need validation
  if (!channelName.startsWith('private-') && !channelName.startsWith('presence-')) {
    return false; // Public channels don't need auth
  }

  // User's own private channel
  if (channelName === `private-user-${userId}`) {
    return true;
  }

  // Cost dashboard - check permissions
  if (channelName === 'private-cost-dashboard') {
    // Check if user has dashboard access
    // This would typically check database/permissions
    return ['admin', 'manager', 'viewer'].includes(userRole);
  }

  // Budget alerts - check permissions
  if (channelName === 'private-budget-alerts') {
    // Check if user has budget access
    return ['admin', 'manager'].includes(userRole);
  }

  // Service monitoring - admin only
  if (channelName === 'private-service-monitoring') {
    return userRole === 'admin';
  }

  // Presence dashboard - all authenticated users
  if (channelName === 'presence-dashboard') {
    return true;
  }

  // Default deny
  return false;
}

/**
 * POST /api/pusher/auth
 * Authenticate Pusher channel subscription.
 */
export async function POST(req: NextRequest) {
  try {
    // Use JWT-only authentication (NextAuth removed from project)
    console.log('Using JWT-only authentication mode');

    // Validate JWT token from Authorization header
    let userId: string | null = null;
    let userRole: string = 'viewer';
    let userName: string = 'Anonymous';
    let userEmail: string = '';

    const authHeader = req.headers.get('authorization');
    if (authHeader?.startsWith('Bearer ')) {
      const token = authHeader.substring(7);
      try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET || 'default-secret-change-in-production') as any;
        userId = decoded.userId || decoded.sub;
        userRole = decoded.role || 'viewer';
        userName = decoded.name || 'Anonymous';
        userEmail = decoded.email || '';
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
    if (!(await checkRateLimit(userId))) {
      return NextResponse.json(
        { error: 'Rate limit exceeded' },
        { status: 429 }
      );
    }

    // Parse request body
    const body = await req.json();
    const { socket_id, channel_name } = body;

    if (!socket_id || !channel_name) {
      return NextResponse.json(
        { error: 'Missing required parameters' },
        { status: 400 }
      );
    }

    // Validate channel access
    const hasAccess = await validateChannelAccess(channel_name, userId, userRole);
    if (!hasAccess) {
      return NextResponse.json(
        { error: 'Access denied to this channel' },
        { status: 403 }
      );
    }

    // Generate auth response based on channel type
    let authResponse;

    if (channel_name.startsWith('presence-')) {
      // Presence channel - include user data
      const presenceData = {
        user_id: userId,
        user_info: {
          name: userName,
          email: userEmail,
          role: userRole,
          avatar: `https://api.dicebear.com/7.x/avataaars/svg?seed=${userId}`,
        },
      };

      authResponse = pusher.authorizeChannel(socket_id, channel_name, presenceData);
    } else {
      // Private channel - simple auth
      authResponse = pusher.authorizeChannel(socket_id, channel_name);
    }

    // Log authentication
    console.log(`User ${userId} authenticated for channel ${channel_name}`);

    return NextResponse.json(authResponse);
  } catch (error) {
    console.error('Pusher auth error:', error);
    return NextResponse.json(
      { error: 'Authentication failed' },
      { status: 500 }
    );
  }
}

/**
 * OPTIONS /api/pusher/auth
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