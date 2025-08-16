"use client";

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { CommandPalette } from '@/components/dashboard/command-palette';
import { KeyboardShortcutsDialog } from '@/components/dashboard/keyboard-shortcuts-dialog';
import { QuickActionsPanel } from '@/components/dashboard/quick-actions';
import { AppSidebar } from '@/components/navigation/app-sidebar';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import { ChatWidget } from '@/components/chat/chat-widget';
import { useAuthStore } from '@/lib/stores/auth.store';
import { Loader2 } from 'lucide-react';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { isAuthenticated, isLoading, checkAuthStatus } = useAuthStore();

  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // Will redirect to login
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        {children}
        <QuickActionsPanel />
        <KeyboardShortcutsDialog />
        <CommandPalette />
        <ChatWidget 
          position="bottom-right" 
          defaultOpen={false}
          enableVoice={true}
        />
      </SidebarInset>
    </SidebarProvider>
  );
}