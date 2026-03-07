import { NextRequest, NextResponse } from 'next/server';
import Pusher from 'pusher';

// Initialize Pusher if credentials are available
const pusherClient = process.env.NEXT_PUBLIC_PUSHER_KEY ? new Pusher({
  appId: process.env.PUSHER_APP_ID!,
  key: process.env.NEXT_PUBLIC_PUSHER_KEY!,
  secret: process.env.PUSHER_SECRET!,
  cluster: process.env.NEXT_PUBLIC_PUSHER_CLUSTER || 'eu',
  useTLS: true
}) : null;

export async function POST(request: NextRequest) {
  try {
    // Verify this is from Vercel Cron (check for secret if configured)
    const authHeader = request.headers.get('authorization');
    if (process.env.CRON_SECRET && authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    if (!pusherClient) {
      console.warn('Pusher not configured, skipping broadcast');
      return NextResponse.json({ 
        success: true, 
        message: 'Pusher not configured, broadcast skipped' 
      });
    }

    // Broadcast heartbeat and/or cost updates
    const timestamp = new Date().toISOString();
    
    // Send heartbeat
    await pusherClient.trigger('system-updates', 'heartbeat', {
      timestamp,
      status: 'healthy'
    });

    // If cost monitoring is enabled, send updates
    if (process.env.ENABLE_COST_MONITORING === 'true') {
      // In a real implementation, you would fetch actual cost data here
      const costData = {
        timestamp,
        totalCost: 0, // Would fetch from database
        budgetUsage: 0, // Would calculate from settings
      };

      await pusherClient.trigger('cost-updates', 'cost-update', costData);
    }

    return NextResponse.json({ 
      success: true,
      timestamp,
      message: 'Broadcast completed successfully'
    });

  } catch (error) {
    console.error('Scheduled broadcast error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

// Support GET for manual testing/health checks
export async function GET(_request: NextRequest) {
  return NextResponse.json({
    status: 'ok',
    pusherConfigured: !!pusherClient,
    timestamp: new Date().toISOString()
  });
}