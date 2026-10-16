/**
 * Sign in with Google or Apple on the login and signup pages (Django templates).
 *
 * The person signs in with the provider through Firebase, the same way as in the app, and the Firebase ID token is
 * handed to the server, which verifies it and starts the ordinary Django session (display.views_social_login). The
 * email/password form keeps working as before.
 */
import { initializeApp } from 'firebase/app';
import { GoogleAuthProvider, OAuthProvider, getAuth, inMemoryPersistence, setPersistence, signInWithPopup } from 'firebase/auth';
import type { AuthProvider } from 'firebase/auth';

import { getCookie } from './utils/csrf';
import { describeSocialLoginError } from './socialLoginErrors';

interface SocialLoginRoot extends HTMLElement {
  dataset: DOMStringMap & { endpoint?: string; next?: string };
}

function providerFor(name: string): AuthProvider | null {
  if (name === 'google') {
    const provider = new GoogleAuthProvider();
    provider.setCustomParameters({ prompt: 'select_account' });
    return provider;
  }
  if (name === 'apple') {
    const provider = new OAuthProvider('apple.com');
    provider.addScope('email');
    provider.addScope('name');
    return provider;
  }
  return null;
}

function init() {
  const root = document.getElementById('social-login') as SocialLoginRoot | null;
  const configElement = document.getElementById('firebase-web-config');
  if (!root || !configElement?.textContent) return;

  const auth = getAuth(initializeApp(JSON.parse(configElement.textContent)));
  const buttons = Array.from(root.querySelectorAll<HTMLButtonElement>('button[data-provider]'));
  const message = root.querySelector<HTMLElement>('[data-social-login-error]');

  const showError = (text: string | null) => {
    if (!message) return;
    message.textContent = text ?? '';
    message.classList.toggle('hidden', !text);
  };
  const setBusy = (busy: boolean) => buttons.forEach((button) => (button.disabled = busy));

  async function signIn(name: string) {
    const provider = providerFor(name);
    if (!provider) return;
    showError(null);
    setBusy(true);
    let redirectTo: string | null = null;
    try {
      // Firebase only vouches for the person to the server once; the browser must not keep the identity (it is
      // persisted across restarts by default), whether or not the server login that follows succeeds.
      await setPersistence(auth, inMemoryPersistence);
      const credential = await signInWithPopup(auth, provider);
      const idToken = await credential.user.getIdToken();
      const response = await fetch(root!.dataset.endpoint ?? '', {
        method: 'POST',
        credentials: 'same-origin',
        // The body carries the token: never follow a redirect (a 307/308 would forward it to the new target)
        redirect: 'error',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') ?? '' },
        body: JSON.stringify({ id_token: idToken, next: root!.dataset.next ?? '' }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        showError((body.error ?? 'Sign-in failed. Please try again.') + (body.detail ? ` [${body.detail}]` : ''));
      } else {
        redirectTo = body.redirect || '/';
      }
    } catch (error) {
      console.error(`Sign-in with ${name} failed`, error);
      showError(describeSocialLoginError((error as { code?: string }).code, name));
    } finally {
      // The server session is what counts from here
      await auth.signOut().catch(() => undefined);
    }
    if (redirectTo) {
      window.location.assign(redirectTo);
    } else {
      setBusy(false);
    }
  }

  buttons.forEach((button) => button.addEventListener('click', () => signIn(button.dataset.provider ?? '')));
}

init();
