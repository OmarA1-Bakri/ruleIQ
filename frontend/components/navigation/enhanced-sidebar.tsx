'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  FileText,
  BarChart3,
  FolderOpen,
  Settings,
  ChevronLeft,
  ChevronRight,
  Home,
  Shield,
  FileCheck,
  AlertTriangle,
  Users,
  HelpCircle,
  LogOut,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
} from '@/components/ui/sidebar';

interface MenuItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
  badge?: number;
  disabled?: boolean;
  children?: MenuItem[];
}

const menuItems: MenuItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: Home, href: '/dashboard' },
  { id: 'policies', label: 'Policies', icon: FileText, href: '/policies', badge: 3 },
  { id: 'evidence', label: 'Evidence', icon: FolderOpen, href: '/evidence' },
  { id: 'risks', label: 'Risk Assessment', icon: AlertTriangle, href: '/risks', badge: 5 },
  { id: 'compliance', label: 'Compliance', icon: Shield, href: '/compliance' },
  { id: 'reports', label: 'Reports', icon: BarChart3, href: '/reports' },
  { id: 'audit', label: 'Audit Logs', icon: FileCheck, href: '/audit' },
  { id: 'team', label: 'Team', icon: Users, href: '/team' },
  { id: 'settings', label: 'Settings', icon: Settings, href: '/settings' },
];

interface EnhancedSidebarProps {
  className?: string;
  defaultCollapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
}

