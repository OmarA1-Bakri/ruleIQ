'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuthStore } from '@/lib/stores/auth.store';
import { cn } from '@/lib/utils';
import { Button } from './button';
import Image from 'next/image';
import { useState } from 'react';

export function Header() {
  const pathname = usePathname();
  const { isAuthenticated } = useAuthStore();
  const [logoError, setLogoError] = useState(false);
  
  const navigation = [
    { name: 'Home', href: '/' },
    { name: 'Features', href: '/features' },
    { name: 'Pricing', href: '/pricing' },
    { name: 'About', href: '/about' },
  ];

  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-neural-purple-500/10 bg-black/80 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo with purple shadow and lift effect */}
          <Link href="/" className="flex items-center space-x-2 group">
            {!logoError ? (
              <div className="relative w-[150px] h-[150px] transition-all duration-300 ease-out
                            group-hover:-translate-y-0.5 group-hover:scale-105
                            filter drop-shadow-[0_4px_20px_rgba(139,92,246,0.3)]
                            group-hover:drop-shadow-[0_8px_30px_rgba(139,92,246,0.5)]">
                <Image 
                  src="/assets/ruleiq-logo.png" 
                  alt="RuleIQ" 
                  fill
                  className="object-contain"
                  priority
                  onError={() => setLogoError(true)}
                />
              </div>
            ) : (
              <div className="flex items-center transition-all duration-300 
                            group-hover:-translate-y-0.5 group-hover:scale-105
                            filter drop-shadow-[0_4px_20px_rgba(139,92,246,0.3)]
                            group-hover:drop-shadow-[0_8px_30px_rgba(139,92,246,0.5)]">
                <span className="text-2xl font-extralight text-white">Rule</span>
                <span className="text-2xl font-extralight text-white relative">
                  IQ
                  <span className="absolute inset-0 text-2xl font-extralight bg-gradient-to-r from-neural-purple-400 via-silver-400 to-neural-purple-400 bg-clip-text text-transparent opacity-60">
                    IQ
                  </span>
                </span>
              </div>
            )}
          </Link>
          
          {/* Navigation */}
          <nav className="hidden md:flex items-center space-x-8">
            {navigation.map((item) => (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  'text-sm font-light tracking-tight transition-all duration-300 relative',
                  pathname === item.href
                    ? 'text-neural-purple-400 after:absolute after:-bottom-0.5 after:left-0 after:right-0 after:h-0.5 after:bg-gradient-to-r after:from-neural-purple-500 after:to-neural-purple-600'
                    : 'text-white/70 hover:text-white hover:-translate-y-0.5'
                )}
              >
                {item.name}
              </Link>
            ))}
          </nav>
          
          {/* Actions */}
          <div className="flex items-center space-x-4">
            {isAuthenticated ? (
              <>
                <Button
                  variant="ghost"
                  className="text-white/70 hover:text-white font-light"
                  onClick={() => window.location.href = '/dashboard'}
                >
                  Dashboard
                </Button>
                <Button
                  variant="ghost"
                  className="text-white/70 hover:text-white font-light"
                  onClick={() => {
                    // Handle logout
                    useAuthStore.getState().logout();
                  }}
                >
                  Sign Out
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="ghost"
                  className="text-white/70 hover:text-white font-light"
                  onClick={() => window.location.href = '/auth/sign-in'}
                >
                  Sign In
                </Button>
                <Button
                  className="bg-gradient-to-r from-neural-purple-500 to-neural-purple-600 
                           text-white font-light hover:from-neural-purple-400 hover:to-neural-purple-500
                           transition-all duration-300"
                  onClick={() => window.location.href = '/auth/sign-up'}
                >
                  Get Started
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
