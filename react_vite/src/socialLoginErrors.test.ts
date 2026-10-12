import { describe, expect, it } from 'vitest';
import { describeSocialLoginError } from './socialLoginErrors';

describe('describeSocialLoginError', () => {
  it('says nothing when the person closed the window', () => {
    expect(describeSocialLoginError('auth/popup-closed-by-user', 'google')).toBeNull();
    expect(describeSocialLoginError('auth/cancelled-popup-request', 'apple')).toBeNull();
  });

  it('names the provider', () => {
    expect(describeSocialLoginError('auth/popup-blocked', 'apple')).toContain('Apple');
    expect(describeSocialLoginError('auth/popup-blocked', 'google')).toContain('Google');
  });

  it('explains an existing account with another sign-in method', () => {
    expect(describeSocialLoginError('auth/account-exists-with-different-credential', 'google')).toContain('already exists');
  });

  it('falls back to a generic message', () => {
    expect(describeSocialLoginError('auth/internal-error', 'google')).toContain('failed');
    expect(describeSocialLoginError(undefined, 'apple')).toContain('Apple');
  });
});
