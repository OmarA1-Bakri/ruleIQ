'use client';
import { Home, ClipboardCheck, FileText, Shield, BarChart3, X } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';

interface MobileNavProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const navigationItems = [
  {
    title: 'Dashboard',
    href: '/',
    icon: Home,
  },
  {
    title: 'Assessments',
    href: '/assessments',
    icon: ClipboardCheck,
  },
  {
    title: 'Evidence',
    href: '/evidence',
    icon: FileText,
  },
  {
    title: 'Policies',
    href: '/policies',
    icon: Shield,
  },
  {
    title: 'Reports',
    href: '/reports',
    icon: BarChart3,
  },
];

export function MobileNav({ open, onOpenChange }: MobileNavProps) {
  const pathname = usePathname();

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="left"
        className="w-[300px] p-0 sm:w-[400px] bg-white border-r border-neutral-200"
      >
        <SheetHeader
          className="border-b border-neutral-200 px-6 py-4"
        >
          <div className="flex items-center justify-between">
            <SheetTitle className="flex items-center space-x-1">
              <span className="text-xl font-bold text-neutral-700">
                rule
              </span>
              <span className="text-xl font-bold text-teal-600">
                IQ
              </span>
            </SheetTitle>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onOpenChange(false)}
              className="text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100"
            >
              <X className="h-5 w-5" />
            </Button>
          </div>
        </SheetHeader>
        <div className="flex flex-col space-y-2 p-6">
          {navigationItems.map((item) => {
            const isActive =
              pathname === item.href || (item.href !== '/' && pathname?.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => onOpenChange(false)}
                className={`flex items-center space-x-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-teal-50 text-teal-700 shadow-sm'
                    : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-50'
                }`}
              >
                <item.icon
                  className={`h-5 w-5 ${
                    isActive ? 'text-teal-600' : 'text-neutral-500'
                  }`}
                />
                <span>{item.title}</span>
              </Link>
            );
          })}
        </div>
      </SheetContent>
    </Sheet>
  );
}