export function EnhancedSidebar({
  className,
  defaultCollapsed = false,
  onCollapsedChange,
}: EnhancedSidebarProps) {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [_expandedItems, _setExpandedItems] = useState<string[]>([]);
  const menuRef = useRef<HTMLUListElement>(null);
  const itemRefs = useRef<(HTMLAnchorElement | null)[]>([]);

  // Handle collapse state change
  const handleCollapse = useCallback((collapsed: boolean) => {
    setIsCollapsed(collapsed);
    onCollapsedChange?.(collapsed);
    // Store preference in localStorage
    localStorage.setItem('sidebar-collapsed', collapsed.toString());
  }, [onCollapsedChange]);

  // Load collapsed state from localStorage
  useEffect(() => {
    const stored = localStorage.getItem('sidebar-collapsed');
    if (stored !== null) {
      handleCollapse(stored === 'true');
    }
  }, [handleCollapse]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!menuRef.current?.contains(document.activeElement)) return;

      switch (e.key) {
        case 'ArrowUp':
          e.preventDefault();
          setFocusedIndex((prev) => (prev > 0 ? prev - 1 : menuItems.length - 1));
          break;
        case 'ArrowDown':
          e.preventDefault();
          setFocusedIndex((prev) => (prev < menuItems.length - 1 ? prev + 1 : 0));
          break;
        case 'ArrowLeft':
          e.preventDefault();
          if (!isCollapsed) {
            handleCollapse(true);
          }
          break;
        case 'ArrowRight':
          e.preventDefault();
          if (isCollapsed) {
            handleCollapse(false);
          }
          break;
        case 'Enter':
        case ' ':
          e.preventDefault();
          itemRefs.current[focusedIndex]?.click();
          break;
        case 'Escape':
          e.preventDefault();
          if (isCollapsed) {
            handleCollapse(false);
          }
          (document.activeElement as HTMLElement)?.blur();
          break;
        case 'Home':
          e.preventDefault();
          setFocusedIndex(0);
          break;
        case 'End':
          e.preventDefault();
          setFocusedIndex(menuItems.length - 1);
          break;
      }
    };

    // Typeahead search
    let searchBuffer = '';
    let searchTimeout: NodeJS.Timeout;

    const handleTypeahead = (e: KeyboardEvent) => {
      if (!menuRef.current?.contains(document.activeElement)) return;
      if (e.key.length !== 1 || e.metaKey || e.ctrlKey || e.altKey) return;

      clearTimeout(searchTimeout);
      searchBuffer += e.key.toLowerCase();

      const matchingIndex = menuItems.findIndex((item) =>
        item.label.toLowerCase().startsWith(searchBuffer)
      );

      if (matchingIndex !== -1) {
        setFocusedIndex(matchingIndex);
        itemRefs.current[matchingIndex]?.focus();
      }

      searchTimeout = setTimeout(() => {
        searchBuffer = '';
      }, 500);
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('keypress', handleTypeahead);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('keypress', handleTypeahead);
      clearTimeout(searchTimeout);
    };
  }, [focusedIndex, isCollapsed, handleCollapse]);

  // Focus management
  useEffect(() => {
    itemRefs.current[focusedIndex]?.focus();
  }, [focusedIndex]);

  const isActive = (href: string) => {
    return pathname === href || pathname?.startsWith(href + '/');
  };

  return (
    <TooltipProvider>
      <aside
        className={cn(
          'sticky top-0 h-screen border-r border-purple-200/20 bg-white/95 backdrop-blur transition-all duration-300 ease-in-out',
          isCollapsed ? 'w-20' : 'w-64',
          className
        )}
        role="navigation"
        aria-label="Main navigation"
      >
        <Sidebar className="h-full">
          {/* Skip to main content link */}
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 z-50 rounded-md bg-purple-600 px-3 py-2 text-sm font-medium text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2"
          >
            Skip to main content
          </a>

          <SidebarHeader className="flex h-16 items-center justify-between px-4">
            <Link
              href="/"
              className={cn(
                'flex items-center gap-2 transition-opacity',
                isCollapsed && 'opacity-0 pointer-events-none'
              )}
              aria-label="ruleIQ Home"
            >
              <span className="text-2xl font-extralight text-purple-600">ruleIQ</span>
            </Link>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => handleCollapse(!isCollapsed)}
              aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              aria-expanded={!isCollapsed}
              className="text-purple-600 hover:bg-purple-50 hover:text-purple-700"
            >
              {isCollapsed ? (
                <ChevronRight className="h-4 w-4" />
              ) : (
                <ChevronLeft className="h-4 w-4" />
              )}
            </Button>
          </SidebarHeader>

          <SidebarContent className="px-2 py-2">
            <SidebarMenu ref={menuRef} role="menu">
              {menuItems.map((item, index) => {
                const active = isActive(item.href);
                const Icon = item.icon;

                const menuButton = (
                  <SidebarMenuItem key={item.id} role="none">
                    <SidebarMenuButton
                      asChild
                      isActive={active}
                      className={cn(
                        'w-full justify-start font-light text-gray-600 transition-all hover:bg-purple-50 hover:text-purple-600',
                        active && 'bg-purple-600/10 text-purple-600 font-normal',
                        focusedIndex === index && 'ring-2 ring-purple-600 ring-offset-2',
                        isCollapsed && 'justify-center px-2',
                        item.disabled && 'opacity-50 cursor-not-allowed'
                      )}
                      aria-disabled={item.disabled}
                    >
                      <Link
                        href={item.href}
                        ref={(el) => { itemRefs.current[index] = el; }}
                        role="menuitem"
                        aria-current={active ? 'page' : undefined}
                        aria-label={item.label}
                        tabIndex={focusedIndex === index ? 0 : -1}
                        onClick={(e) => item.disabled && e.preventDefault()}
                      >
                        <Icon
                          className={cn('h-5 w-5 flex-shrink-0', !isCollapsed && 'mr-3')}
                          aria-hidden="true"
                        />
                        <span
                          className={cn(
                            'flex-1 transition-opacity',
                            isCollapsed && 'sr-only'
                          )}
                        >
                          {item.label}
                        </span>
                        {!isCollapsed && item.badge && (
                          <span className="ml-auto flex h-5 min-w-[20px] items-center justify-center rounded-full bg-purple-600 px-1 text-xs font-medium text-white">
                            {item.badge}
                          </span>
                        )}
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );

                if (isCollapsed) {
                  return (
                    <Tooltip key={item.id} delayDuration={0}>
                      <TooltipTrigger asChild>{menuButton}</TooltipTrigger>
                      <TooltipContent
                        side="right"
                        className="bg-purple-600 text-white"
                      >
                        <p>{item.label}</p>
                        {item.badge && (
                          <span className="ml-2 rounded bg-white/20 px-1 text-xs">
                            {item.badge}
                          </span>
                        )}
                      </TooltipContent>
                    </Tooltip>
                  );
                }

                return menuButton;
              })}
            </SidebarMenu>
          </SidebarContent>

          <SidebarFooter className="border-t border-purple-200/20 p-4">
            <div
              className={cn(
                'flex items-center gap-3',
                isCollapsed && 'justify-center'
              )}
            >
              <Button
                variant="ghost"
                size={isCollapsed ? 'icon' : 'default'}
                className="w-full justify-start text-gray-600 hover:bg-purple-50 hover:text-purple-600"
                aria-label="Help & Support"
              >
                <HelpCircle className={cn('h-5 w-5', !isCollapsed && 'mr-2')} />
                {!isCollapsed && <span className="font-light">Help & Support</span>}
              </Button>
            </div>
            <div
              className={cn(
                'mt-2 flex items-center gap-3',
                isCollapsed && 'justify-center'
              )}
            >
              <Button
                variant="ghost"
                size={isCollapsed ? 'icon' : 'default'}
                className="w-full justify-start text-red-600 hover:bg-red-50 hover:text-red-700"
                aria-label="Sign Out"
              >
                <LogOut className={cn('h-5 w-5', !isCollapsed && 'mr-2')} />
                {!isCollapsed && <span className="font-light">Sign Out</span>}
              </Button>
            </div>
          </SidebarFooter>
        </Sidebar>
      </aside>
    </TooltipProvider>
  );
}