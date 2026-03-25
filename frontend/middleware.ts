import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const LEGACY_ROUTE_PREFIXES = [
  '/advanced-dashboard',
  '/dashboard',
  '/dashboard-2',
  '/demo',
  '/showcase',
  '/test-theme',
  '/_deprecated',
  '/design-system',
  '/neural-demo',
  '/editor',
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isAuthPage =
    pathname.startsWith('/login') || pathname.startsWith('/register');
  const _isPublicPath = pathname === '/' || isAuthPage;

  if (LEGACY_ROUTE_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))) {
    return NextResponse.redirect(new URL('/', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
};
