'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/stores/auth.store';

export default function AuthCallbackPage() {
  const router = useRouter();
  const setTokens = useAuthStore((state) => state.setTokens);
  const checkAuthStatus = useAuthStore((state) => state.checkAuthStatus);

  useEffect(() => {
    const completeGoogleSignIn = async () => {
      const hash = window.location.hash.startsWith('#')
        ? window.location.hash.slice(1)
        : window.location.hash;
      const params = new URLSearchParams(hash);
      const accessToken = params.get('access_token');
      const refreshToken = params.get('refresh_token');
      const isNewUser = params.get('new_user') === 'true';

      if (!accessToken || !refreshToken) {
        router.replace('/login');
        return;
      }

      setTokens({
        access_token: accessToken,
        refresh_token: refreshToken,
        token_type: 'bearer',
      });

      await checkAuthStatus();
      router.replace(isNewUser ? '/onboarding' : '/dashboard');
    };

    void completeGoogleSignIn();
  }, [checkAuthStatus, router, setTokens]);

  return <div>Signing you in...</div>;
}