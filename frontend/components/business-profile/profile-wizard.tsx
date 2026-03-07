'use client';

/**
 * ProfileWizard — stub component.
 * The real implementation does not exist yet. This stub is a placeholder
 * so tests that import it can resolve the module without errors.
 */

import React from 'react';

interface ProfileWizardProps {
  onComplete?: () => void;
}

export function ProfileWizard({ onComplete }: ProfileWizardProps) {
  return (
    <div data-testid="profile-wizard-stub">
      <p>Profile Wizard (stub — not yet implemented)</p>
      <button type="button" onClick={onComplete}>
        Complete
      </button>
    </div>
  );
}
