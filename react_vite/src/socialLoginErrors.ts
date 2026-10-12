/**
 * What to tell the person when Google or Apple sign-in does not complete. Returns null for the cases where nothing
 * should be shown (the person closed the popup themselves).
 */
export function describeSocialLoginError(code: string | undefined, provider: string): string | null {
  const name = provider === 'apple' ? 'Apple' : 'Google';
  switch (code) {
    case 'auth/popup-closed-by-user':
    case 'auth/cancelled-popup-request':
    case 'auth/user-cancelled':
      return null;
    case 'auth/popup-blocked':
      return `Your browser blocked the ${name} sign-in window. Allow pop-ups for this site and try again.`;
    case 'auth/account-exists-with-different-credential':
      return 'An account with this email address already exists with another way of signing in. Sign in with that method (for example your password) instead.';
    case 'auth/network-request-failed':
      return 'Could not reach the sign-in service. Check your connection and try again.';
    case 'auth/unauthorized-domain':
      return 'Sign-in with ' + name + ' is not enabled for this address.';
    default:
      return `Sign-in with ${name} failed. Please try again, or use your email and password.`;
  }
}
